#!/usr/bin/env python3
"""LLM Gateway CLI Entrypoint."""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.cli import main

if __name__ == "__main__":
    main()
