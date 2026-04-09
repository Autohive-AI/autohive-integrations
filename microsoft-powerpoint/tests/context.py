import sys
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
os.chdir(parent_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../dependencies')))
from microsoft_powerpoint import microsoft_powerpoint  # noqa: F401
