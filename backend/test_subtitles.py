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
    custom = {**scene, 'duration': 4, 'subtitle_cues': [
        {'start': .5, 'end': 1.2, 'text': 'First custom phrase'},
        {'start': 2, 'end': 3, 'text': 'Second custom phrase'}]}
    assert cues(custom) == custom['subtitle_cues']
    custom_video = media.render_scene(custom, root, root, 1)
    media.run([media.ffmpeg(), '-v', 'error', '-i', str(custom_video), '-f', 'null', '-'])
    for i, (t, visible) in enumerate([(.35, False), (.8, True), (1.6, False), (2.5, True), (3.5, False)]):
        dest = root/f'custom-{i}.png'
        media.run([media.ffmpeg(), '-y', '-v', 'error', '-ss', str(t), '-i', str(custom_video), '-frames:v', '1', str(dest)])
        pixels=Image.open(dest).convert('RGB').crop((80,860,1840,1010))
        assert any(min(p)>220 for p in pixels.getdata()) == visible, f'Wrong visibility at {t}'
    from pydantic import ValidationError
    from .subtitles import SubtitleCue
    for invalid in [dict(start=2,end=1,text='Bad'),dict(start=float('nan'),end=3,text='Bad')]:
        try:
            SubtitleCue(**invalid)
            raise AssertionError('Invalid timing accepted')
        except ValidationError:
            pass
    print('PASS: custom timing, leading/internal/trailing gaps, real export, invalid intervals')
    import os
    os.environ['JD_PROJECTS_DIR'] = str(root/'api')
    from fastapi.testclient import TestClient
    from .main import app, Scene
    with TestClient(app) as client:
        project=client.post('/api/projects', json={'title':'Timing persistence','opening':False}).json()
        project['scenes']=[Scene(kind='title', narration='Original speech', subtitle_cues=custom['subtitle_cues']).model_dump()]
        url='/api/projects/'+project['id']
        saved=client.put(url,json=project)
        assert saved.status_code==200, saved.text
        project=client.get(url).json()
        assert project['scenes'][0]['subtitle_cues']==custom['subtitle_cues']
        project['scenes'][0]['subtitle_cues'][1]['start']=1
        assert client.put(url,json=project).status_code==422
        project=client.get(url).json()
        project['scenes'][0]['narration']='Changed speech'
        assert client.put(url,json=project).json()['scenes'][0]['subtitle_cues'] is None
    print('PASS: saved/reopened custom cues, overlap rejection, narration edit resets timing')


if __name__ == '__main__':
    main()
