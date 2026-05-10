@echo off
chcp 65001 >nul
echo ========================================
echo    LingPet Nuitka Build
echo ========================================
echo.

cd /d "%~dp0"

:: ---------- Pre-check: Nuitka ----------
.venv\Scripts\python.exe -c "import nuitka" >nul 2>&1 || (
    echo [Install] Installing Nuitka...
    .venv\Scripts\pip.exe install nuitka ordered-set zstandard || (
        echo [Error] Failed to install Nuitka!
        pause
        exit /b 1
    )
)

:: ---------- Clean old build ----------
echo [1/4] Cleaning old build...
if exist run_DyberPet.build rd /s /q run_DyberPet.build
if exist run_DyberPet.dist rd /s /q run_DyberPet.dist
if exist dist rd /s /q dist

:: ---------- Build ----------
echo [2/4] Compiling with Nuitka (may take 10-30 min on first run)...
echo        Nuitka will auto-download MinGW64 if no C compiler is found.
echo.

.venv\Scripts\python.exe -m nuitka ^
    --standalone ^
    --mingw64 ^
    --enable-plugin=pyside6 ^
    --include-data-dir=res=res ^
    --include-module=pynput.mouse._win32 ^
    --include-module=pynput.keyboard._win32 ^
    --include-module=tendo.singleton ^
    --include-package=qfluentwidgets ^
    --include-package=qframelesswindow ^
    --include-package=apscheduler ^
    --nofollow-import-to=pkg_resources ^
    --nofollow-import-to=PySide6.QtWebEngine ^
    --nofollow-import-to=PySide6.QtPdf ^
    --windows-icon-from-ico=res\icons\arrow-204-32.ico ^
    --windows-disable-console ^
    --output-filename=LingPet.exe ^
    --output-dir=. ^
    --show-progress ^
    --assume-yes-for-downloads ^
    run_DyberPet.py

if errorlevel 1 (
    echo.
    echo [Error] Build failed! Check the errors above.
    pause
    exit /b 1
)

:: ---------- Move output ----------
echo.
echo [3/4] Organizing output...
mkdir dist 2>nul
move "run_DyberPet.dist" "dist\LingPet" >nul

:: ---------- Done ----------
echo.
echo [4/4] Build complete!
echo Output: dist\LingPet\LingPet.exe
for %%A in ("dist\LingPet\LingPet.exe") do echo Size: %%~zA bytes
echo.
echo You can zip the dist\LingPet folder for distribution.

echo Cleaning build temp files...
if exist run_DyberPet.build rd /s /q run_DyberPet.build 2>nul

echo Done.
pause
