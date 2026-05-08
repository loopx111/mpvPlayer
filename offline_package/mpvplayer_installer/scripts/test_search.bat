@echo off
chcp 65001 >nul

set "VIDEO_DIR=D:\code\mpvPlayer\data\videos"
set "PLAYLIST_FILE=D:\code\mpvPlayer\data\playlist.txt"

echo 测试视频文件搜索...
echo 视频目录: %VIDEO_DIR%
echo.

:: 检查目录是否存在
if not exist "%VIDEO_DIR%" (
    echo 错误: 视频目录不存在
    pause
    exit /b 1
)

:: 列出目录内容
echo 目录内容:
dir "%VIDEO_DIR%"
echo.

:: 测试搜索方法1: 使用for循环
echo 方法1 - 使用for循环搜索:
(for %%f in ("%VIDEO_DIR%\*.mp4" "%VIDEO_DIR%\*.avi" "%VIDEO_DIR%\*.mkv" "%VIDEO_DIR%\*.mov" "%VIDEO_DIR%\*.wmv") do (
    echo 找到: %%~ff
))

:: 测试搜索方法2: 使用dir和findstr
echo.
echo 方法2 - 使用dir和findstr搜索:
dir "%VIDEO_DIR%" /b | findstr /i ".mp4 .avi .mkv .mov .wmv"

pause