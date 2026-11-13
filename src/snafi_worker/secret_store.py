"""The worker's secrets in Windows Credential Manager (SEC-14).

Each value is a generic credential named "REEMA-Snafi:<NAME>" for the current Windows
user. Windows keeps it encrypted with DPAPI under that user's login, so it is never a
plain-text file on disk and other Windows users cannot read it. Programs running as the
same user can still ask Windows for it: Claude Code sessions are kept away by the deny
rules and .claude/hooks/dev_guard.py, which is a backstop, not a full guarantee.

Standard library only (ctypes); nothing is installed.
"""

import ctypes
import sys
from ctypes import wintypes
from typing import Dict, Iterable, Optional

PREFIX = "REEMA-Snafi:"
NAMES = ("SNAFI_SUPABASE_URL", "SNAFI_SUPABASE_SECRET_KEY", "SNAFI_OWNER_USER_ID", "GEMINI_API_KEY",
         "ANTHROPIC_API_KEY", "SNAFI_BACKUP_SIGNING_KEY")
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2  # this user, this PC, survives restarts; not roamed
ERROR_NOT_FOUND = 1168
MAX_BLOB = 2560


class SecretStoreError(Exception):
    pass


class MemoryCredentials:
    """For tests: same calls, nothing touches Windows."""

    def __init__(self, values: Optional[Dict[str, str]] = None):
        self.values = dict(values or {})

    def read(self, name: str) -> Optional[str]:
        return self.values.get(name)

    def write(self, name: str, value: str) -> None:
        self.values[name] = value

    def delete(self, name: str) -> None:
        self.values.pop(name, None)


if sys.platform == "win32":
    class _FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class _CREDENTIAL(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR), ("LastWritten", _FILETIME), ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD), ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]


class WindowsCredentials:
    """Windows Credential Manager for the current user (CredWriteW / CredReadW / CredDeleteW)."""

    def __init__(self, prefix: str = PREFIX):
        if sys.platform != "win32":
            raise SecretStoreError("Windows Credential Manager is only available on Windows")
        self.prefix = prefix
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        self._write = api.CredWriteW
        self._write.argtypes = [ctypes.POINTER(_CREDENTIAL), wintypes.DWORD]
        self._write.restype = wintypes.BOOL
        self._read = api.CredReadW
        self._read.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIAL))]
        self._read.restype = wintypes.BOOL
        self._delete = api.CredDeleteW
        self._delete.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._delete.restype = wintypes.BOOL
        self._free = api.CredFree
        self._free.argtypes = [ctypes.c_void_p]

    def _target(self, name: str) -> str:
        return self.prefix + name

    def read(self, name: str) -> Optional[str]:
        pointer = ctypes.POINTER(_CREDENTIAL)()
        if not self._read(self._target(name), CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == ERROR_NOT_FOUND:
                return None
            raise SecretStoreError(f"could not read {name} from Credential Manager")
        try:
            cred = pointer.contents
            return bytes(cred.CredentialBlob[: cred.CredentialBlobSize]).decode("utf-8")
        finally:
            self._free(pointer)

    def write(self, name: str, value: str) -> None:
        blob = value.encode("utf-8")
        if not blob or len(blob) > MAX_BLOB:
            raise SecretStoreError(f"{name} is empty or too long")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        cred = _CREDENTIAL()
        cred.Type = CRED_TYPE_GENERIC
        cred.TargetName = self._target(name)
        cred.Comment = "Snafi worker (REEMA)"
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        cred.Persist = CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = "snafi-worker"
        if not self._write(ctypes.byref(cred), 0):
            raise SecretStoreError(f"could not store {name} in Credential Manager")

    def delete(self, name: str) -> None:
        if not self._delete(self._target(name), CRED_TYPE_GENERIC, 0) and ctypes.get_last_error() != ERROR_NOT_FOUND:
            raise SecretStoreError(f"could not remove {name} from Credential Manager")


def load_all(backend, names: Iterable[str] = NAMES) -> Dict[str, str]:
    """Every stored value, by name. Missing ones are left out; values are never printed."""
    values = {}
    for name in names:
        value = backend.read(name)
        if value:
            values[name] = value
    return values
