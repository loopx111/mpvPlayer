#!/usr/bin/env python3
"""
简单摄像头测试 - 验证当前摄像头状态
"""
import cv2
import time

def test_camera_opencv():
    """测试OpenCV摄像头访问"""
    print("=== OpenCV摄像头测试 ===")
    
    for i in range(5):
        try:
            print(f"\n测试摄像头 {i}:")
            cap = cv2.VideoCapture(i)
            
            if cap.isOpened():
                print(f"  - 可以打开摄像头 {i}")
                
                # 尝试读取几帧
                success_count = 0
                for j in range(10):
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        success_count += 1
                        if j == 0:  # 只在第一帧显示分辨率
                            print(f"  - 分辨率: {frame.shape[1]}x{frame.shape[0]}")
                    else:
                        break
                
                if success_count > 0:
                    print(f"  - 成功读取 {success_count}/10 帧")
                else:
                    print(f"  - 无法读取画面")
                
                # 测试不同后端
                backends = [
                    (cv2.CAP_ANY, "默认"),
                    (cv2.CAP_V4L2, "V4L2"),
                    (cv2.CAP_FFMPEG, "FFMPEG")
                ]
                
                for backend, name in backends:
                    try:
                        cap_backend = cv2.VideoCapture(i, backend)
                        if cap_backend.isOpened():
                            ret, frame = cap_backend.read()
                            if ret:
                                print(f"  - {name}后端: 可用")
                            else:
                                print(f"  - {name}后端: 可打开但无法读取")
                        cap_backend.release()
                    except:
                        print(f"  - {name}后端: 错误")
                        
            else:
                print(f"  - 无法打开摄像头 {i}")
                
            cap.release()
            
        except Exception as e:
            print(f"  - 测试摄像头 {i} 时出错: {e}")

def test_specific_device():
    """测试特定设备文件"""
    print("\n=== 设备文件测试 ===")
    
    # 在Windows下测试设备文件
    for i in range(5):
        try:
            # 在Windows下使用索引方式
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"摄像头 {i}: 可用")
                
                # 显示预览
                print("显示预览 (按 'q' 退出)...")
                while True:
                    ret, frame = cap.read()
                    if ret:
                        cv2.imshow(f'Camera {i}', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    else:
                        break
                cv2.destroyAllWindows()
                break
            else:
                print(f"摄像头 {i}: 不可用")
                
            cap.release()
        except Exception as e:
            print(f"摄像头 {i} 测试错误: {e}")

def main():
    """主函数"""
    print("摄像头状态测试")
    print("=" * 50)
    
    # 测试OpenCV访问
    test_camera_opencv()
    
    # 测试设备文件
    test_specific_device()
    
    print("\n测试完成!")
    print("\n建议:")
    print("1. 如果MPV能访问但OpenCV不能 → 检查OpenCV参数和后端")
    print("2. 尝试在代码中指定后端: cv2.VideoCapture(2, cv2.CAP_V4L2)")
    print("3. 检查摄像头权限和驱动状态")

if __name__ == "__main__":
    main()