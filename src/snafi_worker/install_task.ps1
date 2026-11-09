<#
.SYNOPSIS
  Registers (or removes) the "Snafi Worker" scheduled task for the current Windows user.

.DESCRIPTION
  Starts the Snafi worker when you log on, in the background (pythonw, no window), from
  REEMA's .venv, and restarts it every minute if it stops (up to 999 times). It runs only
  while you are logged on, as you, with normal (not elevated) rights. It needs no password.
  Run it yourself from a normal PowerShell window:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\install_task.ps1
  Remove the task:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\install_task.ps1 -Remove
#>
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$TaskName = "Snafi Worker"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Pythonw = Join-Path $Repo ".venv\Scripts\pythonw.exe"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed the '$TaskName' task."
    return
}
if (-not (Test-Path $Pythonw)) { throw "REEMA's .venv was not found at $Pythonw" }

$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "-m src.snafi_worker" -WorkingDirectory $Repo
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 999 `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Principal $Principal -Description "Snafi: Ahmad's worker (REEMA). Starts at logon; restarts if it stops." -Force | Out-Null
Write-Host "Registered '$TaskName' for $User. Start it now with: Start-ScheduledTask -TaskName '$TaskName'"
