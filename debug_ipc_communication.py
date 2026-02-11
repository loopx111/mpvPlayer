#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试IPC通信，打印详细的请求和响应信息
"""

import socket
import json
import sys
import os

def debug_ipc_communication():
    """调试IPC通信"""
    
    socket_path = "/tmp/mpv-socket"
    
    # 检查socket文件是否存在
    if not os.path.exists(socket_path):
        print(f"❌ Socket文件不存在: {socket_path}")
        print("请确保MPV播放器已启动并启用了IPC功能")
        return
    
    print(f"✅ Socket文件存在: {socket_path}")
    
    try:
        # 创建Unix域套接字
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)  # 5秒超时
        
        # 连接到socket
        sock.connect(socket_path)
        print("✅ IPC连接成功")
        
        # 测试1: 查询当前播放文件路径（与app中相同的命令）
        print("\n📝 测试1: 查询当前播放文件路径 (path属性)")
        cmd1 = {
            "command": ["get_property", "path"],
            "request_id": 1
        }
        cmd1_str = json.dumps(cmd1)
        print(f"发送命令: {cmd1_str}")
        sock.send(cmd1_str.encode() + b'\n')
        
        response1 = sock.recv(1024).decode()
        print(f"收到响应: {response1}")
        
        # 解析响应
        try:
            result1 = json.loads(response1)
            if "error" in result1:
                print(f"❌ path查询失败: {result1['error']}")
                
                # 测试2: 尝试使用media-title作为备用
                print("\n📝 测试2: 使用media-title作为备用")
                cmd2 = {
                    "command": ["get_property", "media-title"],
                    "request_id": 2
                }
                cmd2_str = json.dumps(cmd2)
                print(f"发送命令: {cmd2_str}")
                sock.send(cmd2_str.encode() + b'\n')
                
                response2 = sock.recv(1024).decode()
                print(f"收到响应: {response2}")
                result2 = json.loads(response2)
                
                if "error" not in result2:
                    print(f"✅ media-title查询成功: {result2.get('data', '')}")
                else:
                    print(f"❌ media-title查询也失败: {result2['error']}")
            else:
                print(f"✅ path查询成功: {result1.get('data', '')}")
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
        
        # 测试3: 查询播放列表位置
        print("\n📝 测试3: 查询播放列表位置")
        cmd3 = {
            "command": ["get_property", "playlist-pos"],
            "request_id": 3
        }
        cmd3_str = json.dumps(cmd3)
        print(f"发送命令: {cmd3_str}")
        sock.send(cmd3_str.encode() + b'\n')
        
        response3 = sock.recv(1024).decode()
        print(f"收到响应: {response3}")
        
        # 测试4: 查询播放时间
        print("\n📝 测试4: 查询播放时间")
        cmd4 = {
            "command": ["get_property", "time-pos"],
            "request_id": 4
        }
        cmd4_str = json.dumps(cmd4)
        print(f"发送命令: {cmd4_str}")
        sock.send(cmd4_str.encode() + b'\n')
        
        response4 = sock.recv(1024).decode()
        print(f"收到响应: {response4}")
        
        sock.close()
        print("\n✅ 调试完成")
        
    except Exception as e:
        print(f"❌ IPC通信失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_ipc_communication()