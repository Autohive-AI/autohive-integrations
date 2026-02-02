# -*- coding: utf-8 -*-
import sys
import os

# Get the parent directory (github folder)
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Change working directory to the github folder so config.json can be found
os.chdir(parent_dir)

sys.path.insert(0, parent_dir)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

from github import github
