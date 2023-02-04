# For relative imports to work in Python 3.6
from pathlib import Path
import sys
DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
