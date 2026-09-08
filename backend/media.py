"""Media helpers: no shell interpolation; images/captions rendered by Pillow."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageOps
from . import offline_tts
from . import visuals
from .subtitles import cues

VOICES = {
    'en-GB-SoniaNeural': 'Sonia · British female',
    'en-GB-RyanNeural': 'Ryan · British male',
    'en-US-JennyNeural': 'Jenny · American female',
    'en-US-GuyNeural': 'Guy · American male',
}

def ffmpeg():
    return os.environ.get('FFMPEG_PATH') or shutil.which('ffmpeg')

def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=1800,
                            creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(result.stderr[-5000:])
    return result

def audio_duration(path):
    # Decode to PCM to measure accurately without requiring a separate ffprobe.
    result = subprocess.run([ffmpeg(), '-v', 'error', '-i', str(path), '-f', 's16le',
                             '-ac', '1', '-ar', '16000', '-'], capture_output=True, timeout=120,
                            creationflags=0x08000000 if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError('Cannot decode narration audio.')
    return len(result.stdout) / 32000

def signature(scene):
    values = [scene['narration'], scene['voice'], scene['speed']]
    if offline_tts.is_offline(scene['voice']):
        values.append('piper-v1')
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()[:24]

def offline_audio(scene, temporary):
    wave = temporary.with_suffix('.wav')
    try:
        offline_tts.synthesize(scene['narration'], scene['voice'], wave)
        # atempo preserves pitch and gives the percentage slider the same
        # meaning across engines.
        run([ffmpeg(), '-y', '-v', 'error', '-i', str(wave),
             '-af', f"atempo={1 + scene['speed']/100}", '-c:a', 'libmp3lame',
             '-b:a', '128k', str(temporary)])
    finally:
        wave.unlink(missing_ok=True)

async def narrate(scene, folder):
    if not ffmpeg():
        raise ValueError('FFmpeg was not found. Install it and restart the backend.')
    if not scene['narration'].strip():
        raise ValueError('Enter narration text before generating narration.')
    key = signature(scene)
    relative = f'audio/{key}.mp3'
    path = folder / relative
    if not path.exists():
        temporary = path.with_suffix('.tmp.mp3')
        try:
            if offline_tts.is_offline(scene['voice']):
                await asyncio.to_thread(offline_audio, scene, temporary)
            else:
                if scene['voice'] not in VOICES:
                    raise ValueError('Choose an available narration voice.')
                await asyncio.wait_for(edge_tts.Communicate(scene['narration'], scene['voice'],
                                          rate=f"{scene['speed']:+d}%").save(str(temporary)), timeout=90)
            # Validate audio before publishing its cache entry.
            if await asyncio.to_thread(audio_duration, temporary) <= 0:
                raise ValueError('Narration audio is empty. Please regenerate it.')
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    duration = await asyncio.to_thread(audio_duration, path)
    scene.update(audio=relative, audio_key=key, audio_duration=duration)
    if not scene['manual_duration']:
        scene['duration'] = round(duration + 1, 2)
    return scene

def font(size):
    for name in ['C:/Windows/Fonts/segoeui.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)

def lines(text, typeface, width):
    # Pixel wrapping, including long unbroken words.
    result = []
    for paragraph in text.split('\n'):
        line = ''
        for char in paragraph:
            if typeface.getlength(line + char) > width and line:
                result.append(line.rstrip())
                line = ''
            line += char
        result.append(line.rstrip())
    return result

def caption_layer(scene):
    overlay = Image.new('RGBA', (1920, 1080))
    if scene['caption'].strip():
        caption_lines = lines(scene['caption'], font(36), 1680)
        height = len(caption_lines)*48 + 36
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((80, 1010-height, 1840, 1010), 16, fill=(12, 20, 32, 230))
        for index, line in enumerate(caption_lines):
            od.text((960, 1028-height+index*48), line, font=font(36), fill='white', anchor='mt')
    return overlay

def frame(scene, folder, include_caption=True):
    canvas = Image.new('RGB', (1920, 1080), '#101928')
    draw = ImageDraw.Draw(canvas)
    if scene['kind'] == 'title':
        draw.rounded_rectangle((90, 130, 185, 140), radius=5, fill='#61ddb2')
        y = 340
        for line in lines(scene['title'], font(80), 1700):
            draw.text((100, y), line, font=font(80), fill='white')
            y += 100
        for index, line in enumerate(lines(scene.get('subtitle', ''), font(40), 1700)):
            draw.text((100, min(y+30, 760) + index*52), line, font=font(40), fill='#bdc9d9')
        draw.text((100, 950), 'JD TRAINING STUDIO', font=font(25), fill='#61ddb2')
    else:
        with Image.open(folder / scene['image']) as original:
            fitted = ImageOps.contain(ImageOps.exif_transpose(original).convert('RGB'), (1920, 1080))
            canvas.paste(fitted, ((1920-fitted.width)//2, (1080-fitted.height)//2))
        canvas = visuals.annotate(canvas, scene.get('annotations', []), font)
    if include_caption and scene['caption'].strip():
        canvas = Image.alpha_composite(canvas.convert('RGBA'), caption_layer(scene)).convert('RGB')
    return canvas

def render_scene(scene, folder, scratch, index):
    still = scratch / f'{index}.png'
    segment = scratch / f'{index}.mp4'
    frame(scene, folder, include_caption=False).save(still)
    duration = scene['duration']
    fade = min(.3, duration/3)
    args = [ffmpeg(), '-y', '-v', 'error', '-loop', '1', '-framerate', '25', '-i', str(still)]
    if scene.get('audio') and scene.get('audio_key') == signature(scene):
        args += ['-i', str(folder / scene['audio'])]
    else:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    filters = [f for f in [visuals.motion_filter(scene)] if f]
    fades = f'fade=t=in:st=0:d={fade},fade=t=out:st={duration-fade}:d={fade}'
    subtitle_cues = cues(scene)
    subtitle_mode = scene.get('subtitles_enabled') and scene.get('audio_duration')
    if scene['caption'].strip() or subtitle_mode:
        caption = scratch / f'{index}-caption.png'
        if subtitle_mode:
            # A single timed image stream avoids one FFmpeg input per phrase.
            entries = []
            caption_layer({'caption': ''}).save(caption)
            position = 0
            for n, cue in enumerate(subtitle_cues):
                if cue['start'] > position:
                    entries += [f"file '{caption.name}'", 'option framerate 25', f"duration {cue['start']-position:.9f}"]
                layer = scratch / f'{index}-subtitle-{n}.png'
                caption_layer({'caption': cue['text']}).save(layer)
                entries += [f"file '{layer.name}'", 'option framerate 25', f"duration {cue['end']-cue['start']:.9f}"]
                position = cue['end']
            caption_layer({'caption': ''}).save(caption)
            remaining = max(0, duration - position)
            entries += [f"file '{caption.name}'", 'option framerate 25', f'duration {remaining + .08:.9f}', f"file '{caption.name}'"]
            manifest = scratch / f'{index}-subtitles.txt'
            manifest.write_text('\n'.join(entries)+'\n', encoding='utf-8')
            args += ['-f', 'concat', '-safe', '0', '-i', str(manifest)]
        else:
            caption_layer(scene).save(caption)
            args += ['-loop', '1', '-framerate', '25', '-i', str(caption)]
        args += [
                 '-filter_complex_threads', '1', '-filter_complex',
                 f"[0:v]{','.join(filters) if filters else 'null'}[moving];[moving][2:v]overlay=shortest=1,{fades}[v]",
                 '-map', '[v]', '-map', '1:a']
    else:
        args += ['-vf', ','.join(filters + [fades]), '-map', '0:v', '-map', '1:a']
    args += ['-t', str(duration),
             '-af', f'apad,atrim=duration={duration},afade=t=out:st={duration-fade}:d={fade}',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-threads', '2', str(segment)]
    run(args)
    return segment
