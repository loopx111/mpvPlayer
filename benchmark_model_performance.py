#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import onnxruntime as ort
import cv2
import time
import numpy as np

def benchmark_model(model_path):
    """基准测试模型性能"""
    print(f"[测试] 测试模型: {model_path}")
    
    # 检查可用provider
    available_providers = ort.get_available_providers()
    print(f"[可用] 可用推理引擎: {available_providers}")
    
    # 尝试不同的provider
    providers_to_test = []
    
    # 优先级：GPU > CPU优化 > 默认CPU
    if 'CUDAExecutionProvider' in available_providers:
        providers_to_test.append(('CUDA', ['CUDAExecutionProvider']))
    if 'CPUExecutionProvider' in available_providers:
        # 尝试CPU优化配置
        providers_to_test.append(('CPU优化', ['CPUExecutionProvider']))
    providers_to_test.append(('默认CPU', []))  # 空列表使用默认
    
    # 创建测试数据
    test_input = np.random.rand(1, 3, 640, 640).astype(np.float32)
    
    for provider_name, providers in providers_to_test:
        try:
            # 创建session
            session_options = ort.SessionOptions()
            
            # 优化设置
            session_options.enable_cpu_mem_arena = True
            session_options.enable_mem_pattern = True
            session_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
            
            session = ort.InferenceSession(model_path, sess_options=session_options, providers=providers)
            
            # 获取输入输出名称
            input_name = session.get_inputs()[0].name
            print(f"[信息] 输入名称: {input_name}")
            
            # 预热
            for _ in range(5):
                session.run(None, {input_name: test_input})
            
            # 正式测试
            times = []
            for _ in range(20):
                start = time.time()
                session.run(None, {input_name: test_input})
                times.append(time.time() - start)
            
            avg_time = np.mean(times) * 1000  # 转毫秒
            std_time = np.std(times) * 1000
            
            print(f"[结果] {provider_name}: {avg_time:.1f}ms ± {std_time:.1f}ms")
            
        except Exception as e:
            print(f"[错误] {provider_name} 失败: {e}")

# 运行基准测试
model_path = "models/yolov5s-face.onnx"
benchmark_model(model_path)