#!/usr/bin/env python3
"""
测试MPV IPC功能
"""
import sys
import os
import time
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_ipc_implementation():
    """测试IPC功能实现"""
    print("=== 测试MPV IPC功能 ===")
    
    try:
        from src.player.mpv_controller import MpvController
        
        # 创建测试视频目录
        test_video_dir = project_root / "test_videos"
        test_video_dir.mkdir(exist_ok=True)
        
        # 创建一个简单的测试视频文件（如果不存在）
        test_video = test_video_dir / "test.mp4"
        if not test_video.exists():
            print(f"创建测试视频文件: {test_video}")
            # 这里可以添加创建测试视频文件的代码
            print("请手动添加一个测试视频文件到 test_videos/ 目录")
            return
        
        print(f"测试视频文件: {test_video}")
        
        # 测试MPV控制器初始化
        print("\n1. 测试MPV控制器初始化...")
        try:
            player = MpvController(str(test_video_dir), volume=50, loop=True)
            print("✓ MPV控制器初始化成功")
            
            # 等待播放器启动
            print("等待播放器启动...")
            time.sleep(5)
            
            # 测试IPC查询功能
            print("\n2. 测试IPC查询功能...")
            if hasattr(player, 'get_current_playing_file'):
                current_file = player.get_current_playing_file()
                print(f"✓ 当前播放文件: {current_file}")
            else:
                print("✗ get_current_playing_file 方法不存在")
            
            # 测试IPC状态查询
            if hasattr(player, 'query_mpv_status'):
                status = player.query_mpv_status()
                print(f"✓ MPV状态查询结果: {status}")
            else:
                print("✗ query_mpv_status 方法不存在")
            
            # 检查IPC查询定时器是否运行
            print("\n3. 检查IPC查询定时器...")
            if hasattr(player, 'ipc_query_timer') and player.ipc_query_timer:
                if player.ipc_query_timer.is_alive():
                    print("✓ IPC查询定时器正在运行")
                else:
                    print("✗ IPC查询定时器未运行")
            
            # 等待一段时间，让定时器有机会查询
            print("\n4. 等待10秒，让IPC定时器查询...")
            for i in range(10):
                time.sleep(1)
                print(f"  等待中... {i+1}/10 秒")
                
                # 检查是否有新的文件信息
                if hasattr(player, 'current_playing_file') and player.current_playing_file:
                    print(f"  当前播放文件 (通过IPC): {player.current_playing_file}")
            
            # 测试清理功能
            print("\n5. 测试清理功能...")
            player.cleanup()
            print("✓ 清理功能完成")
            
        except Exception as e:
            print(f"✗ MPV控制器测试失败: {e}")
            import traceback
            traceback.print_exc()
            
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        print("请确保项目依赖已正确安装")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_ipc_implementation()