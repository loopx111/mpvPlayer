#!/bin/bash

# 播放列表自动播放脚本
# 自动搜索视频文件并创建播放列表进行循环播放

# 设置环境变量（关键！）
export DISPLAY=${DISPLAY:-:0}
export QT_QPA_PLATFORM=xcb

# 项目目录和视频目录
PROJECT_DIR="/opt/mpvPlayer"
VIDEO_DIR="$PROJECT_DIR/data/videos"
PLAYLIST_FILE="$PROJECT_DIR/data/playlist.txt"

# 检查视频目录是否存在
if [ ! -d "$VIDEO_DIR" ]; then
    echo "错误: 视频目录不存在: $VIDEO_DIR"
    exit 1
fi

# 切换到项目目录
cd "$PROJECT_DIR"

# 激活虚拟环境（如果存在）
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 搜索视频文件并创建播放列表
echo "正在搜索视频文件..."
find "$VIDEO_DIR" -type f \( -name "*.mp4" -o -name "*.avi" -o -name "*.mkv" -o -name "*.mov" -o -name "*.wmv" \) | sort > "$PLAYLIST_FILE"

# 检查是否找到视频文件
VIDEO_COUNT=$(wc -l < "$PLAYLIST_FILE")
if [ $VIDEO_COUNT -eq 0 ]; then
    echo "错误: 在 $VIDEO_DIR 中没有找到视频文件"
    echo "支持格式: .mp4, .avi, .mkv, .mov, .wmv"
    exit 1
fi

echo "找到 $VIDEO_COUNT 个视频文件"
echo "播放列表已保存到: $PLAYLIST_FILE"
echo "播放列表内容:"
cat -n "$PLAYLIST_FILE"
echo ""

# 播放参数设置
VOLUME=70
FULLSCREEN="--fullscreen"
CURSOR_AUTOHIDE="--cursor-autohide=3000"
INPUT_BINDINGS="--input-default-bindings=yes"
LOOP_PLAYLIST="--loop-playlist=inf"
KEEP_OPEN="--keep-open=no"

# 构建mpv命令
MPV_CMD="mpv --playlist=$PLAYLIST_FILE $LOOP_PLAYLIST --volume=$VOLUME $KEEP_OPEN $FULLSCREEN $CURSOR_AUTOHIDE $INPUT_BINDINGS"

echo "开始播放..."
echo "命令: $MPV_CMD"
echo ""
echo "播放控制快捷键:"
echo "  空格键: 暂停/播放"
echo "  q: 退出播放"
echo "  f: 全屏切换"
echo "  ← →: 后退/前进5秒"
echo "  ↑ ↓: 增大/减小音量"
echo "  9/0: 减小/增大音量"
echo "  m: 静音切换"
echo "  p: 播放上一个视频"
echo "  n: 播放下一个视频"
echo ""

# 执行播放命令
eval "$MPV_CMD"

echo "播放结束"

# 清理播放列表文件（可选）
# rm "$PLAYLIST_FILE"