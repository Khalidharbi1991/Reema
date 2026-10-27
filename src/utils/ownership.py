"""Local kernel-held run ownership; files are never removed to break a lock."""

import os
from pathlib import Path
import socket
from uuid import uuid4


class RunLease:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.fd = None
        self.owner = {"host": socket.gethostname(), "pid": os.getpid(), "token": uuid4().hex}

    def __enter__(self):
        if self.fd is not None:
            raise RuntimeError("Run ownership lease is already held")
        path = self.directory / ".owner.lock"
        if path.is_symlink():
            raise ValueError("Run ownership file must not be a symlink")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if os.fstat(fd).st_ino != path.stat().st_ino:
                raise ValueError("Run ownership file changed during acquisition")
        except (OSError, ValueError):
            os.close(fd)
            raise RuntimeError("Run has an active owner or its ownership cannot be established; retry after it exits") from None
        self.fd = fd
        return self

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)  # The OS releases the lock, including after process death.

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()

    def permits(self, directory, owner=None):
        if self.fd is None or self.directory != Path(directory).resolve():
            raise ValueError("Recovery requires the held parent ownership lease")
        if owner and owner.get("host") != socket.gethostname():
            raise ValueError("Cross-host run recovery requires an explicit transfer; local liveness is insufficient")
