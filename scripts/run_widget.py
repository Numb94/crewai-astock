import webview
import sys
import os
import threading
import time
import requests

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configuration
FLASK_PORT = 7000
WIDGET_URL = f'http://127.0.0.1:{FLASK_PORT}/widget'

def check_server():
    """Check if the Flask server is running"""
    try:
        requests.get(WIDGET_URL)
        return True
    except:
        return False

def start_webview():
    """Start the desktop widget"""
    # Create a frameless window
    webview.create_window(
        'Quantum Widget',
        url=WIDGET_URL,
        width=320,
        height=480,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True
    )
    webview.start()

if __name__ == '__main__':
    print("Checking for CrewAI A-Stock Server...")
    if not check_server():
        print(f"Error: Flask server not running at {WIDGET_URL}")
        print("Please run 'python app.py' in a separate terminal first.")
        sys.exit(1)
    
    print("Launching Quantum Widget...")
    start_webview()
