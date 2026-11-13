<#
.SYNOPSIS
  Builds C:\SnafiWorker (the Snafi worker's own copy, with its own private Python) and sets
  folder permissions for the Windows user the worker runs as: you (Khalid), since Nov 13, 2026.
  The separate worker user is kept dormant for a possible return to agy; it is not used, only
  still kept out of your folders.

  First, as YOURSELF in a normal (not admin) PowerShell from the repo folder, build Ahmad's
  prompt text (this runs REEMA's own Python, so it must not run as administrator):
      .venv\Scripts\python.exe -m src.snafi_worker.prompt --write src\snafi_worker\ahmad_base.txt
  Then, in an ADMIN PowerShell from the repo folder:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\deploy.ps1

.DESCRIPTION
  1. Locks C:\SnafiWorker first: Administrators and SYSTEM full; you read and run only, so the
     worker (running as you, not elevated) cannot change its own code.
  2. Refuses if src\snafi_worker has uncommitted changes, then copies only that folder (with the
     prompt text you built) and the launcher. No REEMA code runs as administrator (SEC-30).
  3. Gives the worker its own private Python 3.12.10: python.org's official NuGet package (a zip,
     no installer), downloaded into the locked folder, checked against its pinned SHA-256 (which
     matches the SHA-512 nuget.org publishes for it), and unpacked fresh into C:\SnafiWorker\python.
     It does not touch, need or conflict with any other Python on this PC. Then installs exactly
     pyyaml 6.0.3 and tzdata 2026.6 into it, as wheels whose SHA-256 must match
     requirements-worker.txt.
  4. Lets you (and so the worker) change files in the backups folder, with Administrators and
     SYSTEM; nobody else. Your own processes, Claude Code included, can now open it: only Claude
     Code's deny rules and its guard keep sessions out (a backstop, not an OS boundary). The dormant
     worker user, if it exists, stays denied on D:\Projects and D:\Antigravity_Projects.
  5. Makes Administrators the owner of C:\SnafiWorker and the backups folder, so no normal process
     can change their permissions back.
  Run it again after every Snafi worker update; it replaces the app folder and unpacks a fresh Python.
#>
param(
    [string]$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path,
    [string]$Target = "C:\SnafiWorker",
    [string]$RunAs = [Security.Principal.WindowsIdentity]::GetCurrent().Name,   # you: the worker runs as this user
    [string]$DormantUser = "worker",   # kept, unused, in case agy returns
    [string[]]$DenyFolders = @("D:\Projects", "D:\Antigravity_Projects"),
    [string]$Backups = "D:\Projects\IT Consultant\teams\coordination\snafi-backups"
)
$ErrorActionPreference = "Stop"

# python.org's official NuGet package of Python 3.12.10 (Python Software Foundation).
# SHA-256 of the .nupkg, checked on every deploy. nuget.org publishes this package's SHA-512 as
# u9pNz2iKlCEbYtUJaKkbOPMF0LjR7NkCafdKhvigpPzrt8oWKgdTpHaR6z3wyWQAm9PYGUxv0Zr66NX9AeHMDw== (checked when pinned).
$PythonVersion = "3.12.10"
$PythonUrl = "https://www.nuget.org/api/v2/package/python/3.12.10"
$PythonSha256 = "0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this in an administrator PowerShell." }
Stop-ScheduledTask -TaskName "Snafi Worker" -ErrorAction SilentlyContinue   # files may be in use; start it again afterwards
try { $runAsSid = (New-Object Security.Principal.NTAccount($RunAs)).Translate([Security.Principal.SecurityIdentifier]).Value }
catch { throw "The Windows user '$RunAs' was not found." }
if ($runAsSid -eq "S-1-5-18" -or $runAsSid -eq "S-1-5-32-544") { throw "Run the worker as your own user, not as '$RunAs'." }
Write-Host "The worker will run as $RunAs."
$source = Join-Path $Repo "src\snafi_worker"
if (-not (Test-Path (Join-Path $source "ahmad_base.txt"))) {
    throw "Build Ahmad's prompt text first, as yourself (not admin): .venv\Scripts\python.exe -m src.snafi_worker.prompt --write src\snafi_worker\ahmad_base.txt"
}
$dirty = & git -c core.fsmonitor= -C $Repo status --porcelain -- "src/snafi_worker"
if ($LASTEXITCODE -ne 0) { throw "Could not check git status of src\snafi_worker." }
if ($dirty) { throw "src\snafi_worker has uncommitted changes; commit or discard them before deploying:`n$dirty" }

