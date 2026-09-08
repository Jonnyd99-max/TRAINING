"""Media helpers: no shell interpolation; images/captions rendered by Pillow."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageOps

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
    return hashlib.sha256(json.dumps([scene['narration'], scene['voice'], scene['speed']]).encode()).hexdigest()[:24]

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
            await asyncio.wait_for(edge_tts.Communicate(scene['narration'], scene['voice'],
                                      rate=f"{scene['speed']:+d}%").save(str(temporary)), timeout=90)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    duration = audio_duration(path)
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

def frame(scene, folder):
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
        draw = ImageDraw.Draw(canvas)
    if scene['caption'].strip():
        caption_lines = lines(scene['caption'], font(36), 1680)
        height = len(caption_lines)*48 + 36
        overlay = Image.new('RGBA', canvas.size)
        od = ImageDraw.Draw(overlay)
        od.rounded_rectangle((80, 1010-height, 1840, 1010), 16, fill=(12, 20, 32, 230))
        for index, line in enumerate(caption_lines):
            od.text((960, 1028-height+index*48), line, font=font(36), fill='white', anchor='mt')
        canvas = Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')
    return canvas

def render_scene(scene, folder, scratch, index):
    still = scratch / f'{index}.png'
    segment = scratch / f'{index}.mp4'
    frame(scene, folder).save(still)
    duration = scene['duration']
    fade = min(.3, duration/3)
    args = [ffmpeg(), '-y', '-v', 'error', '-loop', '1', '-framerate', '25', '-i', str(still)]
    if scene.get('audio') and scene.get('audio_key') == signature(scene):
        args += ['-i', str(folder / scene['audio'])]
    else:
        args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    args += ['-t', str(duration), '-vf', f'fade=t=in:st=0:d={fade},fade=t=out:st={duration-fade}:d={fade}',
             '-af', f'apad,atrim=duration={duration},afade=t=out:st={duration-fade}:d={fade}',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-threads', '2', str(segment)]
    run(args)
    return segment
