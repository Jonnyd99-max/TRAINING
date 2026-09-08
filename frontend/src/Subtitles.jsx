import React, {useEffect,useState} from 'react';

export function subtitleCues(scene) {
  if(!scene?.subtitles_enabled || !scene.audio_duration)return [];
  if(scene.subtitle_cues!=null)return scene.subtitle_cues.map(c=>({...c,end:Math.min(c.end,scene.duration)})).filter(c=>c.start<c.end);
  const phrases=[];let current='';
  for(const word of scene.narration.trim().split(/\s+/).filter(Boolean)) {
    for(let i=0;i<word.length;i+=42){const token=word.slice(i,i+42);
      if(current&&current.length+token.length+1>84){phrases.push(current);current='';}
      current=(current+' '+token).trim();
      if(/[.!?;:]$/.test(token)||current.split(/\s+/).length>=12){phrases.push(current);current='';}
    }
  }
  if(current)phrases.push(current);
  const total=phrases.reduce((n,p)=>n+p.length,0);let position=0;
  return phrases.map(text=>{const start=position/total*scene.audio_duration;position+=text.length;return {start,end:Math.min(position/total*scene.audio_duration,scene.duration),text};}).filter(c=>c.start<c.end);
}

export default function Subtitles({scene,elapsed}){
  const cue=subtitleCues(scene).find(c=>elapsed>=c.start&&elapsed<c.end);
  return cue?<div className="narrationSubtitle">{cue.text}</div>:null;
}

export function SubtitleTiming({scene,onChange,onSeek,elapsed}) {
  const [draft,setDraft]=useState([]),[error,setError]=useState(''),[edited,setEdited]=useState(false);
  useEffect(()=>{setDraft((scene.subtitle_cues??subtitleCues(scene)).map(c=>({...c})));setEdited(false);setError('');},[scene.id,scene.subtitle_cues,scene.audio_duration,scene.duration]);
  if(!scene.subtitles_enabled||!scene.audio_duration)return null;
  const update=(i,values)=>{setDraft(draft.map((c,n)=>n===i?{...c,...values}:c));setEdited(true);setError('');};
  function apply(){
    let previous=0;
    const values=draft.map(c=>({...c,start:Number(c.start),end:Number(c.end),text:c.text.trim()}));
    for(const c of values){if(!Number.isFinite(c.start)||!Number.isFinite(c.end)||c.start<previous||c.end<=c.start||c.end>3600||!c.text||c.text.length>84){setError('Use ordered, non-overlapping times: end must follow start, with text in every phrase (maximum 84 characters).');return;}previous=c.end;}
    onChange({subtitle_cues:values});setEdited(false);
  }
  return <div className="subtitleTiming"><h3>Subtitle timing</h3><p className="hint">Times are seconds from this scene’s start. Scrub or play, pause, then use the current time. Apply edits before previewing them.</p><p>{elapsed.toFixed(2)} s · {scene.subtitle_cues==null?'Estimated timing':'Custom timing'}</p>
    <div className="cueList">{draft.map((c,i)=><div className="cueRow" key={i}><label>Phrase {i+1}<textarea maxLength={84} rows={2} value={c.text} onChange={e=>update(i,{text:e.target.value})}/></label><div className="cueTimes"><label>Start (s)<input type="number" min="0" max="3600" step="0.05" value={c.start} onChange={e=>update(i,{start:e.target.value})}/></label><label>End (s)<input type="number" min="0" max="3600" step="0.05" value={c.end} onChange={e=>update(i,{end:e.target.value})}/></label></div><div className="toolrow"><button onClick={()=>onSeek(Number(c.start)||0)}>Go to start</button><button onClick={()=>update(i,{start:Number(elapsed.toFixed(2))})}>Start here</button><button onClick={()=>update(i,{end:Number(elapsed.toFixed(2))})}>End here</button><button onClick={()=>{setDraft(draft.filter((_,n)=>n!==i));setEdited(true);}}>Remove</button></div></div>)}</div>
    {error&&<p role="alert" className="warning">{error}</p>}
    <div className="toolrow"><button disabled={!edited} onClick={apply}>Apply subtitle timing</button><button onClick={()=>{setDraft([...draft,{start:Number(draft.at(-1)?.end||0),end:Math.min(3600,Number(draft.at(-1)?.end||0)+2),text:''}]);setEdited(true);}}>Add phrase</button><button onClick={()=>{onChange({subtitle_cues:null});setDraft(subtitleCues({...scene,subtitle_cues:null}));setEdited(false);setError('');}}>Reset to estimated</button></div>
    <p className="hint">Gaps show no subtitle. Scene duration clips later phrases. Changing narration, voice or speed resets custom timing. {edited?'Unapplied timing edits.':''}</p>
  </div>;
}
