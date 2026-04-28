# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Performance Monitoring Module
=============================
Metrics, profiling, and performance optimization utilities.
"""
import time
import functools
import threading
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from contextlib import contextmanager
import logging
import asyncio

log = logging.getLogger("performance")


@dataclass
class TimingMetric:
    """Timing metric for a function or operation."""
    name: str
    count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add(self, duration: float):
        """Add a timing measurement."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.recent_times.append(duration)
    
    @property
    def avg_time(self) -> float:
        """Average time."""
        return self.total_time / self.count if self.count > 0 else 0.0
    
    @property
    def p95_time(self) -> float:
        """95th percentile time."""
        if not self.recent_times:
            return 0.0
        sorted_times = sorted(self.recent_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "avg_ms": round(self.avg_time * 1000, 2),
            "min_ms": round(self.min_time * 1000, 2),
            "max_ms": round(self.max_time * 1000, 2),
            "p95_ms": round(self.p95_time * 1000, 2),
        }


class PerformanceMonitor:
    """Monitor performance metrics."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        self.metrics: Dict[str, TimingMetric] = {}
        self.active_timers: Dict[str, float] = {}
    
    def start_timer(self, name: str):
        """Start a timer."""
        self.active_timers[name] = time.perf_counter()
    
    def end_timer(self, name: str) -> float:
        """End timer and record metric."""
        if name not in self.active_timers:
            log.warning(f"Timer {name} not started")
            return 0.0
        
        elapsed = time.perf_counter() - self.active_timers[name]
        del self.active_timers[name]
        
        if name not in self.metrics:
            self.metrics[name] = TimingMetric(name)
        
        self.metrics[name].add(elapsed)
        return elapsed
    
    def record(self, name: str, duration: float):
        """Record a timing directly."""
        if name not in self.metrics:
            self.metrics[name] = TimingMetric(name)
        self.metrics[name].add(duration)
    
    def get_metric(self, name: str) -> Optional[TimingMetric]:
        """Get metric by name."""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get all metrics as dict."""
        return {name: metric.to_dict() for name, metric in self.metrics.items()}
    
    def reset(self):
        """Reset all metrics."""
        self.metrics.clear()
        self.active_timers.clear()


# Global monitor instance
monitor = PerformanceMonitor()


def timed(name: Optional[str] = None):
    """Decorator to time function execution."""
    def decorator(func: Callable) -> Callable:
        metric_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor.start_timer(metric_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = monitor.end_timer(metric_name)
                if elapsed > 1.0:  # Log slow operations
                    log.warning(f"Slow operation: {metric_name} took {elapsed:.2f}s")
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor.start_timer(metric_name)
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = monitor.end_timer(metric_name)
                if elapsed > 1.0:
                    log.warning(f"Slow operation: {metric_name} took {elapsed:.2f}s")
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper
    return decorator


@contextmanager
def timed_block(name: str):
    """Context manager for timing blocks."""
    monitor.start_timer(name)
    try:
        yield
    finally:
        monitor.end_timer(name)


class MemoryProfiler:
    """Simple memory usage tracking."""
    
    def __init__(self):
        self.snapshots: deque = deque(maxlen=100)
    
    def snapshot(self, label: str = ""):
        """Take memory snapshot."""
        try:
            import psutil
            process = psutil.Process()
            mem_mb = process.memory_info().rss / 1024 / 1024
            self.snapshots.append({
                "label": label,
                "memory_mb": round(mem_mb, 2),
                "timestamp": time.time()
            })
            return mem_mb
        except ImportError:
            return 0.0
    
    def get_snapshots(self) -> List[Dict]:
        """Get all snapshots."""
        return list(self.snapshots)


# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "api_response": 0.5,  # 500ms
    "llm_call": 30.0,     # 30s
    "file_operation": 0.1, # 100ms
    "db_query": 0.1,      # 100ms
}


def check_performance(name: str, duration: float) -> tuple[bool, str]:
    """Check if performance is within threshold."""
    threshold = PERFORMANCE_THRESHOLDS.get(name, 1.0)
    is_ok = duration <= threshold
    status = "OK" if is_ok else f"SLOW (threshold: {threshold}s)"
    return is_ok, status


class CachingDecorator:
    """TTL + LRU-bounded cache decorator.

    Uses an OrderedDict so eviction is O(1) (popitem(last=False) removes the
    oldest insertion regardless of expiry).  Expired entries are lazily removed
    on access so the hot path stays fast.
    """

    def __init__(self, ttl_seconds: float = 60.0, max_size: int = 1000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hash(args)}:{hash(tuple(sorted(kwargs.items())))}"
            now = time.time()

            with self._lock:
                if key in self._cache:
                    result, expiry = self._cache[key]
                    if now < expiry:
                        self._cache.move_to_end(key)  # refresh LRU position
                        return result
                    del self._cache[key]

            result = func(*args, **kwargs)

            with self._lock:
                if len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)  # evict oldest — O(1)
                self._cache[key] = (result, now + self.ttl)

            return result

        return wrapper


def memoize(ttl_seconds: float = 60.0):
    """Memoization decorator with TTL."""
    cache = CachingDecorator(ttl_seconds)
    return cache


# Export common utilities
__all__ = [
    "PerformanceMonitor",
    "monitor",
    "timed",
    "timed_block",
    "MemoryProfiler",
    "check_performance",
    "memoize",
]
