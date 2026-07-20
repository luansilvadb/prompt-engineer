import uvicorn
import webview
import threading
import time
import socket
import sys

from src.api import app

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def wait_for_port(port, host='127.0.0.1', timeout=10.0):
    start_time = time.time()
    while True:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
            if time.time() - start_time > timeout:
                return False

class APIServer(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        self.server = uvicorn.Server(config=config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

if __name__ == '__main__':
    port = get_free_port()
    api_thread = APIServer(port)
    api_thread.start()

    print(f"Waiting for port {port}...")
    if not wait_for_port(port):
        print("Failed to start API server.")
        sys.exit(1)
    
    print("Server started successfully.")
    
    # Simulating webview logic by stopping server after 2 seconds
    time.sleep(2)
    print("Stopping server...")
    api_thread.stop()
    api_thread.join(timeout=3)
    if api_thread.is_alive():
        print("Server thread did not stop in time.")
    else:
        print("Server stopped gracefully.")
