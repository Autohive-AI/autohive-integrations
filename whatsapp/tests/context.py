# -*- coding: utf-8 -*-
import sys
import os

# Add the parent directory to the path so we can import the integration
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../dependencies")))

# Set the working directory to the integration directory so config.json can be found
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from whatsapp import whatsapp