"""Launch the working checkout without packaging it or installing dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8000'


def already_running():
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1', 8000)) != 0:
            return False
    try:
        with urllib.request.urlopen(URL+'/api/health', timeout=3) as response:
            health = json.load(response)
        if 'voices' in health and 'offline_ready' in health:
            return True
    except (OSError, ValueError):
        pass
    raise RuntimeError('Port 8000 is occupied by another program. Close that program and try again.')


def build():
    frontend = ROOT/'frontend'
    candidates = list((frontend/'node_modules').glob('.pnpm/@esbuild+win32-x64@*/node_modules/@esbuild/win32-x64/esbuild.exe'))
    candidates += list((frontend/'node_modules').glob('@esbuild/win32-x64/esbuild.exe'))
    if not candidates:
        raise RuntimeError('The frontend build tool is missing. Restore frontend/node_modules or run the standard setup.')
    dist = frontend/'dist'
    dist.mkdir(exist_ok=True)
    print('Building the latest interface...', flush=True)
    subprocess.run([str(candidates[0]), str(frontend/'src/main.jsx'), '--bundle', '--minify',
                    '--format=esm', '--outfile='+str(dist/'app.js')], cwd=ROOT, check=True)
    version = hashlib.sha256((dist/'app.js').read_bytes()+(dist/'app.css').read_bytes()).hexdigest()[:12]
    html = (frontend/'index.html').read_text(encoding='utf-8')
    html = html.replace('/src/main.jsx', '/app.js?v='+version)
    html = html.replace('</head>', f'<link rel="stylesheet" href="/app.css?v={version}"></head>')
    (dist/'index.html').write_text(html, encoding='utf-8')


def preflight(check_write=False):
    import uvicorn
    from backend import media, exports
    if not media.ffmpeg():
        raise RuntimeError('FFmpeg is missing. Restore its configured location before starting.')
    subprocess.run([media.ffmpeg(), '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    if check_write:
        destination = exports.output_directory()
        if destination:
            destination.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(prefix='.jd-write-check-', dir=destination):
                pass
            print('Video output folder is writable.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Build and check without starting a server or opening a browser.')
    parser.add_argument('--check-write', action='store_true', help='Also test the configured export folder.')
    args = parser.parse_args()
    os.chdir(ROOT)
    if not args.check and already_running():
        import webbrowser
        print('JD Training Studio is already running. Opening your browser.')
        print('To load code updates, close its existing server window and start again.')
        webbrowser.open(URL)
        return
    preflight(check_write=args.check_write or not args.check)
    build()
    if args.check:
        print('Launcher checks passed. No server was started.')
        return
    print('\nJD Training Studio is running at '+URL, flush=True)
    print('Keep this window open while using the app. Close it to stop the app.\n', flush=True)
    from launch import open_browser
    import threading
    import uvicorn
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('\nJD Training Studio could not start:\n'+str(error), flush=True)
        raise SystemExit(1)
