"""Real annotation/motion export regression test: python -m backend.test_visuals."""
import io
import os
from pathlib import Path
import time
from uuid import uuid4
from PIL import Image, ImageDraw, ImageStat

TEST_ROOT=Path(__file__).resolve().parent.parent/'test-results'/('visuals-'+uuid4().hex)
os.environ['JD_PROJECTS_DIR']=str(TEST_ROOT)
os.environ['JD_VIDEO_OUTPUT_DIR']=str(TEST_ROOT/'exports')
from fastapi.testclient import TestClient
from .main import app, Scene, media

def main():
    with TestClient(app) as client:
        def ok(r):
            assert r.status_code==200,r.text
            return r.json()
        assert ok(client.get('/api/health'))['ffmpeg']
        p=ok(client.post('/api/projects',json={'title':'Annotations and camera test','opening':False}))
        directory=TEST_ROOT/p['id']
        original=Image.new('RGB',(1920,1080),'#407dc0');d=ImageDraw.Draw(original)
        d.rectangle((960,0,1919,1079),fill='#51a577')
        for x in range(100,680,12):d.rectangle((x,110,x+5,320),fill='white')
        d.text((1200,170),'PRIVATE DETAILS',font=media.font(44),fill='white')
        raw=io.BytesIO();original.save(raw,'PNG')
        uploaded=ok(client.post(f'/api/projects/{p["id"]}/images',files={'file':('screen.png',raw.getvalue(),'image/png')}))
        def a(kind,x,y,x2,y2,**more):
            return dict(id=uuid4().hex,type=kind,x=x,y=y,x2=x2,y2=y2,color='#facc15',number=1,**more)
        annotations=[a('blur',.05,.1,.36,.3),a('cover',.6,.1,.92,.3),a('highlight',.1,.5,.3,.7),
                     a('arrow',.4,.6,.6,.6),a('number',.75,.75,.75,.75)]
        scene=Scene(title='Follow this field',image=uploaded['image'],duration=2.4,manual_duration=True,
                    caption='Keep this instruction fixed on screen.',annotations=annotations,
                    camera={'enabled':True,'start':{'zoom':1,'x':.5,'y':.5},'end':{'zoom':2,'x':.75,'y':.5}}).model_dump()
        p['scenes']=[scene]
        p=ok(client.put('/api/projects/'+p['id'],json=p))
        reopened=ok(client.get('/api/projects/'+p['id']))
        assert reopened['scenes'][0]['annotations']==scene['annotations']
        assert reopened['scenes'][0]['camera']==scene['camera']
        bad={**p,'scenes':[{**scene,'camera':{'enabled':True,'start':{'zoom':99},'end':{}}}]}
        assert client.put('/api/projects/'+p['id'],json=bad).status_code==422
        bad={**p,'scenes':[{**scene,'annotations':[{**annotations[0],'x':-1}]}]}
        assert client.put('/api/projects/'+p['id'],json=bad).status_code==422
        composed=media.frame(scene,directory,include_caption=False)
        composed.save(TEST_ROOT/'annotated-frame.png')
        assert composed.getpixel((1300,200))==(16,25,40),'Solid cover did not hide source'
        assert sum(ImageStat.Stat(composed.crop((150,140,600,280))).stddev)<sum(ImageStat.Stat(original.crop((150,140,600,280))).stddev)/3,'Blur did not soften details'
        assert composed.getpixel((192,600))==(250,204,21),'Highlight border missing'
        assert composed.getpixel((1100,648))==(250,204,21),'Arrow missing'
        assert composed.getpixel((1464,810))==(250,204,21),'Step marker missing'
        job=ok(client.post('/api/projects/'+p['id']+'/render'))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            job=ok(client.get('/api/jobs/'+job['id']))
            if job['status']!='running':break
            time.sleep(.15)
        assert job['status']=='complete',job
        p=ok(client.get('/api/projects/'+p['id']))
        video=directory/p['video']
        media.run([media.ffmpeg(),'-v','error','-i',str(video),'-f','null','-'])
        media.run([media.ffmpeg(),'-y','-v','error','-i',str(video),'-vf',"select='eq(n,10)+eq(n,60)'",'-vsync','0',str(TEST_ROOT/'motion-%02d.png')])
        first=Image.open(TEST_ROOT/'motion-01.png').convert('RGB')
        last=Image.open(TEST_ROOT/'motion-02.png').convert('RGB')
        assert first.size==last.size==(1920,1080)
        before,after=first.getpixel((300,850)),last.getpixel((300,850))
        assert before[2]>before[1] and after[1]>after[2],(before,after)
        def text_bounds(image):
            mask=Image.new('1',(1920,1080))
            for y in range(925,1010):
                for x in range(80,1840):
                    if min(image.getpixel((x,y)))>225:mask.putpixel((x,y),1)
            return mask.getbbox()
        assert text_bounds(first)==text_bounds(last) and text_bounds(first),'Caption moved with camera'
        assert Path(p['video_export']['path']).is_file(),'Custom output copy missing'
        # Old scenes without new fields still normalize to a plain static image.
        old={k:v for k,v in scene.items() if k not in {'annotations','camera'}}
        normalized=Scene(**old).model_dump()
        assert normalized['annotations']==[] and not normalized['camera']['enabled']
        print('PASS: saved annotations/camera, invalid input checks, blur/cover/arrow/highlight/step pixels, actual zoom/pan MP4, anchored captions, full decode, custom output copy, legacy defaults.')
        print('Visual QA files:',TEST_ROOT)

if __name__=='__main__':main()
