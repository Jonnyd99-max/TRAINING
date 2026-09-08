import Subtitles from './Subtitles.jsx';
import React, {useEffect,useMemo,useRef,useState} from 'react';
import {W,H,defaultCamera,clamp,cameraAt,prepareVisual,drawViewport,hit} from './visuals.js';

const TOOLS=[['select','Move / resize'],['arrow','Arrow'],['highlight','Highlight'],['number','Step'],['blur','Blur'],['cover','Cover']];
const EMPTY=[];
const uid=()=>crypto.randomUUID().replaceAll('-','');
export default function VisualWorkspace({scene,src,locked,playing,elapsed,onChange,onError}) {
  const [image,setImage]=useState(null),[mode,setMode]=useState('annotate'),[tool,setTool]=useState('select');
  const [selected,setSelected]=useState(null),[color,setColor]=useState('#facc15'),[endpoint,setEndpoint]=useState('end');
  const [draft,setDraft]=useState(null);
  const [previewing,setPreviewing]=useState(false);
  const canvas=useRef(null),gesture=useRef(null);
  const annotations=scene.annotations||EMPTY,camera=scene.camera||defaultCamera();
  const active=annotations.find(a=>a.id===selected);
  useEffect(()=>{if(playing)setPreviewing(true);},[playing]);
  useEffect(()=>{
    let disposed=false;const img=new Image();
    img.onload=()=>{if(!disposed)setImage(img);};
    img.onerror=()=>{if(!disposed)onError('A scene image is missing. Upload it again.');};img.src=src;
    return()=>{disposed=true;};
  },[src]);
  const shown=useMemo(()=>draft ? [...annotations.filter(a=>a.id!==draft.id),draft] : annotations,[annotations,draft]);
  const base=useMemo(()=>image?prepareVisual(image,shown):null,[image,shown]);
  const progress=clamp(Math.floor(elapsed*25)/Math.max(1,Math.ceil(scene.duration*25)-1));
  const view=playing||(previewing&&elapsed>0)?cameraAt(camera,progress):mode==='camera'&&camera.enabled?camera[endpoint]:{zoom:1,x:.5,y:.5};
  useEffect(()=>{
    if(!base||!canvas.current)return;
    const ctx=canvas.current.getContext('2d');drawViewport(ctx,base,view);
    if(mode==='annotate'&&!playing&&selected){
      const a=shown.find(a=>a.id===selected);if(!a)return;
      ctx.save();ctx.strokeStyle='#fff';ctx.fillStyle='#176f59';ctx.lineWidth=3;
      const points=a.type==='number'?[[a.x*W,a.y*H]]:[[a.x*W,a.y*H],[a.x2*W,a.y2*H]];
      for(const [x,y] of points){ctx.fillRect(x-9,y-9,18,18);ctx.strokeRect(x-9,y-9,18,18);}ctx.restore();
    }
  },[base,view.zoom,view.x,view.y,mode,playing,selected,shown]);
  const point=e=>{const r=canvas.current.getBoundingClientRect();return{x:clamp((e.clientX-r.left)/r.width),y:clamp((e.clientY-r.top)/r.height)};};
  const commit=a=>onChange({annotations:annotations.some(v=>v.id===a.id)?annotations.map(v=>v.id===a.id?a:v):[...annotations,a]});
  const setView=values=>onChange({camera:{...camera,[endpoint]:{...camera[endpoint],...values}}});
  function down(e){
    if(locked||playing||!image||e.button!==0)return;
    if(previewing&&elapsed>0){setPreviewing(false);return;}
    setPreviewing(false);
    e.preventDefault();const p=point(e);canvas.current.setPointerCapture?.(e.pointerId);
    if(mode==='camera'){
      if(camera.enabled)gesture.current={kind:'pan',start:p,view:{...camera[endpoint]},latest:null};return;
    }
    if(tool!=='select'){
      if(annotations.length>=40)return;
      const a={id:uid(),type:tool,x:p.x,y:p.y,x2:p.x,y2:p.y,color,number:Math.min(99,1+Math.max(0,...annotations.filter(v=>v.type==='number').map(v=>v.number)))};
      setSelected(a.id);
      if(tool==='number'){commit(a);setTool('select');return;}
      gesture.current={kind:'draw',start:p,original:a,latest:a};setDraft(a);return;
    }
    if(active&&active.type!=='number'){
      for(const end of [1,2]){const x=end===1?active.x:active.x2,y=end===1?active.y:active.y2;
        if(Math.hypot((p.x-x)*W,(p.y-y)*H)<30){gesture.current={kind:'resize',handle:end,start:p,original:active,latest:active};return;}
      }
    }
    const picked=[...annotations].reverse().find(a=>hit(a,p));setSelected(picked?.id||null);
    if(picked)gesture.current={kind:'move',start:p,original:picked,latest:picked};
  }
  function move(e){
    const g=gesture.current;if(!g||locked||playing)return;const p=point(e);
    if(g.kind==='pan'){
      const view={...g.view,x:clamp(g.view.x-(p.x-g.start.x)/g.view.zoom),y:clamp(g.view.y-(p.y-g.start.y)/g.view.zoom)};
      g.latest=view;setView(view);return;
    }
    let a={...g.original};
    if(g.kind==='draw'||g.kind==='resize'){
      if(g.handle===1){a.x=p.x;a.y=p.y;}else{a.x2=p.x;a.y2=p.y;}
    }else{
      const dx=clamp(p.x-g.start.x,-Math.min(a.x,a.x2),1-Math.max(a.x,a.x2)),dy=clamp(p.y-g.start.y,-Math.min(a.y,a.y2),1-Math.max(a.y,a.y2));
      a={...a,x:a.x+dx,x2:a.x2+dx,y:a.y+dy,y2:a.y2+dy};
    }
    g.latest=a;setDraft(a);
  }
  function up(){
    const g=gesture.current;gesture.current=null;setDraft(null);if(!g||g.kind==='pan')return;
    const a=g.latest,valid=a.type==='arrow'?Math.hypot((a.x2-a.x)*W,(a.y2-a.y)*H)>=5:a.type==='number'||(Math.abs(a.x2-a.x)>=.002&&Math.abs(a.y2-a.y)>=.002);
    if(valid)commit(a);else if(g.kind==='draw')setSelected(null);
    if(g.kind==='draw')setTool('select');
  }
  const fade=playing?Math.max(0,Math.min(1,elapsed/.3,(scene.duration-elapsed)/.3)):1;
  return <>
    <div className="previewstage"><div className="preview" style={{opacity:fade}}>
      <canvas ref={canvas} width={W} height={H} className="visualcanvas" aria-label="Screenshot annotation canvas" tabIndex={0}
        style={{cursor:locked||playing?'default':mode==='camera'?'grab':tool==='select'?'move':'crosshair'}}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={()=>{gesture.current=null;setDraft(null);}}
        onKeyDown={e=>{if((e.key==='Delete'||e.key==='Backspace')&&selected&&!locked&&!playing){e.preventDefault();onChange({annotations:annotations.filter(a=>a.id!==selected)});setSelected(null);}}}/>
      {!image&&<div className="visualLoading">Loading screenshot…</div>}
      {scene.subtitles_enabled && scene.audio_duration ? <Subtitles scene={scene} elapsed={elapsed}/> : scene.caption&&<div className="caption">{scene.caption}</div>}
    </div></div>
    <fieldset className="visualtools" disabled={locked||playing} onPointerDownCapture={()=>setPreviewing(false)} onKeyDownCapture={()=>setPreviewing(false)}>
      <div className="visualtabs"><button className={mode==='annotate'?'active':''} onClick={()=>setMode('annotate')}>Annotations</button><button className={mode==='camera'?'active':''} onClick={()=>setMode('camera')}>Zoom &amp; pan</button></div>
      {mode==='annotate'?<>
        <div className="toolrow">{TOOLS.map(([id,label])=><button key={id} className={tool===id?'active':''} disabled={id!=='select'&&annotations.length>=40} onClick={()=>{setTool(id);setSelected(null);}}>{label}</button>)}</div>
        <p className="toolhint">Edit on the full screenshot. Drag to draw; click to place a step. Select a shape to move it or drag its square handles to resize.</p>
        <div className="annotationproperties"><label>Selected annotation<select value={selected||''} onChange={e=>{setSelected(e.target.value||null);setTool('select');}}><option value="">None selected</option>{annotations.map((a,i)=><option key={a.id} value={a.id}>{i+1}. {a.type==='number'?`Step ${a.number}`:a.type}</option>)}</select></label>
          <label>Colour<input type="color" value={active?.color||color} onChange={e=>{setColor(e.target.value);if(active)commit({...active,color:e.target.value});}}/></label>
          {active?.type==='number'&&<label>Step number<input type="number" min="1" max="99" value={active.number} onChange={e=>commit({...active,number:clamp(Number(e.target.value)||1,1,99)})}/></label>}
          <button disabled={!active} onClick={()=>{onChange({annotations:annotations.filter(a=>a.id!==selected)});setSelected(null);}}>Delete annotation</button>
        </div>
        <p className="toolhint">Blur softens details. Use Cover to fully hide sensitive text in the video. Your original project image is retained.</p>
      </>:<>
        <label className="checkbox"><input type="checkbox" checked={camera.enabled} onChange={e=>onChange({camera:{...camera,enabled:e.target.checked}})}/>Enable zoom and pan</label>
        <div className="toolrow"><button className={endpoint==='start'?'active':''} onClick={()=>setEndpoint('start')}>Start view</button><button className={endpoint==='end'?'active':''} onClick={()=>setEndpoint('end')}>End view</button><button onClick={()=>onChange({camera:defaultCamera()})}>Reset framing</button></div>
        <div className="cameracontrols"><label>Zoom <span>{camera[endpoint].zoom.toFixed(2)}×</span><input disabled={!camera.enabled} aria-label="Camera zoom" type="range" min="1" max="3" step="0.05" value={camera[endpoint].zoom} onChange={e=>setView({zoom:Number(e.target.value)})}/></label>
          <label>Horizontal focus <span>{Math.round(camera[endpoint].x*100)}%</span><input disabled={!camera.enabled} aria-label="Camera horizontal focus" type="range" min="0" max="1" step="0.01" value={camera[endpoint].x} onChange={e=>setView({x:Number(e.target.value)})}/></label>
          <label>Vertical focus <span>{Math.round(camera[endpoint].y*100)}%</span><input disabled={!camera.enabled} aria-label="Camera vertical focus" type="range" min="0" max="1" step="0.01" value={camera[endpoint].y} onChange={e=>setView({y:Number(e.target.value)})}/></label></div>
        <p className="toolhint">Set the start and end framing, or drag the zoomed screenshot to pan. Play previews the smooth movement. Matching views give a fixed close-up.</p>
      </>}
    </fieldset>
  </>;
}
