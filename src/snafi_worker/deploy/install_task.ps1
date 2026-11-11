<#
.SYNOPSIS
  Registers (or removes) the "Snafi Worker" scheduled task, run as the snafi-worker user.
  Run it yourself in an ADMIN PowerShell from the repo folder:
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\install_task.ps1
      powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\install_task.ps1 -Remove

.DESCRIPTION
  Starts the worker when Windows starts, whether or not anyone is logged on, as
  snafi-worker with normal (not elevated) rights, in the background (pythonw, isolated -I),
  and restarts it every minute if it stops. Windows asks for snafi-worker's password; it is
  stored by Windows' Task Scheduler, never by REEMA. Running with a stored password also
  loads snafi-worker's profile, which agy's sign-in and Credential Manager need.
#>
param([switch]$Remove, [string]$WorkerUser = "snafi-worker", [string]$Target = "C:\SnafiWorker")

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

$cred = Get-Credential -UserName "$env:COMPUTERNAME\$WorkerUser" -Message "Password of the $WorkerUser Windows user"
$Action = New-ScheduledTaskAction -Execute $Pythonw -Argument "-I `"$Launcher`" worker" -WorkingDirectory $Target
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 1) -RestartCount 999 `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -User $cred.UserName -Password $cred.GetNetworkCredential().Password -RunLevel Limited `
    -Description "Snafi: Ahmad's worker (REEMA), as $WorkerUser. Starts with Windows; restarts if it stops." -Force | Out-Null
Write-Host "Registered '$TaskName' to run as $WorkerUser. Start it now with: Start-ScheduledTask -TaskName '$TaskName'"
