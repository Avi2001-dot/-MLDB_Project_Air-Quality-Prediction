import os
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
import json
from pathlib import Path

from .logger import get_logger

logger = get_logger(__name__)


class SystemHealthMonitor:
    

    def __init__(self, history_size: int = 100):
       
        self.history_size = history_size
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.disk_history = deque(maxlen=history_size)
        self.timestamps = deque(maxlen=history_size)

    def collect_metrics(self) -> Dict[str, float]:
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            disk_info = psutil.disk_usage('/')

            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_info.percent,
                'memory_available_mb': memory_info.available / (1024 * 1024),
                'memory_used_mb': memory_info.used / (1024 * 1024),
                'disk_percent': disk_info.percent,
                'disk_free_mb': disk_info.free / (1024 * 1024),
                'timestamp': datetime.now().isoformat()
            }

            # Store in history
            self.cpu_history.append(cpu_percent)
            self.memory_history.append(memory_info.percent)
            self.disk_history.append(disk_info.percent)
            self.timestamps.append(datetime.now())

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
            return {}

    def get_average_metrics(self) -> Dict[str, float]:
        
        if not self.cpu_history:
            return {}

        return {
            'avg_cpu_percent': sum(self.cpu_history) / len(self.cpu_history),
            'avg_memory_percent': sum(self.memory_history) / len(self.memory_history),
            'avg_disk_percent': sum(self.disk_history) / len(self.disk_history),
            'max_cpu_percent': max(self.cpu_history),
            'max_memory_percent': max(self.memory_history),
            'max_disk_percent': max(self.disk_history),
            'min_cpu_percent': min(self.cpu_history),
            'min_memory_percent': min(self.memory_history),
            'min_disk_percent': min(self.disk_history)
        }

    def is_healthy(
        self,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 85.0,
        disk_threshold: float = 90.0
    ) -> Tuple[bool, List[str]]:
        
        warnings = []
        metrics = self.collect_metrics()

        if metrics.get('cpu_percent', 0) > cpu_threshold:
            warnings.append(
                f"High CPU usage: {metrics['cpu_percent']:.1f}% "
                f"(threshold: {cpu_threshold}%)"
            )

        if metrics.get('memory_percent', 0) > memory_threshold:
            warnings.append(
                f"High memory usage: {metrics['memory_percent']:.1f}% "
                f"(threshold: {memory_threshold}%)"
            )

        if metrics.get('disk_percent', 0) > disk_threshold:
            warnings.append(
                f"High disk usage: {metrics['disk_percent']:.1f}% "
                f"(threshold: {disk_threshold}%)"
            )

        return len(warnings) == 0, warnings


class ExecutionTimeTracker:
    

    def __init__(self):
        """Initialize execution time tracker."""
        self.timings = defaultdict(list)
        self.active_timers = {}

    def start_timer(self, operation_name: str) -> None:
        """
        Start timing an operation.

        Args:
            operation_name: Name of the operation to time
        """
        self.active_timers[operation_name] = time.time()
        logger.debug(f"Started timing: {operation_name}")

    def end_timer(self, operation_name: str) -> float:
        
        if operation_name not in self.active_timers:
            raise ValueError(f"Timer not started for: {operation_name}")

        start_time = self.active_timers.pop(operation_name)
        duration = time.time() - start_time

        self.timings[operation_name].append(duration)
        logger.debug(f"Completed {operation_name}: {duration:.3f}s")

        return duration

    def get_statistics(self, operation_name: str) -> Dict[str, float]:
        
        if operation_name not in self.timings or not self.timings[operation_name]:
            return {}

        timings = self.timings[operation_name]
        return {
            'count': len(timings),
            'min_seconds': min(timings),
            'max_seconds': max(timings),
            'mean_seconds': sum(timings) / len(timings),
            'total_seconds': sum(timings)
        }

    def get_all_statistics(self) -> Dict[str, Dict[str, float]]:
        
        return {
            op_name: self.get_statistics(op_name)
            for op_name in self.timings.keys()
        }

    def reset(self) -> None:
        """Reset all timing data."""
        self.timings.clear()
        self.active_timers.clear()
        logger.info("Execution time tracker reset")


