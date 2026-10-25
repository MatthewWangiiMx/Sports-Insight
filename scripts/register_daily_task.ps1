# Creates (or updates) a Windows scheduled task that runs daily_update.ps1
# every morning. Run once; re-run to change the time:
#     .\scripts\register_daily_task.ps1 -At 9:30am
# Remove it with:
#     Unregister-ScheduledTask -TaskName 'Sports Insight daily update'

param(
    # After the previous night's games are final (late games end ~1am ET).
    [string]$At = '8:00am'
)

$script = Join-Path $PSScriptRoot 'daily_update.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
# -StartWhenAvailable: if the PC was off/asleep at that time, run at the next chance instead of skipping the day.

Register-ScheduledTask -TaskName 'Sports Insight daily update' `
    -Description 'Pulls the current NBA season from stats.nba.com into data/raw/nba and Supabase.' `
    -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Scheduled 'Sports Insight daily update' daily at $At."
