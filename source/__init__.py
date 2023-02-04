"""
    This file contains boilerplate to allow this program to be used
    from within a Home Assistant integration, by upgrading search path
    to allow relative path import in python 3.6
"""

from pathlib import Path
import sys
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
