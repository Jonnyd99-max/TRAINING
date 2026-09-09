import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator
from .subtitles import SubtitleCue

from . import media
from . import offline_tts
from . import exports
from .visuals import Annotation, CameraMotion

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('JD_PROJECTS_DIR', ROOT / 'projects')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(ROOT / 'logs').mkdir(exist_ok=True)
log = logging.getLogger('jd-studio')
log.setLevel(logging.INFO)
log.addHandler(RotatingFileHandler(ROOT / 'logs' / 'studio.log', maxBytes=2_000_000, backupCount=2))
lock = threading.RLock()
jobs = {}
active = set()

def now():
    return datetime.now(timezone.utc).isoformat()

class Scene(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r'^[a-f0-9]{32}$')
    kind: str = Field(default='image', pattern=r'^(image|title)$')
    title: str = Field(default='Untitled scene', max_length=120)
    subtitle: str = Field(default='', max_length=160)
    narration: str = Field(default='', max_length=10000)
    caption: str = Field(default='', max_length=220)
    subtitles_enabled: bool = False
    subtitle_cues: list[SubtitleCue] | None = Field(default=None, max_length=1000)
    image: str | None = None
    audio: str | None = None
    audio_key: str | None = None
    audio_duration: float | None = None
    duration: float = Field(default=5, ge=1, le=3600)
    manual_duration: bool = False
    voice: str = Field(default_factory=offline_tts.default_voice, min_length=1, max_length=200)
    speed: int = Field(default=0, ge=-50, le=100)
    annotations: list[Annotation] = Field(default_factory=list, max_length=40)
    camera: CameraMotion = Field(default_factory=CameraMotion)

    @model_validator(mode='after')
    def validate_subtitle_order(self):
        previous = 0
        for cue in self.subtitle_cues or []:
            if cue.start < previous:
                raise ValueError('Subtitles must be in order and cannot overlap.')
            previous = cue.end
        return self

class ProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(default='', max_length=160)
    opening: bool = True

