#!/usr/bin/env python3
"""
Checker module - utility functions for visualization.
"""
import os


def folder(path):
    """Ensure folder exists, create if not."""
    os.makedirs(path, exist_ok=True)
    return path
