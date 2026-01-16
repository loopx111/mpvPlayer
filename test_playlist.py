#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试播放列表功能的脚本
"""

import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.player.mpv_controller import MpvController
import time

def test_playlist():
    """测试播放列表功能"""
    
    # 测试视频目录（根据你的实际路径修改）
    video_path = r"d:\code\mpvPlayer\data\videos"
    
    if not os.path.exists(video_path):
        print(f"错误: 视频目录不存在: {video_path}")
        return
    
    print(f"测试播放列表功能")
    print(f"视频目录: {video_path}")
    
    # 创建播放器实例
    player = MpvController(video_path, volume=70, loop=True)
    
    print("播放器已创建，等待5秒后自动清理...")
    
    # 等待5秒
    time.sleep(5)
    
    # 清理资源
    player.cleanup()
    print("测试完成")

if __name__ == "__main__":
    test_playlist()