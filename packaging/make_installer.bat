@echo off
REM 构建 CodePal 安装包
REM 1) 先生成单文件可执行程序
python packaging\build_windows.py
IF ERRORLEVEL 1 (echo 构建失败 & pause & exit /b 1)

REM 2) 若本机安装了 Inno Setup，则打包成正式安装程序；否则保留便携版
WHERE iscc >nul 2>nul
IF %ERRORLEVEL%==0 (
    iscc packaging\installer.iss
    echo 已生成 release\CodePal-Setup.exe
) ELSE (
    echo 未检测到 Inno Setup（iscc），已保留便携版 dist\CodePal.exe
    echo 如需正式安装程序，请安装 Inno Setup 后再次运行本脚本。
)
pause
