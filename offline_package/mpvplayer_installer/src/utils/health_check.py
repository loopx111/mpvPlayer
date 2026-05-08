"""
健康检查模块，用于监控各组件状态并自动恢复
"""
import time
import threading
from typing import Dict, Any, Callable, Optional
from ..utils.logger import get_logger


class HealthCheck:
    """健康检查器"""
    
    def __init__(self, check_interval: int = 30) -> None:
        self.log = get_logger("health")
        self.check_interval = check_interval
        self.checks: Dict[str, Dict[str, Any]] = {}
        self._running = True
        self._thread: Optional[threading.Thread] = None
    
    def register_component(self, 
                          component_name: str, 
                          check_func: Callable[[], bool],
                          recovery_func: Optional[Callable[[], None]] = None,
                          max_failures: int = 3) -> None:
        """注册组件健康检查"""
        self.checks[component_name] = {
            'check_func': check_func,
            'recovery_func': recovery_func,
            'max_failures': max_failures,
            'failure_count': 0,
            'last_check': 0,
            'healthy': True
        }
        self.log.info(f"注册组件健康检查: {component_name}", "register_component")
    
    def start(self) -> None:
        """启动健康检查"""
        if self._thread and self._thread.is_alive():
            return
            
        def health_check_loop():
            while self._running:
                try:
                    self._perform_checks()
                except Exception as e:
                    self.log.error(f"健康检查异常: {e}", "health_check_loop", e)
                
                time.sleep(self.check_interval)
        
        self._thread = threading.Thread(target=health_check_loop, daemon=True)
        self._thread.start()
        self.log.info("健康检查已启动", "start")
    
    def stop(self) -> None:
        """停止健康检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.log.info("健康检查已停止", "stop")
    
    def _perform_checks(self) -> None:
        """执行所有健康检查"""
        current_time = time.time()
        
        for component_name, check_info in self.checks.items():
            # 避免过于频繁的检查
            if current_time - check_info['last_check'] < self.check_interval:
                continue
                
            check_info['last_check'] = current_time
            
            try:
                is_healthy = check_info['check_func']()
                
                if is_healthy:
                    if not check_info['healthy']:
                        self.log.info(f"组件 {component_name} 已恢复健康", "health_recovered")
                    check_info['healthy'] = True
                    check_info['failure_count'] = 0
                else:
                    check_info['failure_count'] += 1
                    check_info['healthy'] = False
                    
                    self.log.warning(f"组件 {component_name} 健康检查失败 ({check_info['failure_count']}/{check_info['max_failures']})", "health_check_failed")
                    
                    # 触发恢复机制
                    if (check_info['failure_count'] >= check_info['max_failures'] and 
                        check_info['recovery_func']):
                        self.log.info(f"尝试恢复组件 {component_name}", "recovery_attempt")
                        try:
                            check_info['recovery_func']()
                            check_info['failure_count'] = 0  # 重置失败计数
                            self.log.info(f"组件 {component_name} 恢复成功", "recovery_success")
                        except Exception as e:
                            self.log.error(f"组件 {component_name} 恢复失败: {e}", "recovery_failed", e)
                            
            except Exception as e:
                self.log.error(f"执行组件 {component_name} 健康检查时出错: {e}", "health_check_error", e)
                check_info['failure_count'] += 1
                check_info['healthy'] = False
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有组件状态"""
        status = {}
        for name, info in self.checks.items():
            status[name] = {
                'healthy': info['healthy'],
                'failure_count': info['failure_count'],
                'last_check': info['last_check']
            }
        return status
    
    def is_component_healthy(self, component_name: str) -> bool:
        """检查特定组件是否健康"""
        if component_name not in self.checks:
            return False
        return self.checks[component_name]['healthy']