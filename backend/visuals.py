"""Screenshot annotations and camera motion in a shared 1920x1080 space."""
import math
from uuid import uuid4
from typing import Literal
from PIL import Image, ImageDraw, ImageFilter
from pydantic import BaseModel, ConfigDict, Field, model_validator

WIDTH, HEIGHT = 1920, 1080
FPS = 30

class Annotation(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r'^[a-f0-9]{32}$')
    type: Literal['arrow', 'highlight', 'number', 'blur', 'cover']
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    color: str = Field(default='#facc15', pattern=r'^#[a-fA-F0-9]{6}$')
    number: int = Field(default=1, ge=1, le=99)
    start: float = Field(default=0, ge=0, le=3600)
    end: float | None = Field(default=None, gt=0, le=3600)

    @model_validator(mode='after')
    def nonempty(self):
        if self.end is not None and self.end <= self.start:
            raise ValueError('Annotation exit must be after its entry time.')
        if self.type in {'highlight', 'blur', 'cover'} and (abs(self.x2-self.x) < .002 or abs(self.y2-self.y) < .002):
            raise ValueError('Draw a larger annotation rectangle.')
        if self.type == 'arrow' and math.hypot((self.x2-self.x)*WIDTH, (self.y2-self.y)*HEIGHT) < 5:
            raise ValueError('Draw a longer arrow.')
        return self

class CameraPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    zoom: float = Field(default=1, ge=1, le=3)
    x: float = Field(default=.5, ge=0, le=1)
    y: float = Field(default=.5, ge=0, le=1)

class CameraMotion(BaseModel):
    enabled: bool = False
    start: CameraPoint = Field(default_factory=CameraPoint)
    end: CameraPoint = Field(default_factory=CameraPoint)

def rect(a):
    return (round(min(a['x'], a['x2'])*WIDTH), round(min(a['y'], a['y2'])*HEIGHT),
            round(max(a['x'], a['x2'])*WIDTH), round(max(a['y'], a['y2'])*HEIGHT))

def annotate(canvas, annotations, font):
    # Privacy regions are composited before callouts and BEFORE camera motion.
    # No later frame can reveal the underlying screenshot through a moving blur.
    original = canvas.copy()
    blurred = original.filter(ImageFilter.GaussianBlur(24)) if any(a['type'] == 'blur' for a in annotations) else None
    for a in annotations:
        if a['type'] == 'blur':
            box = rect(a)
            canvas.paste(blurred.crop(box), box)
    draw = ImageDraw.Draw(canvas)
    for a in annotations:
        if a['type'] == 'cover':
            draw.rectangle(rect(a), fill='#101928')
    overlay = Image.new('RGBA', canvas.size)
    draw = ImageDraw.Draw(overlay)
    for a in annotations:
        color = a['color']
        x, y, x2, y2 = a['x']*WIDTH, a['y']*HEIGHT, a['x2']*WIDTH, a['y2']*HEIGHT
        if a['type'] == 'highlight':
            rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            draw.rectangle(rect(a), fill=(*rgb, 38), outline=color, width=6)
        elif a['type'] == 'arrow':
            angle = math.atan2(y2-y, x2-x)
            length = min(34, math.hypot(x2-x, y2-y)*.6)
            bx, by = x2-length*math.cos(angle), y2-length*math.sin(angle)
            draw.line((x, y, bx, by), fill='#101928', width=12)
            draw.line((x, y, bx, by), fill=color, width=8)
            draw.polygon([(x2, y2), (bx-14*math.sin(angle), by+14*math.cos(angle)),
                          (bx+14*math.sin(angle), by-14*math.cos(angle))], fill=color)
        elif a['type'] == 'number':
            draw.ellipse((x-34, y-34, x+34, y+34), fill=color, outline='#101928', width=3)
            draw.text((x, y), str(a['number']), font=font(36), fill='#101928', anchor='mm')
    return Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')

def visible_at(annotation, seconds):
    return seconds >= annotation.get('start', 0) and (annotation.get('end') is None or seconds < annotation['end'])


def annotation_intervals(scene):
    duration = scene['duration']
    boundaries = {0, duration}
    for a in scene.get('annotations', []):
        for value in (a.get('start', 0), a.get('end')):
            if value is not None and 0 < value < duration:
                boundaries.add(value)
    times = sorted(boundaries)
    return [(start, end, [a for a in scene.get('annotations', []) if visible_at(a, start)])
            for start, end in zip(times, times[1:])]


def motion_filter(scene):
    camera = scene.get('camera') or {}
    if not camera.get('enabled') or scene.get('kind') != 'image':
        return None
    a, b = camera['start'], camera['end']
    frames = max(1, math.ceil(scene['duration']*FPS)-1)
    t = f'min(1,on/{frames})'
    ease = f'({t})*({t})*(3-2*({t}))'
    def interpolate(key):
        return f"({a[key]}+({b[key]}-{a[key]})*({ease}))"
    zoom = interpolate('zoom')
    x = f"max(0,min(iw-iw/zoom,iw*{interpolate('x')}-iw/zoom/2))"
    y = f"max(0,min(ih-ih/zoom,ih*{interpolate('y')}-ih/zoom/2))"
    # A larger working image reduces integer crop-position stepping during slow pans.
    return f"scale=3840:2160:flags=bicubic,zoompan=z='{zoom}':x='{x}':y='{y}':d=1:s=1920x1080:fps={FPS}"
