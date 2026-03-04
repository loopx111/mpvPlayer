#!/usr/bin/env python3
"""
摄像头诊断工具 - 全面检测摄像头状态
"""
import os
import subprocess
import cv2
import time

def check_device_files():
    """检查 /dev/video* 设备文件"""
    print("=== 检查摄像头设备文件 ===")
    
    video_devices = []
    for i in range(10):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            # 检查设备权限
            stat_info = os.stat(device_path)
            video_devices.append({
                'path': device_path,
                'exists': True,
                'permissions': oct(stat_info.st_mode)[-3:],
                'size': stat_info.st_size
            })
            print(f"✓ {device_path} 存在 (权限: {oct(stat_info.st_mode)[-3:]})")
        else:
            print(f"X {device_path} 不存在")
    
    return video_devices

def test_opencv_access():
    """测试OpenCV访问摄像头"""
    print("\n=== OpenCV摄像头访问测试 ===")
    
    results = []
    for i in range(5):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # 测试读取
                start_time = time.time()
                ret, frame = cap.read()
                read_time = time.time() - start_time
                
                if ret and frame is not None:
                    results.append({
                        'index': i,
                        'status': '可用',
                        'resolution': f"{frame.shape[1]}x{frame.shape[0]}",
                        'read_time': f"{read_time*1000:.1f}ms"
                    })
                    print(f"OK 摄像头 {i}: 可用 - {frame.shape[1]}x{frame.shape[0]} ({read_time*1000:.1f}ms)")
                else:
                    results.append({
                        'index': i,
                        'status': '可打开但无法读取',
                        'resolution': '未知',
                        'read_time': 'N/A'
                    })
                    print(f"⚠ 摄像头 {i}: 可打开但无法读取画面")
            else:
                results.append({
                    'index': i,
                    'status': '不可用',
                    'resolution': 'N/A',
                    'read_time': 'N/A'
                })
                print(f"✗ 摄像头 {i}: 不可用")
            
            cap.release()
            
        except Exception as e:
            results.append({
                'index': i,
                'status': f'错误: {str(e)}',
                'resolution': 'N/A',
                'read_time': 'N/A'
            })
            print(f"✗ 摄像头 {i}: 错误 - {e}")
    
    return results

def test_mpv_access(device_path):
    """测试MPV访问指定设备"""
    print(f"\n=== MPV访问测试: {device_path} ===")
    
    if not os.path.exists(device_path):
        print(f"✗ 设备文件不存在: {device_path}")
        return False
    
    try:
        # 测试MPV是否能打开设备
        cmd = [
            'mpv', device_path,
            '--demuxer-lavf-format=video4linux2',
            '--demuxer-lavf-o=video_size=640x480,input_format=mjpeg',
            '--no-audio',
            '--no-resume-playback',
            '--length=3'  # 只播放3秒
        ]
        
        print(f"执行命令: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ MPV访问成功")
            return True
        else:
            print(f"✗ MPV访问失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✓ MPV访问成功（超时表示一直在运行）")
        return True
    except Exception as e:
        print(f"✗ MPV访问错误: {e}")
        return False

def check_system_info():
    """检查系统摄像头相关信息"""
    print("\n=== 系统摄像头信息 ===")
    
    # 检查USB设备
    try:
        usb_result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if usb_result.returncode == 0:
            print("USB设备列表:")
            for line in usb_result.stdout.split('\n'):
                if 'camera' in line.lower() or 'video' in line.lower():
                    print(f"  📷 {line}")
    except:
        print("无法获取USB设备信息")
    
    # 检查内核模块
    try:
        modules_result = subprocess.run(['lsmod'], capture_output=True, text=True)
        if modules_result.returncode == 0:
            camera_modules = [
                'uvcvideo', 'videodev', 'v4l2_common', 
                'videobuf2', 'usbcore'
            ]
            print("相关内核模块:")
            for module in camera_modules:
                if module in modules_result.stdout:
                    print(f"  ✓ {module} 已加载")
                else:
                    print(f"  ✗ {module} 未加载")
    except:
        print("无法获取内核模块信息")

def main():
    """主诊断函数"""
    print("摄像头全面诊断工具")
    print("=" * 50)
    
    # 检查设备文件
    devices = check_device_files()
    
    # 检查系统信息
    check_system_info()
    
    # 测试OpenCV访问
    opencv_results = test_opencv_access()
    
    # 测试MPV访问（针对 /dev/video2）
    mpv_success = test_mpv_access('/dev/video2')
    
    # 输出诊断结果
    print("\n" + "=" * 50)
    print("诊断结果汇总:")
    print("=" * 50)
    
    # 分析OpenCV结果
    available_opencv = [r for r in opencv_results if r['status'] == '可用']
    print(f"OpenCV可用摄像头: {len(available_opencv)}个")
    
    # 分析MPV结果
    print(f"MPV访问 /dev/video2: {'✓ 成功' if mpv_success else '✗ 失败'}")
    
    # 给出建议
    print("\n建议:")
    if mpv_success and len(available_opencv) == 0:
        print("1. MPV能访问但OpenCV不能 → 可能是OpenCV参数配置问题")
        print("2. 尝试在OpenCV中指定后端: cv2.VideoCapture(2, cv2.CAP_V4L2)")
        print("3. 检查OpenCV版本和V4L2支持")
    elif mpv_success and len(available_opencv) > 0:
        print("1. 摄像头工作正常")
        print("2. 可以在项目中使用OpenCV索引 {}".format(", ".join([str(r['index']) for r in available_opencv])))
    else:
        print("1. 摄像头可能存在硬件或驱动问题")
        print("2. 建议重启系统或重新插拔摄像头")

if __name__ == "__main__":
    main()