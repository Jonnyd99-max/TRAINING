"""Timed overlays and multi-scene constant-frame-rate MP4 regression."""
import io
import os
import re
import time
from pathlib import Path
from uuid import uuid4
from PIL import Image, ImageDraw, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parent.parent/'test-results'/('annotation-timing-'+uuid4().hex)
os.environ['JD_PROJECTS_DIR'] = str(ROOT)
os.environ['JD_VIDEO_OUTPUT_DIR'] = str(ROOT/'exports')
from fastapi.testclient import TestClient
from .main import app, Scene, media
from .visuals import visible_at


def main():
    with TestClient(app) as client:
        def ok(r):
            assert r.status_code == 200, r.text
            return r.json()
        p = ok(client.post('/api/projects', json={'title':'Timing and smooth playback', 'opening':False}))
        directory = ROOT/p['id']
        original=Image.new('RGB',(1920,1080),'#708090')
        d=ImageDraw.Draw(original)
        for x in range(1100,1500,10):
            d.rectangle((x,120,x+4,340),fill='white')
        data=io.BytesIO();original.save(data,'PNG')
        uploaded=ok(client.post(f'/api/projects/{p["id"]}/images',files={'file':('timing.png',data.getvalue(),'image/png')}))
        def a(kind,x,y,x2,y2,**kwargs):
            return dict(id=uuid4().hex,type=kind,x=x,y=y,x2=x2,y2=y2,color='#facc15',number=1,start=.5,end=1.5,**kwargs)
        annotations=[a('highlight',.05,.1,.22,.3),a('arrow',.27,.15,.45,.3),a('number',.5,.6,.5,.6),
                     a('blur',.57,.11,.79,.32),a('cover',.82,.1,.95,.3)]
        scene=Scene(image=uploaded['image'],duration=3.2,manual_duration=True,annotations=annotations,caption='Fixed caption').model_dump()
        scene['annotations'].append({**annotations[-1], 'id':uuid4().hex,'start':2.2,'end':None,'y':.5,'y2':.7})
        p['scenes']=[scene,Scene(image=uploaded['image'],duration=1.37,manual_duration=True,
            camera={'enabled':True,'start':{'zoom':1,'x':.5,'y':.5},'end':{'zoom':1.1,'x':.55,'y':.5}}).model_dump()]
        url='/api/projects/'+p['id']
        p=ok(client.put(url,json=p))
        assert ok(client.get(url))['scenes'][0]['annotations']==scene['annotations']
        bad={**p,'scenes':[{**scene,'annotations':[{**annotations[0],'end':.4}]}]}
        assert client.put(url,json=bad).status_code==422
        assert visible_at(annotations[0],.5) and not visible_at(annotations[0],1.5)
        legacy={k:v for k,v in annotations[0].items() if k not in {'start','end'}}
        assert visible_at(legacy,0) and visible_at(legacy,50)
        job=ok(client.post(url+'/render'))
        deadline=time.monotonic()+120
        while job['status']=='running' and time.monotonic()<deadline:
            time.sleep(.2);job=ok(client.get('/api/jobs/'+job['id']))
        assert job['status']=='complete',job
        p=ok(client.get(url));video=directory/p['video']
        result=media.run([media.ffmpeg(),'-hide_banner','-i',str(video),'-vf','showinfo','-f','null','-'])
        times=[float(t) for t in re.findall(r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([\d.]+)',result.stderr)]
        assert len(times)>130, len(times)
        assert all(abs((b-a)-1/30)<.0001 for a,b in zip(times,times[1:])), 'Uneven frame spacing at scene join'
        assert '30 fps' in result.stderr and 'yuv420p' in result.stderr
        plain=media.frame({**scene,'annotations':[]},directory,False)
        annotated=media.frame({**scene,'annotations':annotations},directory,False)
        regions=[(85,100,430,335),(495,140,880,335),(918,605,1005,695),(1100,130,1490,330),(1590,120,1800,315)]
        def distance(first,second,region):
            return sum(ImageStat.Stat(ImageChops.difference(first.crop(region),second.crop(region))).mean)
        for i,(t,active) in enumerate([(.35,False),(1,True),(1.85,False),(2.6,False)]):
            path=ROOT/f'frame-{i}.png'
            media.run([media.ffmpeg(),'-y','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1',str(path)])
            image=Image.open(path).convert('RGB')
            for region in regions:
                assert (distance(image,annotated,region)<distance(image,plain,region))==active,(t,region)
            if t==2.6:
                assert max(image.getpixel((1700,650)))<45, 'Until-end cover absent'
        print('PASS: all five timed annotations, entry/exit, until-end, legacy defaults, validation, save/reopen, actual multi-scene MP4, uniform 30 fps across joins, full decode')
        print(video)
        moving={**scene,'camera':p['scenes'][1]['camera'],'annotations':[
            {**annotations[-1],'x':.4,'x2':.6,'y':.4,'y2':.6}]}
        clip=media.render_scene(moving,directory,ROOT,99)
        for i,(t,active) in enumerate([(.35,False),(1,True),(2,False)]):
            path=ROOT/f'moving-{i}.png'
            media.run([media.ffmpeg(),'-y','-v','error','-ss',str(t),'-i',str(clip),'-frames:v','1',str(path)])
            pixel=Image.open(path).convert('RGB').getpixel((960,540))
            assert (max(pixel)<45)==active, (t,pixel)
        print('PASS: timed cover remains attached while camera moves')


if __name__=='__main__':main()
