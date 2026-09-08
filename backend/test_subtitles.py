"""Real offline narration/subtitle export regression: python -m backend.test_subtitles."""
import asyncio
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageChops
from . import media
from .subtitles import cues


def main():
    root = Path(__file__).resolve().parent.parent / 'test-results' / ('subtitles-'+uuid4().hex)
    root.mkdir(parents=True)
    (root/'audio').mkdir()
    scene = dict(kind='title', title='Subtitle verification', subtitle='', caption='Static caption retained',
                 narration='Check the highlighted field. Then select the next training step.',
                 voice='piper:en_GB-northern_english_male-medium', speed=0,
                 manual_duration=False, duration=5, subtitles_enabled=True)
    asyncio.run(media.narrate(scene, root))
    timeline = cues(scene)
    assert len(timeline) == 2 and timeline[0]['start'] == 0
    assert timeline[-1]['end'] == scene['audio_duration']
    assert cues({**scene, 'subtitles_enabled': False}) == []
    assert cues({**scene, 'audio_duration': None}) == []
    assert cues({**scene, 'narration': ''}) == []
    assert cues({**scene, 'duration': .5})[-1]['end'] == .5
    video = media.render_scene(scene, root, root, 0)
    media.run([media.ffmpeg(), '-v', 'error', '-i', str(video), '-f', 'null', '-'])
    images=[]
    for i, t in enumerate([(c['start']+c['end'])/2 for c in timeline]+[scene['audio_duration']+.5]):
        dest=root/f'check-{i}.png'
        media.run([media.ffmpeg(), '-y', '-v', 'error', '-ss', str(t), '-i', str(video), '-frames:v', '1', str(dest)])
        images.append(Image.open(dest).convert('RGB').crop((80,860,1840,1010)))
    assert ImageChops.difference(images[0],images[1]).getbbox(), 'Subtitle did not change'
    # The blank tail must have no white subtitle text.
    assert any(min(p)>220 for p in images[0].getdata())
    assert not any(min(p)>220 for p in images[2].getdata()), 'Subtitle remained after speech'
    print('PASS: offline speech, changing subtitles, silent tail, full MP4 decode, disabled/empty/clipped timing')
    print(video)


if __name__ == '__main__':
    main()
