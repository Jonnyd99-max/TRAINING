"""Open the local UI once FastAPI is ready; keep one visible server terminal."""
import threading
import time
import urllib.request
import webbrowser
import uvicorn

def open_browser():
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
                if response.status == 200:
                    webbrowser.open('http://127.0.0.1:8000')
                    return
        except OSError:
            time.sleep(.5)

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000)
