import uvicorn
import webview
import threading
import time
import socket

from src.api import app

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_server(port):
    # Running uvicorn programmatically
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

if __name__ == '__main__':
    # Determine an available port
    port = get_free_port()
    
    # Start the FastAPI server in a separate thread
    t = threading.Thread(target=start_server, args=(port,))
    t.daemon = True
    t.start()

    # Give it a moment to spin up
    time.sleep(1)

    # Create and start the webview window pointing to our local server
    webview.create_window('Skill Optimizer', f'http://127.0.0.1:{port}', width=1280, height=720, maximized=True)
    webview.start()
