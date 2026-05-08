@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 播放列表自动播放脚本 - Windows版本
:: 自动搜索视频文件并创建播放列表进行循环播放

:: 项目目录和视频目录
set "PROJECT_DIR=%~dp0.."
set "VIDEO_DIR=%PROJECT_DIR%\data\videos"
set "PLAYLIST_FILE=%PROJECT_DIR%\data\playlist.txt"

:: 检查视频目录是否存在
if not exist "%VIDEO_DIR%" (
    echo 错误: 视频目录不存在: %VIDEO_DIR%
    pause
    exit /b 1
)

:: 切换到项目目录
cd /d "%PROJECT_DIR%"

:: 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: 搜索视频文件并创建播放列表
echo 正在搜索视频文件...
del "%PLAYLIST_FILE%" 2>nul

:: 使用dir命令搜索所有视频文件并保存到播放列表
(for /f "delims=" %%f in ('dir /b /s "%VIDEO_DIR%\*.mp4" "%VIDEO_DIR%\*.avi" "%VIDEO_DIR%\*.mkv" "%VIDEO_DIR%\*.mov" "%VIDEO_DIR%\*.wmv" 2^>nul') do (
    echo %%f
)) > "%PLAYLIST_FILE%"

:: 检查是否找到视频文件
set /a VIDEO_COUNT=0
for /f "usebackq delims=" %%i in ("%PLAYLIST_FILE%") do set /a VIDEO_COUNT+=1

if %VIDEO_COUNT% equ 0 (
    echo 错误: 在 %VIDEO_DIR% 中没有找到视频文件
    echo 支持格式: .mp4, .avi, .mkv, .mov, .wmv
    pause
    exit /b 1
)

echo 找到 %VIDEO_COUNT% 个视频文件
echo 播放列表已保存到: %PLAYLIST_FILE%
echo 播放列表内容:
type "%PLAYLIST_FILE%"
echo.

:: 播放参数设置
set "VOLUME=70"
set "FULLSCREEN=--fullscreen"
set "CURSOR_AUTOHIDE=--cursor-autohide=3000"
set "INPUT_BINDINGS=--input-default-bindings=yes"
set "LOOP_PLAYLIST=--loop-playlist=inf"
set "KEEP_OPEN=--keep-open=no"

:: 构建mpv命令
set "MPV_CMD=mpv --playlist=%PLAYLIST_FILE% %LOOP_PLAYLIST% --volume=%VOLUME% %KEEP_OPEN% %FULLSCREEN% %CURSOR_AUTOHIDE% %INPUT_BINDINGS%"

echo 开始播放...
echo 命令: %MPV_CMD%
echo.
echo 播放控制快捷键:
echo   空格键: 暂停/播放
echo   q: 退出播放
echo   f: 全屏切换
echo   ← →: 后退/前进5秒
echo   ↑ ↓: 增大/减小音量
echo   9/0: 减小/增大音量
echo   m: 静音切换
echo   p: 播放上一个视频
echo   n: 播放下一个视频
echo.

:: 执行播放命令
%MPV_CMD%

echo 播放结束

:: 清理播放列表文件（可选）
:: del "%PLAYLIST_FILE%"

pause