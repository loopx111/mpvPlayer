@echo off
echo 正在安装MPV播放器依赖...

:: 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

:: 安装基础依赖
echo 安装基础依赖包...
pip install -r requirements.txt

if errorlevel 1 (
    echo 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)

echo.
echo 依赖安装完成！
echo 现在可以运行测试脚本: python test_camera.py
echo 或运行主程序: python src/app.py
pause