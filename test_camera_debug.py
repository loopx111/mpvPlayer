#!/usr/bin/env python3
"""
摄像头调试工具 - 单独测试摄像头功能
"""
import cv2
import sys
import time

def list_available_cameras():
    """列出所有可用的摄像头设备"""
    print("=== 摄像头设备检测 ===")
    available_cameras = []
    
    # 检查前10个摄像头索引
    for i in range(10):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # 尝试读取一帧验证
                ret, frame = cap.read()
                if ret and frame is not None:
                    available_cameras.append(i)
                    print(f"✓ 摄像头 {i} 可用 - 分辨率: {frame.shape[1]}x{frame.shape[0]}")
                else:
                    print(f"✗ 摄像头 {i} 可打开但无法读取画面")
            else:
                print(f"✗ 摄像头 {i} 不可用")
            cap.release()
        except Exception as e:
            print(f"✗ 检测摄像头 {i} 时出错: {e}")
    
    print(f"\n总计找到 {len(available_cameras)} 个可用摄像头: {available_cameras}")
    return available_cameras

def test_camera_parameters(camera_index):
    """测试摄像头参数"""
    print(f"\n=== 测试摄像头 {camera_index} 参数 ===")
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"无法打开摄像头 {camera_index}")
        return
    
    # 获取默认参数
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"默认分辨率: {width}x{height}")
    print(f"默认帧率: {fps}")
    
    # 测试设置不同分辨率
    resolutions = [(640, 480), (1280, 720), (1920, 1080)]
    for res in resolutions:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, res[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, res[1])
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"尝试设置 {res[0]}x{res[1]} -> 实际: {actual_width}x{actual_height}")
    
    cap.release()

def preview_camera(camera_index, duration=10):
    """预览摄像头画面"""
    print(f"\n=== 预览摄像头 {camera_index} (持续 {duration} 秒) ===")
    
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"无法打开摄像头 {camera_index}")
        return
    
    # 设置参数
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    start_time = time.time()
    frame_count = 0
    
    print("按 'q' 键退出预览，按 's' 键保存当前帧")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("无法读取摄像头画面")
            break
        
        frame_count += 1
        
        # 显示画面
        cv2.imshow(f'Camera {camera_index} Preview', frame)
        
        # 计算并显示帧率
        elapsed = time.time() - start_time
        fps = frame_count / elapsed if elapsed > 0 else 0
        cv2.putText(frame, f'FPS: {fps:.1f}', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 按键处理
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            # 保存当前帧
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"camera_{camera_index}_{timestamp}.jpg"
            cv2.imwrite(filename, frame)
            print(f"截图已保存: {filename}")
        
        # 超时退出
        if time.time() - start_time > duration:
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    actual_fps = frame_count / (time.time() - start_time) if (time.time() - start_time) > 0 else 0
    print(f"实际帧率: {actual_fps:.1f} FPS")

def test_backends(camera_index):
    """测试不同的OpenCV后端"""
    print(f"\n=== 测试摄像头 {camera_index} 不同后端 ===")
    
    backends = [
        (cv2.CAP_V4L2, "V4L2"),
        (cv2.CAP_ANY, "ANY"),
        (cv2.CAP_FFMPEG, "FFMPEG"),
        (cv2.CAP_GSTREAMER, "GSTREAMER")
    ]
    
    for backend, name in backends:
        try:
            cap = cv2.VideoCapture(camera_index, backend)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    print(f"✓ {name} 后端: 可用 - 分辨率: {frame.shape[1]}x{frame.shape[0]}")
                else:
                    print(f"✗ {name} 后端: 可打开但无法读取")
            else:
                print(f"✗ {name} 后端: 不可用")
            cap.release()
        except Exception as e:
            print(f"✗ {name} 后端: 错误 - {e}")

def main():
    """主函数"""
    print("摄像头调试工具")
    print("=" * 50)
    
    # 检测可用摄像头
    cameras = list_available_cameras()
    
    if not cameras:
        print("未找到可用摄像头，退出")
        return
    
    # 选择要测试的摄像头
    if len(cameras) == 1:
        camera_index = cameras[0]
    else:
        print(f"\n请选择要测试的摄像头索引 ({cameras}): ", end="")
        try:
            camera_index = int(input().strip())
            if camera_index not in cameras:
                print(f"无效的摄像头索引，使用默认 {cameras[0]}")
                camera_index = cameras[0]
        except:
            camera_index = cameras[0]
            print(f"输入无效，使用默认 {camera_index}")
    
    # 测试参数
    test_camera_parameters(camera_index)
    
    # 测试后端
    test_backends(camera_index)
    
    # 预览
    print(f"\n是否预览摄像头 {camera_index}? (y/n): ", end="")
    if input().strip().lower() == 'y':
        preview_camera(camera_index)
    
    print("\n调试完成!")

if __name__ == "__main__":
    main()