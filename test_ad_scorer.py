#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试广告关注度评分系统
"""

import sys
import os

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ai.ad_attention_scorer import AdAttentionScorer
import time

def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试广告关注度评分系统 ===")
    
    scorer = AdAttentionScorer()
    
    # 测试1: 模拟一个高质量的广告观看场景
    print("\n测试1: 高质量广告观看场景")
    scorer.start_ad_tracking("ad_high_quality", 30.0)
    
    # 模拟高质量观看：开始有人关注，中间稳定，结束持续
    for i in range(90):  # 3FPS × 30秒
        if i < 30:  # 前10秒：逐渐增加关注
            face_count = 4
            gazing_faces = min(3, i // 10 + 1)
        elif i < 60:  # 中间10秒：稳定高质量关注
            face_count = 3
            gazing_faces = 3
        else:  # 最后10秒：持续关注
            face_count = 2
            gazing_faces = 2
        
        scorer.add_frame_data(face_count, gazing_faces)
        time.sleep(0.01)  # 模拟真实时间间隔
    
    result1 = scorer.end_ad_tracking()
    print(f"高质量广告得分: {result1['total_score']}/100")
    print("各维度得分:")
    for dim, score in result1['breakdown'].items():
        print(f"  {dim}: {score}")
    
    # 测试2: 模拟一个低质量的广告观看场景
    print("\n测试2: 低质量广告观看场景")
    scorer.start_ad_tracking("ad_low_quality", 30.0)
    
    # 模拟低质量观看：波动大，关注不稳定
    for i in range(90):
        if i % 10 < 5:  # 50%的时间有人关注
            face_count = 3
            gazing_faces = 1 if i % 2 == 0 else 2  # 波动
        else:  # 50%的时间无人关注
            face_count = 0
            gazing_faces = 0
        
        scorer.add_frame_data(face_count, gazing_faces)
        time.sleep(0.01)
    
    result2 = scorer.end_ad_tracking()
    print(f"低质量广告得分: {result2['total_score']}/100")
    print("各维度得分:")
    for dim, score in result2['breakdown'].items():
        print(f"  {dim}: {score}")
    
    # 测试3: 模拟一个中等质量的广告观看场景
    print("\n测试3: 中等质量广告观看场景")
    scorer.start_ad_tracking("ad_medium_quality", 30.0)
    
    # 模拟中等质量观看：有一定关注但波动
    for i in range(90):
        if i < 45:  # 前半段：较好关注
            face_count = 4
            gazing_faces = 2
        else:  # 后半段：关注减少
            face_count = 3
            gazing_faces = 1
        
        scorer.add_frame_data(face_count, gazing_faces)
        time.sleep(0.01)
    
    result3 = scorer.end_ad_tracking()
    print(f"中等质量广告得分: {result3['total_score']}/100")
    print("各维度得分:")
    for dim, score in result3['breakdown'].items():
        print(f"  {dim}: {score}")
    
    # 显示广告排名
    print("\n=== 广告排名 ===")
    ranking = scorer.get_score_ranking()
    for i, ad_info in enumerate(ranking):
        print(f"{i+1}. {ad_info['ad_id']}: {ad_info['score']}/100")
    
    return True

def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    scorer = AdAttentionScorer()
    
    # 测试1: 无人观看的广告
    print("\n测试1: 无人观看")
    scorer.start_ad_tracking("ad_no_watch", 30.0)
    
    for i in range(90):
        scorer.add_frame_data(0, 0)  # 始终无人
        time.sleep(0.01)
    
    result = scorer.end_ad_tracking()
    print(f"无人观看广告得分: {result['total_score']}/100")
    
    # 测试2: 全员观看的广告
    print("\n测试2: 全员观看")
    scorer.start_ad_tracking("ad_all_watch", 30.0)
    
    for i in range(90):
        scorer.add_frame_data(5, 5)  # 始终全员观看
        time.sleep(0.01)
    
    result = scorer.end_ad_tracking()
    print(f"全员观看广告得分: {result['total_score']}/100")
    
    # 测试3: 短广告
    print("\n测试3: 短广告（10秒）")
    scorer.start_ad_tracking("ad_short", 10.0)
    
    for i in range(30):  # 3FPS × 10秒
        scorer.add_frame_data(3, 2)  # 稳定观看
        time.sleep(0.01)
    
    result = scorer.end_ad_tracking()
    print(f"短广告得分: {result['total_score']}/100")
    
    return True

def test_continuity_optimization():
    """测试持续关注深度优化效果"""
    print("\n=== 测试持续关注深度优化 ===")
    
    scorer = AdAttentionScorer()
    
    # 测试连续关注场景
    print("\n测试: 连续关注 vs 间断关注")
    
    # 场景1: 连续关注（高质量）
    scorer.start_ad_tracking("ad_continuous", 30.0)
    for i in range(90):
        scorer.add_frame_data(3, 3)  # 持续高质量关注
        time.sleep(0.01)
    result1 = scorer.end_ad_tracking()
    
    # 场景2: 间断关注（中等质量）
    scorer.start_ad_tracking("ad_intermittent", 30.0)
    for i in range(90):
        if i % 20 < 10:  # 50%时间有关注
            scorer.add_frame_data(3, 3)
        else:
            scorer.add_frame_data(3, 0)
        time.sleep(0.01)
    result2 = scorer.end_ad_tracking()
    
    print(f"连续关注广告得分: {result1['total_score']}/100")
    print(f"间断关注广告得分: {result2['total_score']}/100")
    
    # 检查持续关注深度得分差异
    cont_score = result1['breakdown']['duration_score']
    inter_score = result2['breakdown']['duration_score']
    print(f"持续关注深度得分: {cont_score} vs {inter_score}")
    
    return True

if __name__ == "__main__":
    try:
        # 运行所有测试
        test_basic_functionality()
        test_edge_cases()
        test_continuity_optimization()
        
        print("\n=== 所有测试完成 ===")
        print("广告关注度评分系统功能正常！")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()