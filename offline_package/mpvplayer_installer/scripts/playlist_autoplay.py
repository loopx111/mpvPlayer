#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
播放列表自动播放脚本 - Python版本
自动搜索视频文件并创建播放列表进行循环播放
"""

import os
import sys
import glob
import subprocess
import platform
from pathlib import Path

class PlaylistAutoPlayer:
    def __init__(self):
        # 项目目录和视频目录
        self.project_dir = Path("/opt/mpvPlayer")
        self.video_dir = self.project_dir / "data" / "videos"
        self.playlist_file = self.project_dir / "data" / "playlist.txt"
        
        # 支持的视频格式
        self.supported_formats = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
        # 播放参数
        self.volume = 70
        self.fullscreen = True
        self.cursor_autohide = 3000
        self.loop_playlist = True
        
    def find_video_files(self):
        """搜索视频文件"""
        video_files = []
        
        # 检查视频目录是否存在
        if not self.video_dir.exists():
            print(f"错误: 视频目录不存在: {self.video_dir}")
            return []
        
        # 搜索所有支持格式的视频文件
        for ext in self.supported_formats:
            pattern = str(self.video_dir / f"**/*{ext}")
            video_files.extend(glob.glob(pattern, recursive=True))
        
        # 按文件名排序
        video_files.sort()
        return video_files
    
    def create_playlist(self, video_files):
        """创建播放列表文件"""
        try:
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                for video_file in video_files:
                    f.write(video_file + '\n')
            return True
        except Exception as e:
            print(f"创建播放列表文件失败: {e}")
            return False
    
    def build_mpv_command(self):
        """构建mpv播放命令"""
        cmd = [
            "mpv",
            f"--playlist={self.playlist_file}",
            "--loop-playlist=inf" if self.loop_playlist else "",
            f"--volume={self.volume}",
            "--keep-open=no",
            "--fullscreen" if self.fullscreen else "",
            f"--cursor-autohide={self.cursor_autohide}",
            "--input-default-bindings=yes",
            "--no-terminal"
        ]
        
        # 过滤空字符串
        cmd = [arg for arg in cmd if arg]
        return cmd
    
    def print_help(self):
        """打印帮助信息"""
        print("\n播放控制快捷键:")
        print("  空格键: 暂停/播放")
        print("  q: 退出播放")
        print("  f: 全屏切换")
        print("  ← →: 后退/前进5秒")
        print("  ↑ ↓: 增大/减小音量")
        print("  9/0: 减小/增大音量")
        print("  m: 静音切换")
        print("  p: 播放上一个视频")
        print("  n: 播放下一个视频")
        print("")
    
    def setup_environment(self):
        """设置环境变量（麒麟系统专用）"""
        if platform.system().lower() == "linux":
            # 设置显示环境变量
            os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':0')
            # 设置Qt平台为XCB（关键！）
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
    
    def run(self):
        """运行播放器"""
        print("=== 播放列表自动播放器 ===")
        
        # 设置环境变量
        self.setup_environment()
        
        # 搜索视频文件
        print("正在搜索视频文件...")
        video_files = self.find_video_files()
        
        if not video_files:
            print(f"错误: 在 {self.video_dir} 中没有找到视频文件")
            print(f"支持格式: {', '.join(self.supported_formats)}")
            return False
        
        print(f"找到 {len(video_files)} 个视频文件")
        
        # 创建播放列表
        if not self.create_playlist(video_files):
            return False
        
        print(f"播放列表已保存到: {self.playlist_file}")
        print("播放列表内容:")
        for i, video_file in enumerate(video_files, 1):
            print(f"  {i:2d}. {os.path.basename(video_file)}")
        
        # 构建播放命令
        mpv_cmd = self.build_mpv_command()
        print(f"\n开始播放...")
        print(f"命令: {' '.join(mpv_cmd)}")
        
        # 打印帮助信息
        self.print_help()
        
        try:
            # 执行播放命令
            subprocess.run(mpv_cmd, check=True)
            print("播放结束")
            return True
        except subprocess.CalledProcessError as e:
            print(f"播放过程中出现错误: {e}")
            return False
        except KeyboardInterrupt:
            print("\n用户中断播放")
            return True
        except FileNotFoundError:
            print("错误: 找不到mpv命令，请确保mpv已安装")
            return False

def main():
    """主函数"""
    player = PlaylistAutoPlayer()
    
    # 如果提供了命令行参数，可以调整设置
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("用法: python playlist_autoplay.py [选项]")
            print("选项:")
            print("  --help, -h     显示帮助信息")
            print("  --volume=N     设置音量 (0-100)")
            print("  --no-fullscreen 非全屏播放")
            print("  --no-loop      不循环播放")
            return
        
        # 处理其他参数
        for arg in sys.argv[1:]:
            if arg.startswith("--volume=") and arg[9:].isdigit():
                player.volume = int(arg[9:])
            elif arg == "--no-fullscreen":
                player.fullscreen = False
            elif arg == "--no-loop":
                player.loop_playlist = False
    
    # 运行播放器
    success = player.run()
    
    # 清理播放列表文件（可选）
    # if player.playlist_file.exists():
    #     player.playlist_file.unlink()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()