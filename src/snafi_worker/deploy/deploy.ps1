<#
.SYNOPSIS
  Builds C:\SnafiWorker (the Snafi worker's own copy) and sets folder permissions for the
  snafi-worker Windows user. Run it yourself in an ADMIN PowerShell from the repo folder:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\deploy.ps1

.DESCRIPTION
  1. Copies only src\snafi_worker into C:\SnafiWorker\app, with Ahmad's prompt text built from
     REEMA, and the launcher (snafi.cmd, snafi.py).
  2. Creates C:\SnafiWorker\venv from machine-wide Python 3.12.10 and installs exactly
     pyyaml 6.0.3 and tzdata 2026.6 (the approved list). Nothing else.
  3. Permissions:
     - C:\SnafiWorker: Administrators and SYSTEM full; snafi-worker and you read and run only,
       so the worker cannot change its own code.
     - D:\Projects (and the other folders in -DenyFolders): snafi-worker DENIED, so it cannot read
       or change your projects, the Customer references or your task store.
     - The backups folder only: snafi-worker may write there.
  Run it again after every Snafi worker update; it replaces the app folder and keeps the venv.
  It changes nothing for any other user. To undo the permissions, see the README.
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
$account = Get-LocalUser -Name $WorkerUser -ErrorAction SilentlyContinue
if (-not $account) { throw "The Windows user '$WorkerUser' does not exist yet. Create it first (README)." }
if ((Get-LocalGroupMember -Group Administrators | Where-Object { $_.Name -like "*\$WorkerUser" })) {
    throw "'$WorkerUser' must NOT be an administrator. Remove it from Administrators first."
}
if (-not (Test-Path $Python)) { throw "Machine-wide Python not found at $Python (install 3.12.10 for all users)." }
$version = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($version -ne "3.12.10") { throw "Expected Python 3.12.10 at $Python, found $version." }
$repoPython = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $repoPython)) { throw "REEMA's .venv was not found at $repoPython." }

# 1. The app copy
$app = Join-Path $Target "app"
New-Item -ItemType Directory -Force -Path (Join-Path $app "src") | Out-Null
robocopy (Join-Path $Repo "src\snafi_worker") (Join-Path $app "src\snafi_worker") /MIR /XD __pycache__ deploy /XF *.pyc /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copying the worker failed (robocopy $LASTEXITCODE)." }
Set-Content -Path (Join-Path $app "src\__init__.py") -Value "" -Encoding UTF8
Copy-Item (Join-Path $PSScriptRoot "snafi.py") (Join-Path $app "snafi.py") -Force
Copy-Item (Join-Path $PSScriptRoot "snafi.cmd") (Join-Path $Target "snafi.cmd") -Force
Push-Location $Repo
try {
    & $repoPython -I -c "import sys; sys.path.insert(0, r'$Repo'); from src.snafi_worker.prompt import main; sys.exit(main(['--write', r'$app\src\snafi_worker\ahmad_base.txt']))"
    if ($LASTEXITCODE -ne 0) { throw "Building Ahmad's prompt text failed." }
} finally { Pop-Location }

# 2. The worker's own Python environment, with exactly the approved packages
$venv = Join-Path $Target "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { & $Python -m venv $venv }
& (Join-Path $venv "Scripts\python.exe") -m pip install --no-input --disable-pip-version-check "pyyaml==6.0.3" "tzdata==2026.6"
if ($LASTEXITCODE -ne 0) { throw "Installing pyyaml and tzdata failed." }

# 3. Permissions
$me = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $Target /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "${WorkerUser}:(OI)(CI)RX" "${me}:(OI)(CI)RX" /T /Q | Out-Null
foreach ($folder in $DenyFolders) {
    if (Test-Path $folder) {
        icacls $folder /deny "${WorkerUser}:(OI)(CI)F" /Q | Out-Null
        Write-Host "Denied $WorkerUser on $folder"
    }
}
New-Item -ItemType Directory -Force -Path $Backups | Out-Null
icacls $Backups /grant "${WorkerUser}:(OI)(CI)M" /Q | Out-Null

Write-Host ""
Write-Host "Deployed the Snafi worker to $Target."
Write-Host "Next, as $WorkerUser: install and sign in to agy, then run: $Target\snafi.cmd set-secrets, then: $Target\snafi.cmd prove"
