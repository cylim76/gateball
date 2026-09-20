@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Python was not found. Install Python 3 and select "Add Python to PATH".
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import serial" >nul 2>nul
if errorlevel 1 (
  echo Installing required package: pyserial
  %PYTHON_CMD% -m pip install --user pyserial
  if errorlevel 1 (
    echo Failed to install pyserial.
    pause
    exit /b 1
  )
)

%PYTHON_CMD% esp32_usb_range_test.py
if errorlevel 1 pause
