#!/usr/bin/env python3
import subprocess
import sys
import os
import time

def start_server():
    """Start the Flask server"""
    try:
        # Change to the correct directory
        os.chdir('/home/runner/workspace')
        
        # Start the Flask app
        process = subprocess.Popen([
            sys.executable, 'app.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print(f"Server started with PID: {process.pid}")
        print("Server is running on http://0.0.0.0:5000")
        
        # Keep the process running
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            process.terminate()
            
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    start_server()