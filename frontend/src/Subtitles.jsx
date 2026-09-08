import React from 'react';

export function subtitleCues(scene) {
  if(!scene?.subtitles_enabled || !scene.audio_duration)return [];
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
