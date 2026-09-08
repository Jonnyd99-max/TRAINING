"""Integration smoke test. Run with: python -m backend.test_workflow

Uses isolated project storage; tests offline TTS by default, --online for Edge.
Install httpx as a test-only dependency. Requires FFmpeg on PATH/FFMPEG_PATH.
"""
import io
import json
import os
from pathlib import Path
import shutil
import time
import sys
from uuid import uuid4

TEST_ROOT = Path(__file__).resolve().parent.parent / 'test-results' / uuid4().hex
os.environ['JD_PROJECTS_DIR'] = str(TEST_ROOT)
os.environ['JD_VIDEO_OUTPUT_DIR'] = str(TEST_ROOT / 'exports')
from fastapi.testclient import TestClient
from PIL import Image
from .main import app, Scene, media

def main():
    results = {}
    with TestClient(app) as client:
        def ok(response):
            assert response.status_code == 200, response.text
            return response.json()
        health = ok(client.get('/api/health'))
        online = '--online' in sys.argv
        engine = 'edge_tts' if online else 'offline_tts'
        voice = 'en-GB-SoniaNeural' if online else health['default_voice']
        results['ffmpeg'] = health['ffmpeg']
        assert len(ok(client.get('/api/projects'))[0]['scenes']) == 3
        p = ok(client.post('/api/projects', json={'title': 'Workflow verification', 'subtitle': 'A real export', 'opening': True}))
        pid = p['id']
        raw = io.BytesIO()
        Image.new('RGB', (1000, 650), '#72bda7').save(raw, format='PNG')
        upload = ok(client.post(f'/api/projects/{pid}/images', files={'file': ('screen.png', raw.getvalue(), 'image/png')}))
        assert client.post(f'/api/projects/{pid}/images', files={'file': ('bad.txt', b'not an image')}).status_code == 400
        p['scenes'] += [Scene(title='First step', image=upload['image'], voice=voice, narration='Welcome to training.', caption="Review the highest priority lots first.").model_dump(),
                        Scene(title='Second step', image=upload['image'], duration=2, manual_duration=True).model_dump()]
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        assert client.put(f'/api/projects/{pid}', json={**p, 'revision': 0}).status_code == 409
        p['scenes'][1], p['scenes'][2] = p['scenes'][2], p['scenes'][1]
        p = ok(client.put(f'/api/projects/{pid}', json=p))
        assert ok(client.get(f'/api/projects/{pid}'))['scenes'][1]['title'] == 'Second step'
        results['create_upload_reorder_save_reopen'] = 'passed'
        results['invalid_upload_and_stale_save'] = 'passed'
        sid = p['scenes'][2]['id']
        if health['ffmpeg']:
            tts = client.post(f'/api/projects/{pid}/scenes/{sid}/narration')
            if tts.status_code == 200:
                p = tts.json()
                s = p['scenes'][2]
                assert s['audio_duration'] > 0
                assert abs(s['duration'] - s['audio_duration'] - 1) < .02
                assert len(client.get(f'/api/projects/{pid}/media/{s["audio"]}').content) > 100
                results[engine] = 'passed: real synthesis, audio playback bytes and automatic duration'
            else:
                if not online and health['offline_ready']:
                    raise AssertionError(tts.text)
                results[engine] = f'unavailable: {tts.text}'
                # Test FFmpeg audio integration separately with a known generated tone.
                audio = TEST_ROOT / pid / 'audio' / 'test-tone.mp3'
                media.run([media.ffmpeg(), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', str(audio)])
                p['scenes'][2]['narration'] = ''
                p = ok(client.put(f'/api/projects/{pid}', json=p))
                saved = TEST_ROOT / pid / 'project.json'
                p['scenes'][2].update(audio='audio/test-tone.mp3', audio_key=media.signature(p['scenes'][2]))
                saved.write_text(json.dumps(p), encoding='utf-8')
            job = ok(client.post(f'/api/projects/{pid}/render'))
            assert client.put(f'/api/projects/{pid}', json=p).status_code == 409
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                job = ok(client.get(f'/api/jobs/{job["id"]}'))
                if job['status'] != 'running':
                    break
                time.sleep(.3)
            assert job['status'] == 'complete', job
            p = ok(client.get(f'/api/projects/{pid}'))
            video = TEST_ROOT / pid / p['video']
            assert video.stat().st_size > 1000
            media.run([media.ffmpeg(), '-v', 'error', '-i', str(video), '-f', 'null', '-'])
            # Extract a frame for visual QA and inspect actual codec/resolution metadata.
            media.run([media.ffmpeg(), '-y', '-v', 'error', '-ss', '6', '-i', str(video), '-frames:v', '1', str(TEST_ROOT / 'export-frame.png')])
            import subprocess
            metadata = subprocess.run([media.ffmpeg(), '-i', str(video)], capture_output=True, text=True).stderr
            assert '1920x1080' in metadata and 'h264' in metadata and 'aac' in metadata, metadata
            results['mp4_1080p_h264_aac_decode'] = 'passed'
            results['video'] = str(video)
        with TestClient(app) as reopened:
            assert reopened.get(f'/api/projects/{pid}').json()['title'] == 'Workflow verification'
            assert len(reopened.get('/api/projects').json()) == 2
        results['app_restart_persistence'] = 'passed'
    (TEST_ROOT / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
