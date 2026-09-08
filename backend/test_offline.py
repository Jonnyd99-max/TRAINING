"""Real offline narration/export test: python -m backend.test_offline.

Requires Piper voice models, FFmpeg and httpx. Blocks Python network entry
points and the online TTS client; no fabricated speech substitutes are used.
"""
import asyncio
import io
import json
import os
import socket
from pathlib import Path
import time
from unittest.mock import patch
from uuid import uuid4

TEST_ROOT = Path(__file__).resolve().parent.parent / 'test-results' / ('offline-' + uuid4().hex)
os.environ['JD_PROJECTS_DIR'] = str(TEST_ROOT)
os.environ['JD_VIDEO_OUTPUT_DIR'] = str(TEST_ROOT / 'exports')
from fastapi.testclient import TestClient
from PIL import Image
from .main import app, Scene, media, offline_tts

real_connect = socket.socket.connect
def local_connect(sock, address):
    # Windows asyncio implements its internal socketpair over loopback.
    if isinstance(address, tuple) and address[0] in {'127.0.0.1', '::1'}:
        return real_connect(sock, address)
    raise AssertionError('Offline narration attempted an external socket connection')

def main():
    results = {}
    blocked = AssertionError('Offline narration attempted to use the network')
    with patch('socket.create_connection', side_effect=blocked), \
         patch('socket.socket.connect', new=local_connect), \
         patch('edge_tts.Communicate', side_effect=blocked), \
         patch('aiohttp.ClientSession', side_effect=blocked), TestClient(app) as client:
        def ok(response):
            assert response.status_code == 200, response.text
            return response.json()
        health = ok(client.get('/api/health'))
        assert health['offline_ready'], health['offline_message']
        assert health['ffmpeg'], 'Install FFmpeg or set FFMPEG_PATH.'
        results['installed_voices'] = list(health['offline_voices'])
        p = ok(client.post('/api/projects', json={'title': 'Offline speech verification'}))
        pid = p['id']
        assert p['scenes'][0]['voice'] == health['default_voice']
        assert p['scenes'][0]['voice'].startswith('piper:')
        image = io.BytesIO()
        Image.new('RGB', (1280, 720), '#367b65').save(image, 'PNG')
        uploaded = ok(client.post(f'/api/projects/{pid}/images', files={'file': ('offline.png', image.getvalue(), 'image/png')}))
        text = 'Welcome to offline training. Review the highest priority lots before moving any work.'
        p['scenes'] += [Scene(title='Offline step', image=uploaded['image'], narration=text, caption='All narration generated locally.').model_dump()]
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        sid = p['scenes'][1]['id']
        p = ok(client.post(f'/api/projects/{pid}/scenes/{sid}/narration'))
        s = p['scenes'][1]
        baseline = s['audio_duration']
        assert baseline > 1 and abs(s['duration'] - baseline - 1) < .02
        assert len(client.get(f'/api/projects/{pid}/media/{s["audio"]}').content) > 1000
        results['real_offline_speech_and_auto_duration'] = 'passed'
        cached = TEST_ROOT / pid / s['audio']
        timestamp = cached.stat().st_mtime_ns
        with patch.object(offline_tts, 'synthesize', side_effect=AssertionError('Cache was not reused')):
            p = ok(client.post(f'/api/projects/{pid}/scenes/{sid}/narration'))
        assert cached.stat().st_mtime_ns == timestamp
        results['cache_reuse'] = 'passed'
        # Change speed, ensure stale audio disappears, and respect a manual duration.
        p['scenes'][1].update(speed=100, duration=2, manual_duration=True)
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        assert p['scenes'][1]['audio'] is None
        p = ok(client.post(f'/api/projects/{pid}/scenes/{sid}/narration'))
        assert .4 < p['scenes'][1]['audio_duration']/baseline < .65
        assert p['scenes'][1]['duration'] == 2
        assert p['scenes'][1]['audio'] != s['audio']
        results['speed_cache_invalidation_and_manual_duration'] = 'passed'
        # Every downloaded voice must produce decodable speech, including literal
        # punctuation and Unicode passed directly to the local speech engine.
        for voice in health['offline_voices']:
            p['scenes'][1].update(voice=voice, narration='Check "priority" — it’s £5.\nRead $value literally.', speed=-50, manual_duration=False)
            p = ok(client.put(f'/api/projects/{pid}', json=p))
            p = ok(client.post(f'/api/projects/{pid}/scenes/{sid}/narration'))
            assert p['scenes'][1]['audio_duration'] > 1
        results['all_installed_voices_and_unicode'] = 'passed'
        # A previously saved but removed voice must fail clearly, never go online.
        p['scenes'][1]['voice'] = 'piper:Missing Test Voice'
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        response = client.post(f'/api/projects/{pid}/scenes/{sid}/narration')
        assert response.status_code == 400 and 'not installed' in response.json()['detail']
        assert not list((TEST_ROOT / pid / 'audio').glob('*.tmp.*'))
        # Regenerate at export, not in advance, to exercise the background path.
        p['scenes'][1].update(voice=health['default_voice'], narration=text, speed=0, manual_duration=False)
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        job = ok(client.post(f'/api/projects/{pid}/render'))
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            job = ok(client.get('/api/jobs/' + job['id']))
            if job['status'] != 'running':
                break
            time.sleep(.25)
        assert job['status'] == 'complete', job
        p = ok(client.get(f'/api/projects/{pid}'))
        video = TEST_ROOT / pid / p['video']
        media.run([media.ffmpeg(), '-v', 'error', '-i', str(video), '-f', 'null', '-'])
        assert p['scenes'][1]['audio'] and p['scenes'][1]['duration'] > baseline
        results['offline_mp4_export_full_decode'] = 'passed'
        results['missing_voice_friendly_error_no_online_fallback'] = 'passed'
        results['video'] = str(video)
        # Core storage still works when offline voice discovery fails.
        with patch.object(offline_tts, 'find_spec', return_value=None):
            failed = ok(client.get('/api/health'))
            assert not failed['offline_ready'] and failed['offline_message']
            assert ok(client.get(f'/api/projects/{pid}'))['scenes'][1]['voice'].startswith('piper:')
        offline_tts.refresh()
        results['missing_engine_health_and_persistence'] = 'passed'
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    (TEST_ROOT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