# 1. Lock the target before anything is copied into it
New-Item -ItemType Directory -Force -Path $Target | Out-Null
icacls $Target /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*${runAsSid}:(OI)(CI)RX" /Q | Out-Null
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

# 3. The worker's own private Python: the official NuGet package, hash-checked, unpacked fresh
$downloads = Join-Path $Target "downloads"
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$package = Join-Path $downloads "python.$PythonVersion.nupkg"
$haveGood = (Test-Path $package) -and ((Get-FileHash -Algorithm SHA256 $package).Hash -eq $PythonSha256)
if (-not $haveGood) {
    Remove-Item -Force $package -ErrorAction SilentlyContinue
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $package
}
$hash = (Get-FileHash -Algorithm SHA256 $package).Hash
if ($hash -ne $PythonSha256) {
    Remove-Item -Force $package
    throw "The Python package's SHA-256 ($hash) does not match the pinned $PythonSha256; nothing was installed."
}
$pythonHome = Join-Path $Target "python"
if (Test-Path $pythonHome) { Remove-Item -Recurse -Force $pythonHome }   # fresh every deploy, so every wheel is hash-checked (SEC-36)
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($package, $pythonHome)
$py = Join-Path $pythonHome "tools\python.exe"
if (-not (Test-Path $py)) { throw "The Python package did not contain tools\python.exe." }
$version = & $py -I -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
if ($version -ne $PythonVersion) { throw "Expected Python $PythonVersion in the package, found $version." }
& $py -I -m pip install --no-input --disable-pip-version-check --no-warn-script-location `
    --require-hashes --only-binary=:all: --no-deps -r (Join-Path $Target "requirements-worker.txt")
if ($LASTEXITCODE -ne 0) { throw "Installing the worker's packages failed (hash or version mismatch?)." }
$oldVenv = Join-Path $Target "venv"
if (Test-Path $oldVenv) { Remove-Item -Recurse -Force $oldVenv }   # the earlier layout used a venv
icacls (Join-Path $Target "*") /reset /T /Q | Out-Null   # the contents inherit the lock; the folder keeps it
icacls $Target /setowner "*S-1-5-32-544" /T /C /Q | Out-Null   # owned by Administrators, so no normal process can re-open it (SEC-36)

# 4. The dormant worker user stays out of your folders; the backups folder is yours (and the worker's)
$dormant = Get-LocalUser -Name $DormantUser -ErrorAction SilentlyContinue
if ($dormant) {
    foreach ($folder in $DenyFolders) {
        if (Test-Path $folder) {
            icacls $folder /deny "*$($dormant.SID.Value):(OI)(CI)F" /Q | Out-Null
            Write-Host "Kept the dormant $DormantUser user denied on $folder"
        }
    }
}
New-Item -ItemType Directory -Force -Path $Backups | Out-Null
icacls $Backups /setowner "*S-1-5-32-544" /T /C /Q | Out-Null   # a worker run may have created it as you (SEC-36)
icacls $Backups /inheritance:r /grant:r "*S-1-5-32-544:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*${runAsSid}:(OI)(CI)M" /Q | Out-Null
if ($dormant) { icacls $Backups /remove:g "*$($dormant.SID.Value)" /Q | Out-Null }   # the dormant user no longer writes backups

Write-Host ""
Write-Host "Deployed the Snafi worker to $Target with its own Python $PythonVersion, to run as $RunAs."
Write-Host "Next, as yourself in a normal PowerShell: $Target\snafi.cmd set-secrets, then $Target\snafi.cmd check"
