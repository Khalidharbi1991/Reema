<#
.SYNOPSIS
  Builds C:\SnafiWorker (the Snafi worker's own copy) and sets folder permissions for the
  snafi-worker Windows user.

  First, as YOURSELF in a normal (not admin) PowerShell from the repo folder, build Ahmad's
  prompt text (this runs REEMA's own Python, so it must not run as administrator):
      .venv\Scripts\python.exe -m src.snafi_worker.prompt --write src\snafi_worker\ahmad_base.txt
  Then, in an ADMIN PowerShell from the repo folder:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\deploy.ps1

.DESCRIPTION
  1. Locks C:\SnafiWorker first: Administrators and SYSTEM full; snafi-worker and you read and
     run only, so the worker cannot change its own code.
  2. Refuses if src\snafi_worker has uncommitted changes, then copies only that folder (with the
     prompt text you built) and the launcher. No REEMA code runs as administrator (SEC-30).
  3. Creates C:\SnafiWorker\venv from machine-wide Python 3.12.10 and installs exactly pyyaml
     6.0.3 and tzdata 2026.6, as wheels whose SHA-256 must match requirements-worker.txt.
  4. Denies snafi-worker on D:\Projects and D:\Antigravity_Projects, and lets it write only to
     the backups folder, which is locked to snafi-worker, Administrators and SYSTEM (your normal,
     non-admin processes, Claude Code included, cannot open it).
  5. Makes Administrators the owner of C:\SnafiWorker and the backups folder, so no normal process
     (yours or the worker's) can change their permissions back.
  Run it again after every Snafi worker update; it replaces the app folder and rebuilds the venv.
#>
param(
    [string]$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$Target = "C:\SnafiWorker",
    [string]$WorkerUser = "snafi-worker",
    [string]$Python = "C:\Program Files\Python312\python.exe",
    [string[]]$DenyFolders = @("D:\Projects", "D:\Antigravity_Projects"),
    [string]$Backups = "D:\Projects\IT Consultant\teams\coordination\snafi-backups"
)
$ErrorActionPreference = "Stop"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this in an administrator PowerShell." }
Stop-ScheduledTask -TaskName "Snafi Worker" -ErrorAction SilentlyContinue   # files may be in use; start it again afterwards
$account = Get-LocalUser -Name $WorkerUser -ErrorAction SilentlyContinue
if (-not $account) { throw "The Windows user '$WorkerUser' does not exist yet. Create it first (README)." }
if ((Get-LocalGroupMember -Group Administrators | Where-Object { $_.Name -like "*\$WorkerUser" })) {
    throw "'$WorkerUser' must NOT be an administrator. Remove it from Administrators first."
}
if (-not (Test-Path $Python)) { throw "Machine-wide Python not found at $Python (install 3.12.10 for all users)." }
$version = & $Python -I -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($version -ne "3.12.10") { throw "Expected Python 3.12.10 at $Python, found $version." }
$source = Join-Path $Repo "src\snafi_worker"
if (-not (Test-Path (Join-Path $source "ahmad_base.txt"))) {
    throw "Build Ahmad's prompt text first, as yourself (not admin): .venv\Scripts\python.exe -m src.snafi_worker.prompt --write src\snafi_worker\ahmad_base.txt"
}
$dirty = & git -c core.fsmonitor= -C $Repo status --porcelain -- "src/snafi_worker"
if ($LASTEXITCODE -ne 0) { throw "Could not check git status of src\snafi_worker." }
if ($dirty) { throw "src\snafi_worker has uncommitted changes; commit or discard them before deploying:`n$dirty" }

# 1. Lock the target before anything is copied into it
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
New-Item -ItemType Directory -Force -Path $Target | Out-Null
icacls $Target /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "${WorkerUser}:(OI)(CI)RX" "${me}:(OI)(CI)RX" /Q | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Locking $Target failed." }

# 2. The app copy (files only; nothing from the repo is executed here)
$app = Join-Path $Target "app"
New-Item -ItemType Directory -Force -Path (Join-Path $app "src") | Out-Null
robocopy $source (Join-Path $app "src\snafi_worker") /MIR /XD __pycache__ deploy /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copying the worker failed (robocopy $LASTEXITCODE)." }
Set-Content -Path (Join-Path $app "src\__init__.py") -Value "" -Encoding UTF8
Copy-Item (Join-Path $PSScriptRoot "snafi.py") (Join-Path $app "snafi.py") -Force
Copy-Item (Join-Path $PSScriptRoot "snafi.cmd") (Join-Path $Target "snafi.cmd") -Force
Copy-Item (Join-Path $PSScriptRoot "requirements-worker.txt") (Join-Path $Target "requirements-worker.txt") -Force

# 3. The worker's own Python environment: exactly the approved wheels, checked by SHA-256
$venv = Join-Path $Target "venv"
if (Test-Path $venv) { Remove-Item -Recurse -Force $venv }   # rebuilt every time, so every wheel is hash-checked (SEC-36)
& $Python -I -m venv $venv
& (Join-Path $venv "Scripts\python.exe") -I -m pip install --no-input --disable-pip-version-check `
    --require-hashes --only-binary=:all: --no-deps -r (Join-Path $Target "requirements-worker.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing the worker's packages failed (hash or version mismatch?)." }
icacls (Join-Path $Target "*") /reset /T /Q | Out-Null   # the contents inherit the lock; the folder keeps it
icacls $Target /setowner "*S-1-5-32-544" /T /C /Q | Out-Null   # owned by Administrators, so no normal process can re-open it (SEC-36)

# 4. Keep the worker out of your folders; it may write only to the backups folder
foreach ($folder in $DenyFolders) {
    if (Test-Path $folder) {
        icacls $folder /deny "${WorkerUser}:(OI)(CI)F" /Q | Out-Null
        Write-Host "Denied $WorkerUser on $folder"
    }
}
New-Item -ItemType Directory -Force -Path $Backups | Out-Null
icacls $Backups /setowner "*S-1-5-32-544" /T /C /Q | Out-Null   # the step 2 worker may have created it as you (SEC-36)
icacls $Backups /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "${WorkerUser}:(OI)(CI)M" /Q | Out-Null

Write-Host ""
Write-Host "Deployed the Snafi worker to $Target."
Write-Host "Next, as ${WorkerUser}: install and sign in to agy, then run: $Target\snafi.cmd set-secrets, then: $Target\snafi.cmd prove"