class ProjectEdit(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    subtitle: str = Field(default='', max_length=160)
    scenes: list[Scene] = Field(max_length=100)
    revision: int

def folder(pid):
    if not re.fullmatch(r'[a-f0-9]{32}', pid):
        raise HTTPException(404, 'Project not found.')
    return DATA / pid

def read(pid):
    try:
        return json.loads((folder(pid) / 'project.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise HTTPException(404, 'Project files are missing or damaged. Restore the project folder from a backup.')

def write(project):
    directory = folder(project['id'])
    for name in ['images', 'audio', 'output']:
        (directory / name).mkdir(parents=True, exist_ok=True)
    project['modified'] = now()
    target = directory / 'project.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(project, indent=2), encoding='utf-8')
    temporary.replace(target)

def create(data):
    project = dict(id=uuid4().hex, title=data.title.strip() or 'Untitled training', subtitle=data.subtitle,
                   scenes=[], revision=0, modified=now(), video=None)
    if data.opening:
        project['scenes'].append(Scene(kind='title', title=project['title'], subtitle=data.subtitle).model_dump())
    write(project)
    return project

def editable(pid):
    if pid in active:
        raise HTTPException(409, 'Please wait until media generation finishes before editing this project.')

def seed():
    marker = DATA / '.demo-created'
    if marker.exists():
        return
    project = create(ProjectInput(title='Scheduler Training Demo', opening=False))
    texts = [
        ('Welcome to Scheduler', 'Welcome to Scheduler Training. This short guide explains how production priorities are displayed.'),
        ('Review lot priorities', 'The priority list determines which lots should be processed first. Always review the highest priority lots before selecting additional work.'),
        ('Confirm the location', 'Before moving a lot, confirm that its recorded location is correct.'),
    ]
    for i, (title, narration) in enumerate(texts):
        image = Image.new('RGB', (1920, 1080), '#e9eef4')
        d = ImageDraw.Draw(image)
        d.rectangle((0, 0, 1920, 120), fill='#152235')
        d.text((70, 34), 'SCHEDULER  /  TRAINING DEMO', font=media.font(38), fill='white')
        d.text((90, 185), title, font=media.font(62), fill='#17283e')
        for row, content in enumerate(['LOT 1042    HIGH PRIORITY        Assembly A', 'LOT 1086    STANDARD                 Warehouse B', 'LOT 1091    STANDARD                 Inspection C']):
            y = 360 + row*155
            d.rounded_rectangle((90, y, 1830, y+115), 16, fill='#c8f3e6' if row == i else 'white')
            d.text((125, y+35), content, font=media.font(34), fill='#17283e')
        d.text((90, 945), 'Demonstration only - replace this image with your screenshot', font=media.font(27), fill='#526174')
        relative = f'images/demo-{i}.png'
        image.save(folder(project['id']) / relative)
        project['scenes'].append(Scene(title=title, narration=narration, image=relative,
                                      caption=['Understand production priorities', 'Review the highest priority lots first', 'Check the recorded location before moving a lot'][i]).model_dump())
    write(project)
    marker.write_text(project['id'])

@asynccontextmanager
async def lifespan(app):
    seed()
    yield

app = FastAPI(title='JD Training Studio', lifespan=lifespan)
@app.middleware('http')
async def local_requests(request: Request, call_next):
    origin = request.headers.get('origin')
    allowed = {'http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:8000', 'http://127.0.0.1:8000'}
    if request.method in {'POST', 'PUT', 'DELETE'} and origin and origin not in allowed:
        return JSONResponse({'detail': 'Open JD Training Studio from its local address.'}, status_code=403)
    return await call_next(request)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173',
                                               'http://localhost:8000', 'http://127.0.0.1:8000'],
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type'])

@app.get('/api/health')
def health():
    binary = media.ffmpeg()
    ready = False
    if binary:
        try:
            media.run([binary, '-version'])
            ready = True
        except (OSError, RuntimeError):
            pass
    offline = offline_tts.refresh()
    return dict(ffmpeg=ready, voices={**offline['voices'], **media.VOICES},
                offline_voices=offline['voices'], online_voices=media.VOICES,
                offline_ready=offline['ready'], default_voice=offline['default_voice'],
                offline_message=offline['message'], offline_instructions=offline_tts.INSTRUCTIONS,
                instructions='Install FFmpeg (including ffmpeg.exe), add its bin folder to PATH, then restart. On Windows: winget install Gyan.FFmpeg')

@app.get('/api/projects')
def list_projects():
    result = []
    for path in DATA.glob('*/project.json'):
        try:
            p = read(path.parent.name)
            result.append({k: p[k] for k in ['id', 'title', 'modified', 'scenes']})
        except HTTPException:
            log.warning('Unreadable project: %s', path)
    return sorted(result, key=lambda p: p['modified'], reverse=True)

@app.post('/api/projects')
def new_project(data: ProjectInput):
    with lock:
        return create(data)

@app.get('/api/projects/{pid}')
def get_project(pid: str):
    with lock:
        return read(pid)

@app.put('/api/projects/{pid}')
def save_project(pid: str, data: ProjectEdit):
    with lock:
        editable(pid)
        project = read(pid)
        if data.revision != project['revision']:
            raise HTTPException(409, 'This project changed in another window. Reopen it before saving.')
        existing = {s['id']: s for s in project['scenes']}
        scenes = [s.model_dump() for s in data.scenes]
        if len({s['id'] for s in scenes}) != len(scenes):
            raise HTTPException(400, 'Each scene must have a unique identifier.')
        for scene in scenes:
            if len({a['id'] for a in scene['annotations']}) != len(scene['annotations']):
                raise HTTPException(400, 'Each annotation must have a unique identifier within its scene.')
            if scene['voice'] not in media.VOICES and not offline_tts.is_offline(scene['voice']):
                raise HTTPException(400, 'Choose one of the available narration voices.')
            for key in ['image', 'audio']:
                value = scene[key]
                if value and (not re.fullmatch(r'(images|audio)/[a-zA-Z0-9_-]+\.(png|mp3)', value)
                              or not (folder(pid) / value).is_file()):
                    raise HTTPException(400, 'A scene media file is missing. Upload the image or regenerate narration.')
            # Only preserve server-generated narration metadata; edits invalidate it.
            old = existing.get(scene['id'])
            if old and media.signature(old) != media.signature(scene):
                scene['subtitle_cues'] = None
            if old and old.get('audio_key') == media.signature(scene):
                for key in ['audio', 'audio_key', 'audio_duration']:
                    scene[key] = old.get(key)
            else:
                scene.update(audio=None, audio_key=None, audio_duration=None)
        project.update(title=data.title.strip() or 'Untitled training', subtitle=data.subtitle,
                       scenes=scenes, revision=project['revision']+1, video=None)
        write(project)
        return project

@app.post('/api/projects/{pid}/images')
async def upload(pid: str, file: UploadFile):
    read(pid)
    contents = await file.read(20*1024*1024+1)
    if len(contents) > 20*1024*1024:
        raise HTTPException(400, 'Choose an image smaller than 20 MB.')
    import io
    try:
        with Image.open(io.BytesIO(contents)) as image:
            if image.format not in ['PNG', 'JPEG', 'WEBP'] or image.width*image.height > 40_000_000:
                raise ValueError()
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((3840, 2160))
            relative = f'images/{uuid4().hex}.png'
            image.save(folder(pid) / relative)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, 'Unsupported image. Use a PNG, JPEG or WebP image under 40 megapixels.')
    return dict(image=relative)

@app.get('/api/projects/{pid}/media/{area}/{name}')
def get_media(pid: str, area: str, name: str):
    if area not in ['images', 'audio', 'output'] or not re.fullmatch(r'[a-zA-Z0-9_-]+\.(png|mp3|mp4)', name):
        raise HTTPException(404, 'Media file not found.')
    path = folder(pid) / area / name
    if not path.is_file():
        raise HTTPException(404, 'Media file is missing. Upload or generate it again.')
    return FileResponse(path)

@app.post('/api/projects/{pid}/scenes/{sid}/narration')
async def narration(pid: str, sid: str):
    with lock:
        editable(pid)
        project = read(pid)
        scene = next((s for s in project['scenes'] if s['id'] == sid), None)
        if not scene:
            raise HTTPException(404, 'Scene not found.')
        active.add(pid)
    try:
        await media.narrate(scene, folder(pid))
        with lock:
            project['revision'] += 1
            project['video'] = None
            write(project)
        return project
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        log.exception('Narration failed')
        if offline_tts.is_offline(scene['voice']):
            raise HTTPException(500, 'Offline narration failed. Check the selected Piper voice and FFmpeg, then retry. Details are in logs/studio.log.')
        raise HTTPException(502, 'Narration could not be generated. Check your internet connection and retry; the free Edge TTS service may be unavailable.')
    finally:
        with lock:
            active.discard(pid)

def render_job(jobid, project):
    pid = project['id']
    job = jobs[jobid]
    directory = folder(pid)
    scratch = directory / 'output' / f'work-{jobid}'
    scratch.mkdir()
    try:
        job.update(message='Preparing scenes...', progress=5)
        for i, scene in enumerate(project['scenes']):
            if scene['narration'].strip():
                job.update(message=f'Generating narration {i+1} of {len(project["scenes"])}...', progress=10)
                asyncio.run(media.narrate(scene, directory))
        with lock:
            project['revision'] += 1
            write(project)
        segments = []
        for i, scene in enumerate(project['scenes']):
            job.update(message=f'Rendering scene {i+1} of {len(project["scenes"])}...',
                       progress=20 + int(65*i/len(project['scenes'])))
            segments.append(media.render_scene(scene, directory, scratch, i))
        job.update(message='Combining video...', progress=90)
        manifest = scratch / 'segments.txt'
        manifest.write_text('\n'.join(f"file '{p.name}'" for p in segments), encoding='utf-8')
        output = f'output/training-{jobid}.mp4'
        media.run([media.ffmpeg(), '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(manifest),
                   '-vf', f'fps={media.visuals.FPS}', *media.video_encoding_args(),
                   '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-threads', '2',
                   '-movflags', '+faststart', str(directory / output)])
        project['video'] = output
        job.update(message='Saving video...', progress=95)
        project['video_export'] = exports.publish(project, directory / output)
        with lock:
            project.update(video=output, revision=project['revision']+1)
            write(project)
        job.update(status='complete', progress=100, message='VIDEO READY', video=output)
    except ValueError as e:
        log.exception('Video narration failed')
        job.update(status='failed', message=str(e))
    except Exception:
        log.exception('Video generation failed')
        job.update(status='failed', message='Video generation failed. Check FFmpeg, available disk space and your narration voice. Online voices also require internet. Technical details are in logs/studio.log.')
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        with lock:
            active.discard(pid)

@app.post('/api/projects/{pid}/render')
def render(pid: str):
    with lock:
        editable(pid)
        project = read(pid)
        if not media.ffmpeg():
            raise HTTPException(400, 'FFmpeg was not found. Install it and restart the backend.')
        if not project['scenes']:
            raise HTTPException(400, 'Add at least one scene first.')
        for index, scene in enumerate(project['scenes']):
            if scene['kind'] != 'title' and not scene['image']:
                raise HTTPException(400, f'Scene {index+1} needs an image.')
        jobid = uuid4().hex
        jobs[jobid] = dict(id=jobid, project_id=pid, status='running', progress=0, message='Preparing scenes...')
        active.add(pid)
        threading.Thread(target=render_job, args=(jobid, project), daemon=True).start()
        return jobs[jobid]

@app.get('/api/jobs/{jobid}')
def get_job(jobid: str):
    if jobid not in jobs:
        raise HTTPException(404, 'Generation job was lost after a restart. Generate the video again.')
    return jobs[jobid]

@app.post('/api/projects/{pid}/open-output')
def open_output(pid: str):
    project = read(pid)
    if not project.get('video') or not (folder(pid) / project['video']).exists():
        raise HTTPException(404, 'Generate a video first.')
    exported = project.get('video_export') or {}
    destination = folder(pid) / 'output'
    if exported.get('video') == project['video']:
        external = Path(exported['path'])
        if not external.is_file():
            raise HTTPException(404, 'The exported video was moved or deleted. Restore it or generate the video again.')
        destination = external.parent
    if os.name == 'nt':
        os.startfile(str(destination))
    return {'path': str(destination)}

DIST = ROOT / 'frontend' / 'dist'
if DIST.exists():
    app.mount('/', StaticFiles(directory=DIST, html=True), name='frontend')
