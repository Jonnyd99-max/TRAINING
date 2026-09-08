"""Real short export plus custom-folder/open-location/playback checks."""
import argparse
import os
from pathlib import Path
import time
from unittest.mock import patch
from uuid import uuid4

TEST_ROOT = Path(__file__).resolve().parent.parent / 'test-results' / ('exports-' + uuid4().hex)
os.environ['JD_PROJECTS_DIR'] = str(TEST_ROOT)
from fastapi.testclient import TestClient
from .main import app, exports

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', default=str(TEST_ROOT / 'exports'))
    destination = Path(parser.parse_args().destination).resolve()
    os.environ['JD_VIDEO_OUTPUT_DIR'] = str(destination)
    created = []
    try:
        with TestClient(app) as client:
            def ok(response):
                assert response.status_code == 200, response.text
                return response.json()
            p = ok(client.post('/api/projects', json={'title': 'Output folder test'}))
            p['scenes'][0]['duration'] = 1
            p = ok(client.put('/api/projects/' + p['id'], json=p))
            job = ok(client.post('/api/projects/' + p['id'] + '/render'))
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                job = ok(client.get('/api/jobs/' + job['id']))
                if job['status'] != 'running':
                    break
                time.sleep(.1)
            assert job['status'] == 'complete', job
            p = ok(client.get('/api/projects/' + p['id']))
            target = Path(p['video_export']['path'])
            created.append(target)
            assert target.parent == destination and target.stat().st_size > 1000
            playback = client.get('/api/projects/' + p['id'] + '/media/' + p['video'])
            assert playback.status_code == 200 and playback.content == target.read_bytes()
            with patch('os.startfile', create=True) as open_folder:
                opened = ok(client.post('/api/projects/' + p['id'] + '/open-output'))
                assert Path(opened['path']) == destination
                if os.name == 'nt':
                    open_folder.assert_called_once_with(str(destination))
            duplicate = exports.publish(p, TEST_ROOT / p['id'] / p['video'])
            created.append(Path(duplicate['path']))
            assert duplicate['path'] != str(target)
            # Files generated solely by this test are cleaned up below.
            blocked = TEST_ROOT / 'not-a-directory'
            blocked.write_text('test', encoding='utf-8')
            with patch.dict(os.environ, {'JD_VIDEO_OUTPUT_DIR': str(blocked)}):
                try:
                    exports.publish(p, TEST_ROOT / p['id'] / p['video'])
                except ValueError as error:
                    assert 'Could not save' in str(error)
                else:
                    raise AssertionError('An unwritable folder was accepted')
            print(f'PASS: actual MP4 saved in {destination}; playback, Open Video Location, unique filenames and folder-error handling verified.')
    finally:
        for path in created:
            assert path.parent == destination and path.name.startswith('Output-folder-test-')
            path.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
