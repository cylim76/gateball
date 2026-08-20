@echo off
setlocal

cd /d "%~dp0"

echo Cleaning old Gateball web server processes...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo Stopping process on port 8000: %%P
  taskkill /PID %%P /F >nul 2>nul
)

for /f "skip=1 tokens=2 delims=," %%P in ('wmic process where "CommandLine like '%%web/server.py%%' or CommandLine like '%%web\\server.py%%'" get ProcessId /format:csv 2^>nul') do (
  if not "%%P"=="" (
    echo Stopping old web/server.py process: %%P
    taskkill /PID %%P /F >nul 2>nul
  )
)

echo Starting Gateball web server...
echo Scoreboard: http://127.0.0.1:8000/scoreboard
echo Remote:     http://127.0.0.1:8000/remote
echo Settings:   http://127.0.0.1:8000/set
echo.
echo Opening scoreboard in full-screen browser...
start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url='http://127.0.0.1:8000/scoreboard'; for ($i=0; $i -lt 30; $i++) { try { Invoke-WebRequest 'http://127.0.0.1:8000/api/state' -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }; $browsers=@($env:ProgramFiles+'\Microsoft\Edge\Application\msedge.exe', ${env:ProgramFiles(x86)}+'\Microsoft\Edge\Application\msedge.exe', $env:ProgramFiles+'\Google\Chrome\Application\chrome.exe', ${env:ProgramFiles(x86)}+'\Google\Chrome\Application\chrome.exe'); foreach ($browser in $browsers) { if (Test-Path $browser) { Start-Process $browser -ArgumentList @('--start-fullscreen','--new-window',$url); exit } }; Start-Process $url"
echo.
echo Press Ctrl+C to stop.
echo.

python web\server.py
