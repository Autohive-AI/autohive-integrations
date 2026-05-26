import sys
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(parent_dir)
sys.path.insert(0, parent_dir)
from lumin_pdf import lumin_pdf  # noqa
