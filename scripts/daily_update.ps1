# Runs the daily NBA data update (ml/ingest/update.py) and appends its output
# to logs/daily_update.log. Called by the scheduled task that
# register_daily_task.ps1 creates; safe to run by hand too.

$repo = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repo 'logs'
$log = Join-Path $logDir 'daily_update.log'
New-Item -ItemType Directory -Force $logDir | Out-Null

# Keep the log from growing forever: start fresh once it passes 1 MB.
if ((Test-Path $log) -and (Get-Item $log).Length -gt 1MB) {
    Move-Item $log "$log.old" -Force
}

# UTF-8 so player names like "Doncic" with accents don't break logging.
$env:PYTHONUTF8 = '1'
$python = Join-Path $repo 'ml\.venv\Scripts\python.exe'

Push-Location (Join-Path $repo 'ml')
try {
    Add-Content $log "==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===="
    # cmd handles the redirect: PowerShell 5.1 would wrap Python's stderr lines
    # in error records instead of writing them plainly.
    cmd /c "`"$python`" -m ingest.update >> `"$log`" 2>&1"
    Add-Content $log "exit code $LASTEXITCODE`r`n"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
