#!/usr/bin/env python3
"""
WSGI Configuration for PythonAnywhere
Facebook Messenger Bot - Complete Version
"""

import sys
import os

# Add project directory to Python path
project_home = '/home/yourusername/mysite'  # Replace with your actual username
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from .env file
def load_environment():
    """Load environment variables from .env file"""
    env_file = os.path.join(project_home, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value.strip('"\'')

# Load environment
load_environment()

# Import the Flask application
from app import app as application

if __name__ == "__main__":
    application.run()