class EventMetricsCollector:
   

    def __init__(self, window_size: int = 1000):
        
        self.window_size = window_size
        self.event_latencies = deque(maxlen=window_size)
        self.event_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        self.last_reset_time = datetime.now()

    def record_event(self, latency_ms: float, success: bool = True) -> None:
        
        self.event_latencies.append(latency_ms)
        self.event_count += 1

        if not success:
            self.error_count += 1

    def get_metrics(self) -> Dict[str, float]:
        
        if not self.event_latencies:
            return {
                'event_count': self.event_count,
                'error_count': self.error_count,
                'error_rate': 0.0,
                'throughput_events_per_second': 0.0
            }

        latencies = list(self.event_latencies)
        elapsed_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            'event_count': self.event_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / self.event_count if self.event_count > 0 else 0.0,
            'min_latency_ms': min(latencies),
            'max_latency_ms': max(latencies),
            'mean_latency_ms': sum(latencies) / len(latencies),
            'p95_latency_ms': self._percentile(latencies, 95),
            'p99_latency_ms': self._percentile(latencies, 99),
            'throughput_events_per_second': self.event_count / elapsed_seconds if elapsed_seconds > 0 else 0.0
        }

    @staticmethod
    def _percentile(data: List[float], percentile: float) -> float:
        
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def reset(self) -> None:
        """Reset metrics."""
        self.event_latencies.clear()
        self.event_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        self.last_reset_time = datetime.now()
        logger.info("Event metrics collector reset")


class PerformanceMonitor:
    """
    Comprehensive performance monitoring for the entire system.

    Aggregates metrics from system health, execution times, and event
    processing to provide holistic system performance view.
    """

    def __init__(self, metrics_dir: str = 'metrics'):
        
        self.metrics_dir = metrics_dir
        self.system_monitor = SystemHealthMonitor()
        self.execution_tracker = ExecutionTimeTracker()
        self.event_collector = EventMetricsCollector()
        self.start_time = datetime.now()

        # Create metrics directory
        Path(metrics_dir).mkdir(parents=True, exist_ok=True)

    def get_system_report(self) -> Dict:
        
        current_metrics = self.system_monitor.collect_metrics()
        average_metrics = self.system_monitor.get_average_metrics()
        is_healthy, warnings = self.system_monitor.is_healthy()

        return {
            'timestamp': datetime.now().isoformat(),
            'current_metrics': current_metrics,
            'average_metrics': average_metrics,
            'is_healthy': is_healthy,
            'warnings': warnings
        }

    def get_performance_report(self) -> Dict:
        
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': uptime_seconds,
            'execution_times': self.execution_tracker.get_all_statistics(),
            'event_metrics': self.event_collector.get_metrics()
        }

    def get_full_report(self) -> Dict:
       
        return {
            'timestamp': datetime.now().isoformat(),
            'system': self.get_system_report(),
            'performance': self.get_performance_report()
        }

    def save_report(self, report_name: str = 'monitoring_report') -> str:
        
        try:
            report = self.get_full_report()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{report_name}_{timestamp}.json"
            filepath = os.path.join(self.metrics_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)

            logger.info(f"Monitoring report saved to {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save monitoring report: {str(e)}")
            raise

    def log_report(self) -> None:
        """Log monitoring report to logger."""
        try:
            report = self.get_full_report()
            logger.info(f"System Report: {json.dumps(report['system'], indent=2)}")
            logger.info(f"Performance Report: {json.dumps(report['performance'], indent=2)}")
        except Exception as e:
            logger.error(f"Failed to log monitoring report: {str(e)}")


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def start_operation_timer(operation_name: str) -> None:
    
    monitor = get_performance_monitor()
    monitor.execution_tracker.start_timer(operation_name)


def end_operation_timer(operation_name: str) -> float:
    
    monitor = get_performance_monitor()
    return monitor.execution_tracker.end_timer(operation_name)


def record_event_metric(latency_ms: float, success: bool = True) -> None:
    
    monitor = get_performance_monitor()
    monitor.event_collector.record_event(latency_ms, success)
