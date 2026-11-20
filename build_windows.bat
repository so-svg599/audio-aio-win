@echo off
setlocal
py -m pip install -r requirements.txt pyinstaller
py -m PyInstaller --noconfirm AudioPlayerAIO.spec
if errorlevel 1 exit /b 1
echo Build fini : dist\AudioPlayerAIO\AudioPlayerAIO.exe
