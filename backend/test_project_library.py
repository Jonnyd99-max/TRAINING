"""Isolated destructive-operation tests; never targets real projects or exports."""
import os
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parent.parent/'test-results'/('library-'+uuid4().hex)
os.environ['JD_PROJECTS_DIR']=str(ROOT/'projects')
os.environ['JD_VIDEO_OUTPUT_DIR']=str(ROOT/'Training output')
from fastapi.testclient import TestClient
from . import main


def run():
    with TestClient(main.app) as client:
        def create(title):
            response=client.post('/api/projects',json={'title':title,'opening':False})
            assert response.status_code==200,response.text
            return response.json()
        p=create('Disposable project');other=create('Keep this project')
        path=main.folder(p['id']);url='/api/projects/'+p['id']
        moved=client.put(url+'/organization',json={'folder':'  Production   training  ','revision':p['revision']})
        assert moved.status_code==200,moved.text
        p=moved.json();assert p['folder']=='Production training'
        assert client.get(url).json()['folder']==p['folder']
        assert next(x for x in client.get('/api/projects').json() if x['id']==p['id'])['folder']==p['folder']
        saved=client.put(url,json=p);assert saved.status_code==200
        p=saved.json();assert p['folder']=='Production training'
        deletion={'confirm_title':p['title'],'revision':p['revision']}
        assert client.request('DELETE',url,json={**deletion,'confirm_title':'wrong'}).status_code==400
        assert client.request('DELETE',url,json={**deletion,'revision':0}).status_code==409
        main.active.add(p['id'])
        assert client.request('DELETE',url,json=deletion).status_code==409
        main.active.remove(p['id'])
        assert client.request('DELETE',url,json=deletion,headers={'Origin':'https://example.org'}).status_code==403
        external=ROOT/'Training output';external.mkdir();export=external/'Keep.mp4';export.write_bytes(b'finished video')
        for relative in ['images/source.png','audio/speech.mp3','output/internal.mp4']:
            (path/relative).write_bytes(b'test-only local file')
        # Even metadata referencing an external export is never followed by deletion.
        p['video_export']={'path':str(export)};main.write(p)
        old=os.environ['JD_VIDEO_OUTPUT_DIR'];os.environ['JD_VIDEO_OUTPUT_DIR']=str(path/'output')
        assert client.request('DELETE',url,json=deletion).status_code==400
        os.environ['JD_VIDEO_OUTPUT_DIR']=old
        assert client.request('DELETE',url,json=deletion).status_code==200
        assert not path.exists()
        assert export.read_bytes()==b'finished video'
        assert main.folder(other['id']).exists()
        assert client.get(url).status_code==404
        assert client.put(url,json=p).status_code==404, 'Stale editor recreated deleted project'
        assert all(x['id']!=p['id'] for x in client.get('/api/projects').json())
        # Verify legacy projects and moving back out of a folder.
        assert next(x for x in client.get('/api/projects').json() if x['id']==other['id'])['folder']==''
        assert client.put('/api/projects/'+other['id']+'/organization',json={'folder':'','revision':0}).status_code==200
    with TestClient(main.app) as client:
        assert client.get(url).status_code==404
    print('PASS: folders persist, local files deleted, external export and other project preserved, confirmation/revision/active-job/origin checks, nested export protection, stale save rejected, no resurrection on restart')
    print(ROOT)


if __name__=='__main__':run()
