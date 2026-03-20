#!/usr/bin/env python3
"""
factory.py — legacy entry point, kept for backward compatibility.

Please use factoryctl (or factoryctl.py) instead.
This file will be removed in a future release.
"""
import sys
import os

# Re-exec factoryctl.py from the same directory
here = os.path.dirname(os.path.abspath(__file__))
fctl = os.path.join(here, "factoryctl.py")

if os.path.exists(fctl):
    exec(open(fctl).read())
else:
    print("Error: factoryctl.py not found. Please use factoryctl directly.")
    sys.exit(1)
