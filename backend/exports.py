"""Copy completed videos to a configurable, easy-to-find local folder."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
from uuid import uuid4

SETTINGS_FILE = Path(__file__).resolve().parent.parent / 'settings.local.json'

def output_directory():
    value = os.environ.get('JD_VIDEO_OUTPUT_DIR')
    if not value and SETTINGS_FILE.exists():
        try:
            value = json.loads(SETTINGS_FILE.read_text(encoding='utf-8')).get('video_output_dir')
        except (OSError, ValueError, AttributeError) as error:
            raise ValueError('The video output setting could not be read. Check settings.local.json.') from error
    if not value:
        return None
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError('The video output folder must be an absolute path in settings.local.json.')
    return Path(value)

def publish(project, source):
    destination = output_directory()
    if destination is None:
        return None
    title = re.sub(r'[^a-zA-Z0-9_-]+', '-', project['title']).strip('-')[:70] or 'training'
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f'{title}-{stamp}-{uuid4().hex[:10]}.mp4'
    target = destination / filename
    temporary = target.with_suffix('.partial')
    try:
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, temporary)
        temporary.replace(target)
    except OSError as error:
        raise ValueError('Could not save the video to the chosen output folder. Check that the folder is available and writable, then generate again.') from error
    finally:
        temporary.unlink(missing_ok=True)
    return {'video': project['video'], 'path': str(target)}
