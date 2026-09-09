import React, {useEffect,useState} from 'react';

export default function AnnotationTiming({annotation,duration,elapsed,onChange}) {
  const [start,setStart]=useState(0),[end,setEnd]=useState(null),[error,setError]=useState('');
  useEffect(()=>{setStart(annotation.start??0);setEnd(annotation.end??null);setError('');},[annotation.id,annotation.start,annotation.end]);
  const changed=Number(start)!==(annotation.start??0)||(end===null?null:Number(end))!==(annotation.end??null);
  function apply(){
    const a=Number(start),b=end===null?null:Number(end);
    if(start===''||end===''||!Number.isFinite(a)||a<0||a>3600||(b!==null&&(!Number.isFinite(b)||b<=a||b>3600))){setError('Enter a start of 0 seconds or later, and an exit after the start (maximum 3600 seconds).');return;}
    onChange({...annotation,start:a,end:b});setError('');
  }
  return <div className="annotationTiming"><h4>When this annotation appears</h4>
    <div className="cueTimes"><div><label className="checkbox"><input type="checkbox" checked={start!==''&&Number(start)===0} onChange={e=>setStart(e.target.checked?0:Math.max(.05,Number(elapsed.toFixed(2))))}/>From the start</label>
      <label>Enter at (seconds)<input type="number" min="0" max="3600" step="0.05" value={start} onChange={e=>setStart(e.target.value)}/></label><button onClick={()=>setStart(Number(elapsed.toFixed(2)))}>Enter at playhead</button></div>
    <div><label className="checkbox"><input type="checkbox" checked={end===null} onChange={e=>setEnd(e.target.checked?null:Math.min(3600,Math.max(Number(start)+.5,elapsed)))}/>Until scene ends</label>
      <label>Exit at (seconds)<input type="number" min="0" max="3600" step="0.05" disabled={end===null} value={end??''} placeholder="Scene end" onChange={e=>setEnd(e.target.value)}/></label><button onClick={()=>setEnd(Number(elapsed.toFixed(2)))}>Exit at playhead</button></div></div>
    <p className="toolhint">Playhead: {elapsed.toFixed(2)} s · Scene: {duration.toFixed(2)} s. Times are measured from this scene’s start.</p>
    {Number(start)>=duration&&<p className="warning">The entry is after this scene ends, so the annotation will not appear.</p>}
    {['cover','blur'].includes(annotation.type)&&<p className="toolhint">The screenshot is visible outside this blur/cover’s active time. Keep it on for the whole scene if the details must stay hidden.</p>}
    {error&&<p role="alert" className="warning">{error}</p>}
    <button disabled={!changed} onClick={apply}>Apply annotation timing</button>{changed&&<span className="toolhint"> Unapplied timing edits</span>}
  </div>;
}
