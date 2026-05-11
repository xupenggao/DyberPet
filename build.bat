@echo off
chcp 65001 >nul
echo ========================================
echo    爪爪宠物 一键打包
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 清理旧构建...
if exist build rd /s /q build
if exist dist  rd /s /q dist

echo [2/3] 开始打包，请稍候...
.venv\Scripts\pyinstaller.exe --noconfirm "爪爪宠物.spec"

if %errorlevel% neq 0 (
    echo.
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 打包完成！
echo 输出文件: dist\爪爪宠物.exe
for %%A in ("dist\爪爪宠物.exe") do echo 文件大小: %%~zA 字节
echo.
pause
