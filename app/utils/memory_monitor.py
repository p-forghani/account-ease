import logging
import psutil
import os
from functools import wraps
from flask import current_app, g, request
import time
from typing import Optional, Dict, Any


class MemoryMonitor:
    """Memory monitoring utility using psutil"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.process = psutil.Process(os.getpid())
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information"""
        try:
            # Process memory info
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            # System memory info
            system_memory = psutil.virtual_memory()
            
            return {
                'process': {
                    'rss': memory_info.rss,  # Resident Set Size
                    'vms': memory_info.vms,  # Virtual Memory Size
                    'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
                    'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
                    'percent': round(memory_percent, 2)
                },
                'system': {
                    'total_mb': round(system_memory.total / 1024 / 1024, 2),
                    'available_mb': round(system_memory.available / 1024 / 1024, 2),
                    'used_mb': round(system_memory.used / 1024 / 1024, 2),
                    'percent': system_memory.percent
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting memory info: {e}")
            return {}
    
    def log_memory_usage(self, context: str = ""):
        """Log current memory usage"""
        memory_info = self.get_memory_info()
        if memory_info:
            process_info = memory_info['process']
            system_info = memory_info['system']
            
            log_message = (
                f"Memory Usage{' - ' + context if context else ''}: "
                f"Process: {process_info['rss_mb']}MB ({process_info['percent']}%), "
                f"System: {system_info['used_mb']}/{system_info['total_mb']}MB "
                f"({system_info['percent']}%)"
            )
            self.logger.info(log_message)
    
    def log_memory_diff(self, before: Dict[str, Any], after: Dict[str, Any], context: str = ""):
        """Log memory usage difference"""
        if not before or not after:
            return
            
        rss_diff = after['process']['rss_mb'] - before['process']['rss_mb']
        vms_diff = after['process']['vms_mb'] - before['process']['vms_mb']
        
        log_message = (
            f"Memory Diff{' - ' + context if context else ''}: "
            f"RSS: {rss_diff:+.2f}MB, VMS: {vms_diff:+.2f}MB"
        )
        
        if abs(rss_diff) > 1.0:  # Only log if significant change (>1MB)
            self.logger.info(log_message)


def monitor_memory_usage(context: str = ""):
    """Decorator to monitor memory usage of a function"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = MemoryMonitor(current_app.logger if current_app else None)
            
            # Log before
            before = monitor.get_memory_info()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Log after
                after = monitor.get_memory_info()
                execution_time = time.time() - start_time
                
                function_context = f"{func.__name__}{' - ' + context if context else ''}"
                monitor.log_memory_diff(before, after, function_context)
                
                if execution_time > 1.0:  # Log slow operations
                    monitor.logger.info(f"Slow operation: {function_context} took {execution_time:.2f}s")
        
        return wrapper
    return decorator


def log_memory_periodic():
    """Log memory usage periodically (for use in background tasks)"""
    monitor = MemoryMonitor(current_app.logger if current_app else None)
    monitor.log_memory_usage("Periodic Check")


def setup_memory_monitoring_middleware(app):
    """Set up Flask middleware to monitor memory usage"""
    
    @app.before_request
    def before_request():
        if app.config.get('ENABLE_MEMORY_MONITORING', False):
            monitor = MemoryMonitor(app.logger)
            g.memory_before = monitor.get_memory_info()
            g.request_start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if app.config.get('ENABLE_MEMORY_MONITORING', False) and hasattr(g, 'memory_before'):
            monitor = MemoryMonitor(app.logger)
            memory_after = monitor.get_memory_info()
            request_time = time.time() - g.request_start_time
            
            # Only log if request took more than 100ms or used significant memory
            memory_diff = (memory_after['process']['rss_mb'] - g.memory_before['process']['rss_mb']) if memory_after and g.memory_before else 0
            
            if request_time > 0.1 or abs(memory_diff) > 0.5:
                context = f"{request.method} {request.path} ({response.status_code}) - {request_time:.3f}s"
                monitor.log_memory_diff(g.memory_before, memory_after, context)
        
        return response