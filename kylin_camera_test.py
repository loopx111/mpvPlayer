#!/usr/bin/env python3
"""
麒麟系统专用摄像头测试工具
针对麒麟系统的特殊摄像头配置进行优化
"""
import cv2
import os
import sys
import time

def check_system_environment():
    """检查系统环境"""
    print("=== 系统环境检查 ===")
    
    # 检查操作系统
    if os.name == 'posix':
        print("✓ 运行在Linux系统上")
        
        # 检查设备文件
        for i in range(10):
            dev_path = f"/dev/video{i}"
            if os.path.exists(dev_path):
                print(f"✓ 发现设备文件: {dev_path}")
                
        # 检查V4L2支持
        try:
            import subprocess
            result = subprocess.run(['v4l2-ctl', '--list-devices'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✓ V4L2工具可用")
                for line in result.stdout.split('\n'):
                    if '/dev/video' in line:
                        print(f"  - {line.strip()}")
            else:
                print("✗ V4L2工具不可用")
        except:
            print("✗ 无法检查V4L2工具")
    else:
        print("✗ 非Linux系统，可能无法使用V4L2")

def test_camera_with_v4l2():
    """专门测试V4L2摄像头访问"""
    print("\n=== V4L2摄像头测试 ===")
    
    # 优先使用V4L2后端
    available_cameras = []
    
    for i in range(5):
        print(f"\n测试摄像头 {i}:")
        
        # 尝试V4L2后端
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                print("  ✓ V4L2后端: 摄像头可打开")
                
                # 测试读取
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"  ✓ 成功读取画面: {frame.shape[1]}x{frame.shape[0]}")
                    available_cameras.append({
                        'index': i,
                        'backend': 'V4L2',
                        'resolution': f"{frame.shape[1]}x{frame.shape[0]}"
                    })
                else:
                    print("  ✗ 无法读取画面")
                
                cap.release()
            else:
                print("  ✗ V4L2后端: 无法打开摄像头")
        except Exception as e:
            print(f"  ✗ V4L2后端错误: {e}")
        
        # 如果V4L2失败，尝试其他后端
        if i not in [cam['index'] for cam in available_cameras]:
            for backend, name in [(cv2.CAP_ANY, 'ANY'), (cv2.CAP_FFMPEG, 'FFMPEG')]:
                try:
                    cap = cv2.VideoCapture(i, backend)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            print(f"  ✓ {name}后端: 可用 - {frame.shape[1]}x{frame.shape[0]}")
                            available_cameras.append({
                                'index': i,
                                'backend': name,
                                'resolution': f"{frame.shape[1]}x{frame.shape[0]}"
                            })
                            cap.release()
                            break
                        cap.release()
                except:
                    pass
    
    return available_cameras

def test_camera_parameters():
    """测试摄像头参数设置"""
    print("\n=== 摄像头参数测试 ===")
    
    # 测试不同的参数组合
    resolutions = [
        (640, 480),   # VGA
        (1280, 720),  # HD
        (1920, 1080)  # Full HD
    ]
    
    formats = [
        ('MJPG', cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG')),
        ('YUYV', cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'YUYV')),
    ]
    
    for i in range(2):  # 只测试前2个摄像头
        print(f"\n测试摄像头 {i} 参数:")
        
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if not cap.isOpened():
                continue
            
            for res in resolutions:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
                
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if actual_w == res[0] and actual_h == res[1]:
                    print(f"  ✓ 分辨率 {res[0]}x{res[1]}: 支持")
                else:
                    print(f"  ✗ 分辨率 {res[0]}x{res[1]}: 实际 {actual_w}x{actual_h}")
            
            cap.release()
        except:
            pass

def preview_camera(camera_index, backend=cv2.CAP_V4L2):
    """预览摄像头画面"""
    print(f"\n=== 预览摄像头 {camera_index} ===")
    
    try:
        cap = cv2.VideoCapture(camera_index, backend)
        if not cap.isOpened():
            print("无法打开摄像头")
            return
        
        # 设置参数
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        print("按 'q' 键退出预览")
        
        start_time = time.time()
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # 显示帧率
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            
            cv2.putText(frame, f'FPS: {fps:.1f}', (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f'Camera: {camera_index}', (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow(f'Kylin Camera Test - {camera_index}', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        print(f"平均帧率: {fps:.1f} FPS")
        
    except Exception as e:
        print(f"预览失败: {e}")

def main():
    """主函数"""
    print("麒麟系统摄像头测试工具")
    print("=" * 60)
    
    # 检查系统环境
    check_system_environment()
    
    # 测试摄像头
    available_cameras = test_camera_with_v4l2()
    
    # 测试参数
    test_camera_parameters()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    if available_cameras:
        print(f"找到 {len(available_cameras)} 个可用摄像头:")
        for cam in available_cameras:
            print(f"  - 摄像头 {cam['index']}: {cam['backend']}后端, {cam['resolution']}")
        
        # 询问是否预览
        print("\n是否预览摄像头? (输入摄像头索引或 'n' 退出): ")
        try:
            user_input = input().strip()
            if user_input.lower() != 'n':
                camera_index = int(user_input)
                if camera_index in [cam['index'] for cam in available_cameras]:
                    preview_camera(camera_index)
        except:
            pass
    else:
        print("未找到可用摄像头")
        print("\n建议:")
        print("1. 检查摄像头驱动是否安装")
        print("2. 检查摄像头设备权限")
        print("3. 尝试重启系统")
        print("4. 检查V4L2支持")
    
    print("\n测试完成!")

if __name__ == "__main__":
    main()