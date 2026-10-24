@echo off
setlocal
cd /d "%~dp0"
set "KKA_TEST_MODE=1"
if not exist logs mkdir logs

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$root=(Resolve-Path '.').Path; $python=Join-Path $root '.venv\Scripts\python.exe'; if (-not (Test-Path $python)) { throw 'Virtual environment missing. Follow RUNBOOK.md first.' }; $daily=Start-Process -FilePath $python -ArgumentList 'daily_update.py' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'logs\daily_update.log') -RedirectStandardError (Join-Path $root 'logs\daily_update.err.log'); $web=Start-Process -FilePath $python -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'logs\website.log') -RedirectStandardError (Join-Path $root 'logs\website.err.log'); Write-Output ('Daily updater PID: ' + $daily.Id); Write-Output ('Website PID: ' + $web.Id); $ready=$false; for ($i=0; $i -lt 20; $i++) { Start-Sleep -Seconds 1; try { $health=Invoke-RestMethod 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; if ($health.status -eq 'ok') { $ready=$true; break } } catch {} }; if (-not $ready) { throw 'Website readiness check failed; inspect logs\website.err.log' }; Write-Output 'Website is ready at http://127.0.0.1:8000'; Write-Output 'Logs: logs\daily_update.log and logs\website.log'"
if errorlevel 1 exit /b 1
endlocal
