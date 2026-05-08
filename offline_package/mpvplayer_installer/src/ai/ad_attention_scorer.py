#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
广告关注度评分器 - 基于实际帧数据结构的100分制评分系统
"""

import numpy as np
import time
from typing import List, Dict, Optional
from collections import defaultdict


class AdAttentionScorer:
    """优化版广告关注度评分器 - 解决重复计算和得分偏低问题"""
    
    def __init__(self):
        self.current_ad_data = []  # 当前广告的帧数据
        self.ad_records = {}  # 存储每个广告的统计信息
        self.ad_historical_stats = {}  # 存储广告的历史统计信息（用于累计平均排名）
        self.ad_start_time = None
        self.current_ad_id = None
        self.ad_duration = 0
        
    def start_ad_tracking(self, ad_id: str, ad_duration: float):
        """开始跟踪一个新广告"""
        self.current_ad_data = []
        self.ad_start_time = time.time()
        self.current_ad_id = ad_id
        self.ad_duration = ad_duration
        print(f"开始跟踪广告: {ad_id}, 时长: {ad_duration}秒")
    
    def add_frame_data(self, face_count: int, gazing_faces: int):
        """添加帧检测数据"""
        if self.ad_start_time is None:
            return
            
        current_time = time.time()
        ad_progress = (current_time - self.ad_start_time) / self.ad_duration if self.ad_duration > 0 else 0
        
        data_point = {
            'timestamp': current_time,
            'face_count': face_count,
            'gazing_faces': gazing_faces,
            'ad_progress': min(1.0, max(0.0, ad_progress))  # 限制在0-1之间
        }
        self.current_ad_data.append(data_point)
    
    def calculate_continuity_metric(self, data_points: List[Dict]) -> float:
        """计算持续关注指标 - 使用预期连续长度优化"""
        if not data_points:
            return 0.0
        
        streak_lengths = []
        current_streak = 0
        total_frames = len(data_points)
        
        # 计算连续关注段
        for dp in data_points:
            if dp['gazing_faces'] > 0:
                current_streak += 1
            else:
                if current_streak > 0:
                    streak_lengths.append(current_streak)
                    current_streak = 0
        
        # 处理最后一段连续关注
        if current_streak > 0:
            streak_lengths.append(current_streak)
        
        if not streak_lengths:
            return 0.0
        
        # 计算平均连续关注长度
        avg_streak = sum(streak_lengths) / len(streak_lengths)
        
        # 优化：使用预期连续长度替代直接除以总帧数
        # 预期连续长度 = 总帧数 / (关注段数 + 1)
        expected_streak = total_frames / (len(streak_lengths) + 1)
        
        if expected_streak > 0:
            continuity_ratio = min(1.0, avg_streak / expected_streak)
        else:
            continuity_ratio = 0.0
        
        return continuity_ratio
    
    def calculate_consistency_metric(self, data_points: List[Dict]) -> float:
        """计算关注稳定性指标"""
        attention_ratios = []
        
        for dp in data_points:
            if dp['face_count'] > 0:
                ratio = dp['gazing_faces'] / dp['face_count']
                attention_ratios.append(ratio)
        
        if len(attention_ratios) < 2:
            # 单帧数据给中等评分，无数据给0分
            return 0.5 if len(attention_ratios) == 1 else 0.0
        
        # 计算标准差
        std_dev = np.std(attention_ratios)
        
        # 标准差小于0.3认为稳定，大于0.6认为不稳定
        consistency = max(0.0, 1.0 - min(1.0, std_dev / 0.6))
        
        return consistency
    
    def end_ad_tracking(self) -> Dict:
        """结束广告跟踪并计算得分"""
        if not self.current_ad_data or self.current_ad_id is None:
            return {
                'total_score': 0.0,
                'breakdown': {},
                'statistics': {},
                'error': '没有广告数据或未开始跟踪'
            }
        
        data_points = self.current_ad_data
        total_frames = len(data_points)
        
        # 基础统计计算
        total_face_count = sum(dp['face_count'] for dp in data_points)
        total_gazing_faces = sum(dp['gazing_faces'] for dp in data_points)
        
        if total_frames == 0:
            return {
                'total_score': 0.0,
                'breakdown': {},
                'statistics': {},
                'error': '无有效数据帧'
            }
        
        avg_gazing_faces = total_gazing_faces / total_frames
        max_face_count = max(dp['face_count'] for dp in data_points) if data_points else 1
        
        # 1. 注意力比率得分（25分）- 观看质量
        attention_ratio = total_gazing_faces / total_face_count if total_face_count > 0 else 0.0
        attention_score = 25.0 * min(1.0, attention_ratio)
        
        # 2. 绝对关注规模得分（20分）- 观看规模
        if max_face_count > 0:
            # 使用对数平滑，避免人数过多时得分过高
            log_score = np.log2(1 + avg_gazing_faces) / np.log2(1 + max_face_count)
            absolute_score = 20.0 * min(1.0, log_score)
        else:
            absolute_score = 0.0
        
        # 3. 持续关注深度得分（25分）- 观看深度（关键优化）
        continuity_ratio = self.calculate_continuity_metric(data_points)
        duration_score = 25.0 * continuity_ratio
        
        # 4. 关注稳定性得分（15分）- 稳定性
        consistency = self.calculate_consistency_metric(data_points)
        consistency_score = 15.0 * consistency
        
        # 5. 关注覆盖率得分（15分）- 覆盖率
        effective_frames = sum(1 for dp in data_points if dp['gazing_faces'] > 0)
        efficiency_ratio = effective_frames / total_frames
        efficiency_score = 15.0 * efficiency_ratio
        
        # 最终总分
        total_score = attention_score + absolute_score + duration_score + consistency_score + efficiency_score
        
        # 构建结果
        result = {
            'total_score': round(total_score, 1),
            'breakdown': {
                'attention_score': round(attention_score, 1),      # 注意力比率
                'absolute_score': round(absolute_score, 1),        # 绝对规模
                'duration_score': round(duration_score, 1),        # 持续深度
                'consistency_score': round(consistency_score, 1),  # 稳定性
                'efficiency_score': round(efficiency_score, 1)     # 覆盖率
            },
            'statistics': {
                'ad_id': self.current_ad_id,
                'ad_duration': self.ad_duration,
                'total_frames': total_frames,
                'avg_face_count': round(total_face_count / total_frames, 1),
                'avg_gazing_faces': round(avg_gazing_faces, 1),
                'attention_ratio': round(attention_ratio, 3),
                'continuity_ratio': round(continuity_ratio, 3),
                'consistency': round(consistency, 3),
                'efficiency_ratio': round(efficiency_ratio, 3)
            }
        }
        
        # 存储记录
        self.ad_records[self.current_ad_id] = result
        
        # 更新历史统计（只统计有效得分>0的数据）
        if result['total_score'] > 0:
            self._update_historical_stats(self.current_ad_id, result['total_score'])
        
        # 清空当前数据
        self.current_ad_data = []
        self.ad_start_time = None
        self.current_ad_id = None
        
        print(f"广告 {result['statistics']['ad_id']} 评分完成: {result['total_score']}/100")
        
        return result
    
    def _update_historical_stats(self, ad_id: str, score: float) -> None:
        """更新广告的历史统计信息"""
        if ad_id not in self.ad_historical_stats:
            # 初始化历史统计
            self.ad_historical_stats[ad_id] = {
                'total_score': score,
                'play_count': 1,
                'avg_score': score,
                'latest_score': score
            }
        else:
            # 更新历史统计
            stats = self.ad_historical_stats[ad_id]
            stats['total_score'] += score
            stats['play_count'] += 1
            stats['avg_score'] = stats['total_score'] / stats['play_count']
            stats['latest_score'] = score
    
    def get_ad_score(self, ad_id: str) -> Optional[Dict]:
        """获取指定广告的评分结果"""
        # 如果请求的是当前正在播放的广告，不返回得分（避免频繁打印5维度详情）
        if ad_id == self.current_ad_id and self.ad_start_time is not None:
            return None
        
        return self.ad_records.get(ad_id)
    
    def get_all_scores(self) -> Dict[str, Dict]:
        """获取所有广告的评分结果"""
        return self.ad_records.copy()
    
    def get_score_ranking(self) -> List[Dict]:
        """获取广告评分排名（基于历史有效得分的平均分）"""
        scores = []
        
        # 优先使用历史统计中的平均得分
        for ad_id, stats in self.ad_historical_stats.items():
            scores.append({
                'ad_id': ad_id,
                'score': stats['avg_score'],  # 使用平均得分
                'play_count': stats['play_count'],  # 播放次数
                'total_score': stats['total_score'],  # 累计总分
                'ranking_type': 'historical_avg'
            })
        
        # 对于没有历史统计但最近有得分的广告，使用最新得分
        for ad_id, result in self.ad_records.items():
            if ad_id not in self.ad_historical_stats and result['total_score'] > 0:
                scores.append({
                    'ad_id': ad_id,
                    'score': result['total_score'],  # 使用最新得分
                    'play_count': 1,  # 只播放过一次
                    'total_score': result['total_score'],  # 累计总分
                    'ranking_type': 'latest_score'
                })
        
        # 按平均得分降序排列
        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores


def test_optimized_scorer():
    """测试优化版评分器"""
    scorer = AdAttentionScorer()
    
    # 模拟一个30秒广告
    ad_duration = 30
    scorer.start_ad_tracking("test_ad_001", ad_duration)
    
    # 模拟不同阶段的观看数据
    total_frames = 90  # 3FPS × 30秒
    
    for i in range(total_frames):
        progress = i / total_frames
        
        # 模拟真实的观看模式
        if progress < 0.2:  # 开始阶段：人数多，关注少
            face_count = 6
            gazing_faces = 1
        elif progress < 0.4:  # 上升阶段：关注增加
            face_count = 5
            gazing_faces = 3
        elif progress < 0.7:  # 稳定阶段：高质量关注
            face_count = 4
            gazing_faces = 3
        else:  # 结尾阶段：人数减少但关注稳定
            face_count = 3
            gazing_faces = 2
        
        scorer.add_frame_data(face_count, gazing_faces)
    
    # 计算得分
    result = scorer.end_ad_tracking()
    
    print("=== 广告关注度评分结果 ===")
    print(f"总分: {result['total_score']}/100")
    print("\n各维度得分:")
    for dim, score in result['breakdown'].items():
        print(f"  {dim}: {score}")
    
    print("\n统计数据:")
    for stat, value in result['statistics'].items():
        print(f"  {stat}: {value}")
    
    return result


if __name__ == "__main__":
    # 运行测试
    test_optimized_scorer()