import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from .paths import logs_dir


class ComponentLogger:
    """组件专用日志器，提供结构化日志记录"""
    
    def __init__(self, name: str, component: str) -> None:
        self.logger = logging.getLogger(name)
        self.component = component
        self.operation_start_time: Optional[float] = None
    
    def info(self, message: str, operation: Optional[str] = None) -> None:
        """信息日志"""
        if operation:
            message = f"[{self.component}] {operation}: {message}"
        else:
            message = f"[{self.component}] {message}"
        self.logger.info(message)
    
    def error(self, message: str, operation: Optional[str] = None, error: Optional[Exception] = None) -> None:
        """错误日志"""
        if operation:
            message = f"[{self.component}] {operation}: {message}"
        else:
            message = f"[{self.component}] {message}"
        
        if error:
            message = f"{message} - 错误: {error}"
        
        self.logger.error(message)
    
    def warning(self, message: str, operation: Optional[str] = None) -> None:
        """警告日志"""
        if operation:
            message = f"[{self.component}] {operation}: {message}"
        else:
            message = f"[{self.component}] {message}"
        self.logger.warning(message)
    
    def debug(self, message: str, operation: Optional[str] = None) -> None:
        """调试日志"""
        if operation:
            message = f"[{self.component}] {operation}: {message}"
        else:
            message = f"[{self.component}] {message}"
        self.logger.debug(message)
    
    def start_operation(self, operation: str) -> None:
        """开始操作计时"""
        self.operation_start_time = time.time()
        self.info(f"开始 {operation}", operation)
    
    def end_operation(self, operation: str, success: bool = True) -> None:
        """结束操作计时"""
        if self.operation_start_time:
            duration = time.time() - self.operation_start_time
            status = "成功" if success else "失败"
            self.info(f"{operation} {status}，耗时: {duration:.2f}秒", operation)
            self.operation_start_time = None


def setup_logging(level: str = "INFO", name: str = "mpvPlayer", max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3) -> ComponentLogger:
    """设置日志配置并返回应用级日志器"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # 清除现有处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(ch)

    # File handler
    log_file: Path = logs_dir() / f"{name}.log"
    fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    fh.setLevel(log_level)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s"))
    logger.addHandler(fh)
    
    return ComponentLogger("app", "Application")


def get_logger(name: str) -> ComponentLogger:
    """获取指定名称的组件日志器"""
    component_name = name.split('.')[-1] if '.' in name else name
    return ComponentLogger(name, component_name)
