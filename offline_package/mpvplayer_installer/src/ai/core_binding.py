"""
核心绑定管理模块

针对飞腾E2000 4核处理器的多核绑核优化，
实现进程和线程级别的CPU核心绑定。
"""

import os
import psutil
import threading
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class CoreBindingConfig:
    """核心绑定配置"""
    system_cores: List[int] = None      # 系统预留核心
    camera_cores: List[int] = None      # 摄像头采集核心
    mpv_cores: List[int] = None         # MPV播放器核心
    ai_cores: List[int] = None          # AI推理核心
    
    def __post_init__(self):
        if self.system_cores is None:
            self.system_cores = [0]      # 默认核心0为系统预留
        if self.camera_cores is None:
            self.camera_cores = [1]      # 默认核心1为摄像头采集
        if self.mpv_cores is None:
            self.mpv_cores = [2]         # 默认核心2为MPV播放器
        if self.ai_cores is None:
            self.ai_cores = [3]          # 默认核心3为AI推理


class CoreBindingManager:
    """核心绑定管理器"""
    
    def __init__(self, config: Optional[CoreBindingConfig] = None):
        """
        初始化核心绑定管理器
        
        Args:
            config: 核心绑定配置，默认使用4核优化配置
        """
        self.config = config or CoreBindingConfig()
        self.total_cores = psutil.cpu_count(logical=False)  # 物理核心数
        
        # 验证配置有效性
        self._validate_config()
        
        # 绑定记录
        self.binding_records = {}
        
        print(f"✓ 核心绑定管理器初始化完成")
        print(f"✓ 系统核心数: {self.total_cores}")
        print(f"✓ 核心分配: 系统{self.config.system_cores}, "
              f"摄像头{self.config.camera_cores}, MPV{self.config.mpv_cores}, AI{self.config.ai_cores}")
    
    def _validate_config(self):
        """验证核心配置有效性"""
        all_cores = (self.config.system_cores + self.config.camera_cores + 
                    self.config.mpv_cores + self.config.ai_cores)
        
        # 检查核心重复
        if len(all_cores) != len(set(all_cores)):
            raise ValueError("核心配置中存在重复的核心编号")
        
        # 检查核心范围
        for core in all_cores:
            if core < 0 or core >= self.total_cores:
                raise ValueError(f"核心编号 {core} 超出范围 [0, {self.total_cores-1}]")
        
        # 检查是否覆盖所有核心（可选）
        if len(all_cores) < self.total_cores:
            print(f"⚠️ 警告: 未使用所有核心，剩余核心: {set(range(self.total_cores)) - set(all_cores)}")
    
    def bind_process_to_cores(self, process_name: str, cores: List[int], 
                            pid: Optional[int] = None) -> bool:
        """
        绑定进程到指定核心
        
        Args:
            process_name: 进程名称（用于记录）
            cores: 要绑定的核心列表
            pid: 进程ID，如果为None则使用当前进程
            
        Returns:
            绑定是否成功
        """
        try:
            if pid is None:
                pid = os.getpid()
            
            # 获取进程对象
            process = psutil.Process(pid)
            
            # 检查进程是否仍在运行
            if not process.is_running():
                print(f"✗ 进程 {pid} 未在运行")
                return False
            
            # 设置CPU亲和性
            process.cpu_affinity(cores)
            
            # 记录绑定信息
            self.binding_records[process_name] = {
                'pid': pid,
                'cores': cores,
                'type': 'process',
                'timestamp': psutil.boot_time()
            }
            
            print(f"✓ 进程 '{process_name}' (PID: {pid}) 绑定到核心 {cores}")
            return True
            
        except Exception as e:
            print(f"✗ 进程绑定失败: {e}")
            return False
    
    def bind_thread_to_cores(self, thread_name: str, cores: List[int], 
                           thread_id: Optional[int] = None) -> bool:
        """
        绑定线程到指定核心（Linux系统有效）
        
        Args:
            thread_name: 线程名称
            cores: 要绑定的核心列表
            thread_id: 线程ID，如果为None则使用当前线程
            
        Returns:
            绑定是否成功
        """
        try:
            # 在Windows上，线程级绑定需要特殊处理
            import platform
            if platform.system() == "Windows":
                print("⚠️ Windows系统暂不支持线程级核心绑定，使用进程级绑定")
                return self.bind_process_to_cores(thread_name, cores)
            
            # Linux系统使用taskset命令进行线程级绑定
            if thread_id is None:
                thread_id = threading.get_ident()
            
            # 构建核心掩码
            core_mask = self._create_core_mask(cores)
            
            # 使用taskset命令绑定线程
            cmd = f"taskset -p {core_mask} {thread_id}"
            result = os.system(cmd)
            
            if result == 0:
                self.binding_records[thread_name] = {
                    'thread_id': thread_id,
                    'cores': cores,
                    'type': 'thread',
                    'timestamp': psutil.boot_time()
                }
                print(f"✓ 线程 '{thread_name}' (TID: {thread_id}) 绑定到核心 {cores}")
                return True
            else:
                print(f"✗ 线程绑定命令执行失败")
                return False
                
        except Exception as e:
            print(f"✗ 线程绑定失败: {e}")
            return False
    
    def _create_core_mask(self, cores: List[int]) -> str:
        """创建核心掩码字符串"""
        mask = 0
        for core in cores:
            mask |= (1 << core)
        return hex(mask)
    
    def bind_camera_thread(self, thread_obj=None) -> bool:
        """绑定摄像头采集线程到指定核心"""
        return self.bind_thread_to_cores(
            'camera_capture', 
            self.config.camera_cores,
            thread_obj.ident if thread_obj else None
        )
    
    def bind_mpv_process(self, pid: Optional[int] = None) -> bool:
        """绑定MPV播放器进程到指定核心"""
        return self.bind_process_to_cores(
            'mpv_player', 
            self.config.mpv_cores,
            pid
        )
    
    def bind_ai_inference_thread(self, thread_obj=None) -> bool:
        """绑定AI推理线程到指定核心"""
        return self.bind_thread_to_cores(
            'ai_inference', 
            self.config.ai_cores,
            None  # 不传递线程ID，让bind_thread_to_cores内部处理
        )
    
    def get_cpu_usage(self) -> Dict:
        """获取各核心的CPU使用率"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            
            usage_info = {}
            for i, usage in enumerate(cpu_percent):
                core_type = self._get_core_type(i)
                usage_info[i] = {
                    'usage_percent': round(usage, 1),
                    'type': core_type,
                    'assigned': i in (self.config.system_cores + self.config.camera_cores + 
                                    self.config.mpv_cores + self.config.ai_cores)
                }
            
            return usage_info
            
        except Exception as e:
            print(f"✗ 获取CPU使用率失败: {e}")
            return {}
    
    def _get_core_type(self, core: int) -> str:
        """获取核心类型"""
        if core in self.config.system_cores:
            return 'system'
        elif core in self.config.camera_cores:
            return 'camera'
        elif core in self.config.mpv_cores:
            return 'mpv'
        elif core in self.config.ai_cores:
            return 'ai'
        else:
            return 'unassigned'
    
    def get_binding_status(self) -> Dict:
        """获取当前绑定状态"""
        status = {
            'total_cores': self.total_cores,
            'binding_records': self.binding_records,
            'cpu_usage': self.get_cpu_usage(),
            'config': {
                'system_cores': self.config.system_cores,
                'camera_cores': self.config.camera_cores,
                'mpv_cores': self.config.mpv_cores,
                'ai_cores': self.config.ai_cores
            }
        }
        return status
    
    def optimize_binding(self) -> Dict:
        """根据当前负载优化核心绑定"""
        cpu_usage = self.get_cpu_usage()
        
        # 分析各核心负载
        overloaded_cores = []
        underutilized_cores = []
        
        for core, info in cpu_usage.items():
            if info['usage_percent'] > 80:  # 负载过高
                overloaded_cores.append(core)
            elif info['usage_percent'] < 20:  # 负载过低
                underutilized_cores.append(core)
        
        optimization_suggestions = []
        
        # 生成优化建议
        if overloaded_cores:
            optimization_suggestions.append({
                'type': 'load_balancing',
                'message': f"核心 {overloaded_cores} 负载过高，考虑重新分配任务",
                'suggested_actions': [
                    "将部分任务迁移到低负载核心",
                    "优化算法减少计算量",
                    "增加任务执行间隔"
                ]
            })
        
        if underutilized_cores:
            optimization_suggestions.append({
                'type': 'resource_utilization',
                'message': f"核心 {underutilized_cores} 利用率不足",
                'suggested_actions': [
                    "将更多任务分配到这些核心",
                    "启用并行处理",
                    "优化任务调度策略"
                ]
            })
        
        return {
            'overloaded_cores': overloaded_cores,
            'underutilized_cores': underutilized_cores,
            'suggestions': optimization_suggestions
        }
    
    def set_realtime_priority(self, process_name: str, pid: Optional[int] = None) -> bool:
        """设置进程实时优先级（需要管理员权限）"""
        try:
            if pid is None:
                pid = os.getpid()
            
            process = psutil.Process(pid)
            
            # 设置高优先级（Windows）
            if os.name == 'nt':
                process.nice(psutil.HIGH_PRIORITY_CLASS)
            else:
                # Linux系统设置实时优先级
                os.nice(-10)  # 提高优先级
            
            print(f"✓ 进程 '{process_name}' 设置为高优先级")
            return True
            
        except Exception as e:
            print(f"✗ 设置实时优先级失败（可能需要管理员权限）: {e}")
            return False


def create_4core_optimized_config() -> CoreBindingConfig:
    """创建4核飞腾E2000优化配置"""
    return CoreBindingConfig(
        system_cores=[0],   # 核心0：系统基础服务
        camera_cores=[1],   # 核心1：摄像头采集（低延迟）
        mpv_cores=[2],      # 核心2：MPV播放器（媒体处理）
        ai_cores=[3]        # 核心3：AI推理（计算密集型）
    )


# 测试代码
if __name__ == "__main__":
    # 创建4核优化配置
    config = create_4core_optimized_config()
    
    # 初始化核心绑定管理器
    manager = CoreBindingManager(config)
    
    # 绑定当前进程到AI核心
    manager.bind_process_to_cores('test_process', config.ai_cores)
    
    # 获取绑定状态
    status = manager.get_binding_status()
    print("绑定状态:", status)
    
    # 获取CPU使用率
    usage = manager.get_cpu_usage()
    print("CPU使用率:", usage)
    
    # 优化建议
    optimization = manager.optimize_binding()
    print("优化建议:", optimization)