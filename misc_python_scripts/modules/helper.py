#!/usr/bin/env python3
"""
Helper module - utility functions for visualization.
"""
import functools


def verbose(func):
    """Decorator to print function execution info."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"[INFO] Running: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
