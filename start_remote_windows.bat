@echo off
REM MPV Player Windows 远程环境优化启动脚本
REM 针对远程桌面环境优化，避免连接断开问题

REM 设置脚本目录为当前目录
cd /d "%~dp0"

REM 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo 检测到虚拟环境，正在激活...
    call venv\Scripts\activate.bat
    echo 虚拟环境已激活
) else if exist ".venv\Scripts\activate.bat" (
    echo 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
    echo 虚拟环境已激活
) else (
    echo 未检测到虚拟环境，使用系统Python
)

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: Python 未安装或不在 PATH 中
    echo 请确保Python已正确安装或虚拟环境已配置
    pause
    exit /b 1
)

REM 检查PySide6依赖
python -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    echo 错误: PySide6 未安装
    echo 正在尝试安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo 依赖安装失败，请手动运行: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo 依赖安装成功
)

REM 创建必要的目录
if not exist "data\downloads" mkdir "data\downloads"
if not exist "data\videos" mkdir "data\videos"
if not exist "data\logs" mkdir "data\logs"

REM 设置远程环境标志（通过环境变量传递）
echo 设置远程环境优化模式...
set MPV_REMOTE_MODE=true

REM 启动应用（远程优化模式）
echo 启动 MPV Player (远程优化模式)...
echo 注意: 此模式使用低资源占用的MPV参数，避免远程连接断开
python -m src.app --remote-mode

echo 应用已退出
pause