@echo off
REM MPV Player 虚拟环境设置脚本

REM 设置脚本目录为当前目录
cd /d "%~dp0"

echo 正在设置MPV Player虚拟环境...

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python 未安装或不在 PATH 中
    echo 请先安装Python 3.8或更高版本
    pause
    exit /b 1
)

echo Python版本检查通过

REM 检查是否已存在虚拟环境
if exist "venv" (
    echo 虚拟环境已存在，跳过创建
    goto :install_deps
)

REM 创建虚拟环境
echo 正在创建虚拟环境...
python -m venv venv
if errorlevel 1 (
    echo 错误: 虚拟环境创建失败
    pause
    exit /b 1
)

echo 虚拟环境创建成功

:install_deps
REM 激活虚拟环境并安装依赖
echo 正在激活虚拟环境...
call venv\Scripts\activate.bat

echo 正在安装依赖包...
pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo 错误: 依赖安装失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo 虚拟环境设置完成！
echo.
echo 使用方法：
echo 1. 直接运行 start_windows.bat 启动应用
echo 2. 或手动激活环境：
echo     在命令行中运行: venv\Scripts\activate.bat
echo     然后运行: python -m src.app
echo ============================================

pause