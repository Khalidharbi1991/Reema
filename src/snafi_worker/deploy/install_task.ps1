<#
.SYNOPSIS
  Registers (or removes) the "Snafi Worker" scheduled task, run as YOU (Khalid).
  Run it yourself in an ADMIN PowerShell from the repo folder:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\install_task.ps1
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\install_task.ps1 -Remove

.DESCRIPTION
  Starts the worker when you sign in to Windows, as you, with normal (not elevated) rights, in
  the background (pythonw, isolated -I), and restarts it every minute if it stops. It runs only
  while you are signed in (a locked screen is fine); after a restart it starts again when you sign
  in. No password is asked for or stored: the task uses your sign-in, which also unlocks your
  Credential Manager, where set-secrets keeps the worker's keys.
  The dormant worker user (kept for a possible return to agy) is not used.
#>
param([switch]$Remove, [string]$RunAs = [Security.Principal.WindowsIdentity]::GetCurrent().Name,
      [string]$Target = "C:\SnafiWorker")

$ErrorActionPreference = "Stop"
$TaskName = "Snafi Worker"
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed the '$TaskName' task."
    return
}
$Pythonw = Join-Path $Target "python\tools\pythonw.exe"   # the worker's own private Python
$Launcher = Join-Path $Target "app\snafi.py"
if (-not (Test-Path $Pythonw) -or -not (Test-Path $Launcher)) { throw "Run deploy.ps1 first ($Target is not ready)." }

$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "-I `"$Launcher`" worker" -WorkingDirectory $Target
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $RunAs
$Principal = New-ScheduledTaskPrincipal -UserId $RunAs -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 999 `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings `
    -Description "Snafi: Ahmad's worker (REEMA), as $RunAs. Starts when $RunAs signs in; restarts if it stops." -Force | Out-Null
Write-Host "Registered '$TaskName' to run as $RunAs. Start it now with: Start-ScheduledTask -TaskName '$TaskName'"
