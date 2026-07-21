#!/usr/bin/env python3
"""
PD Generator - CLI Entrypoint Launcher
"""
import sys
import os

# Ensure src is importable
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(PROJECT_ROOT, "cred", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

from cli import main

if __name__ == "__main__":
    main()
