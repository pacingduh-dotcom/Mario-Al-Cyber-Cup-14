@echo off
REM Reproducible Windows build for MARIO AL CYBER CUP 14.  Requires Python 3.10+ (64-bit) on PATH.
setlocal
cd /d "%~dp0"
if not exist .venv python -m venv .venv || goto :fail
call .venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt || goto :fail
python tests\test_logic.py || goto :fail
python tests\smoke_real_pygame.py || goto :fail
pyinstaller --noconfirm --clean --onefile --windowed --noupx --name MarioAlCyberCup14 --exclude-module tkinter --exclude-module unittest --exclude-module pydoc main.py || goto :fail
echo.
echo BUILD OK:  %CD%\dist\MarioAlCyberCup14.exe
exit /b 0
:fail
echo BUILD FAILED
exit /b 1
