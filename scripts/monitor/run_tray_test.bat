@echo off
cd /d "%~dp0..\.."
echo Running tray test from: %CD%
echo Using: vendors\python\pythonw.exe
start "" "vendors\python\pythonw.exe" "scripts\monitor\tray_test_minimal.py"
echo Tray started. Check taskbar. Right-click icon and select Exit to quit.
pause
