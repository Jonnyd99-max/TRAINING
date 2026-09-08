import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

async function api(path, options = {}) {
  const response = await fetch('/api' + path, { ...options, headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' } });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the fields and try again.');
  }
  return response.json();
}
const makeScene = (voice = 'piper:en_GB-northern_english_male-medium') => ({ id: crypto.randomUUID().replaceAll('-', ''), kind: 'image', title: 'Untitled scene', subtitle: '', image: null, narration: '', caption: '', duration: 5, manual_duration: false, voice, speed: 0, audio: null, audio_key: null, audio_duration: null });
const formatTime = value => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;

function App() {
  const [health, setHealth] = useState(null), [projects, setProjects] = useState([]), [project, setProject] = useState(null);
  const [selected, setSelected] = useState(0), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [creating, setCreating] = useState(false), [busy, setBusy] = useState(false), [dirty, setDirty] = useState(false);
  const [saveState, setSaveState] = useState('Saved locally'), [playing, setPlaying] = useState(false), [elapsed, setElapsed] = useState(0);
  const [job, setJob] = useState(null), [showVideo, setShowVideo] = useState(false);
  const latest = useRef(null), generation = useRef(0), saving = useRef(null), audio = useRef(null), elapsedRef = useRef(0);
  const scene = project?.scenes[selected];
  const locked = busy || job?.status === 'running';
  const offlineScene = scene?.voice.startsWith('piper:');
  const onlineSceneCount = project?.scenes.filter(s => !s.voice.startsWith('piper:')).length || 0;
  const offlineVoiceMissing = offlineScene && (!health?.offline_ready || !health?.offline_voices?.[scene.voice]);
  const mediaUrl = path => path && project ? `/api/projects/${project.id}/media/${path}` : '';
  const accept = p => { latest.current = p; setProject(p); };
  const change = p => { generation.current++; accept(p); setDirty(true); setSaveState('Unsaved changes'); setShowVideo(false); setJob(null); };
  const patchScene = values => {
    const p = latest.current;
    const invalidate = ['narration', 'voice', 'speed'].some(k => k in values);
    change({ ...p, video: null, scenes: p.scenes.map((s, i) => i === selected ? { ...s, ...values, ...(invalidate ? { audio: null, audio_key: null, audio_duration: null } : {}) } : s) });
  };

  async function save() {
    if (saving.current) { await saving.current; return save(); }
    if (!latest.current) return;
    if (!dirty) return latest.current;
    const version = generation.current, snapshot = latest.current;
    setSaveState('Saving…');
    const promise = api(`/projects/${snapshot.id}`, { method: 'PUT', body: JSON.stringify(snapshot) });
    saving.current = promise;
    try {
      const result = await promise;
      if (latest.current?.id !== snapshot.id) return result;
      if (generation.current === version) { accept(result); setDirty(false); setSaveState('Saved locally'); }
      else { accept({ ...latest.current, revision: result.revision }); setSaveState('Unsaved changes'); }
      return result;
    } catch (e) { setSaveState('Save failed'); setError(e.message); throw e; }
    finally { saving.current = null; }
  }
  async function action(fn) {
    setError(''); setNotice(''); setBusy(true); setPlaying(false);
    try { await fn(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function dashboard() {
    if (dirty) await save();
    setProjects(await api('/projects')); accept(null); setPlaying(false); setJob(null); setShowVideo(false);
  }
  useEffect(() => {
    Promise.all([api('/health'), api('/projects')]).then(([h, p]) => { setHealth(h); setProjects(p); }).catch(e => setError('Cannot reach the backend. Start it and reload. ' + e.message));
  }, []);
  useEffect(() => {
    if (!dirty || locked) return;
    const timer = setTimeout(() => save().catch(() => {}), 900);
    return () => clearTimeout(timer);
  }, [project, dirty, locked]);
  useEffect(() => {
    const warn = e => { if (dirty || locked) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn);
  }, [dirty, locked]);
  useEffect(() => {
    if (job?.status !== 'running') return;
    const timer = setInterval(async () => {
      try {
        const next = await api(`/jobs/${job.id}`); setJob(next);
        if (next.status !== 'running') {
          accept(await api(`/projects/${latest.current.id}`)); setDirty(false);
          if (next.status === 'failed') setError(next.message);
        }
      } catch (e) { setError(e.message); setJob(j => ({ ...j, status: 'failed' })); }
    }, 1000);
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  useEffect(() => { elapsedRef.current = 0; setElapsed(0); }, [selected, project?.id]);
  useEffect(() => {
    if (!playing || !scene) { audio.current?.pause(); return; }
    if (scene.audio && audio.current) {
      audio.current.currentTime = Math.min(elapsedRef.current, scene.audio_duration || 0);
      audio.current.play().catch(() => { setPlaying(false); setError('Audio playback was blocked. Press Play to try again.'); });
    }
    let last = performance.now();
    const timer = setInterval(() => {
      const t = performance.now(); elapsedRef.current += (t-last)/1000; last = t;
      setElapsed(elapsedRef.current);
      if (elapsedRef.current >= scene.duration) {
        audio.current?.pause(); elapsedRef.current = 0; setElapsed(0);
        if (selected < project.scenes.length-1) setSelected(i => i+1); else { setPlaying(false); setSelected(0); }
      }
    }, 50);
    return () => { clearInterval(timer); audio.current?.pause(); };
  }, [playing, selected, scene?.audio, scene?.duration]);

  const select = i => { setPlaying(false); audio.current?.pause(); elapsedRef.current = 0; setElapsed(0); setSelected(i); };
  const total = project?.scenes.reduce((sum, s) => sum + s.duration, 0) || 0;
  const move = delta => {
    const scenes = [...project.scenes], destination = selected + delta;
    [scenes[selected], scenes[destination]] = [scenes[destination], scenes[selected]];
    change({ ...project, video: null, scenes }); select(destination);
  };
  return <>
    <header className="topbar"><a className="brand" href="#" onClick={e => { e.preventDefault(); if (!locked) action(dashboard); }}><span className="monogram">JD</span><span>Training Studio<small>SCREENSHOTS TO KNOW-HOW</small></span></a>
      <nav><button disabled={locked} onClick={() => action(dashboard)}>Dashboard</button><button disabled={locked} onClick={() => action(dashboard)}>Open Project</button><button className="primary" disabled={locked} onClick={() => setCreating(true)}>+ New Training</button></nav>
    </header>
    <div className="systembar"><span><i className={health?.ffmpeg ? 'dot ready' : 'dot'} />FFmpeg: {health ? health.ffmpeg ? 'Ready' : 'Not Found' : 'Checking…'}</span><span>LOCAL WORKSPACE <b>•</b> Your files stay on this computer</span></div>
    {health && !health.ffmpeg && <div className="banner">{health.instructions}</div>}
    <div className="offlinebar"><span>Offline narration: <strong>{health ? health.offline_ready ? 'Ready' : 'Unavailable' : 'Checking…'}</strong></span><button disabled={locked} onClick={() => action(async () => { setHealth(await api('/health')); setNotice('Offline voice list refreshed.'); })}>Refresh voices</button></div>
    {health && !health.offline_ready && <div className="banner">{health.offline_message}</div>}
    {error && <div role="alert" className="banner error">{error}<button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
    {notice && <div role="status" className="banner">{notice}</div>}
    {!project ? <main className="dashboard">
      <div className="eyebrow">YOUR TRAINING WORKSPACE</div><div className="pageheading"><div><h1>Good training starts here.</h1><p>Turn everyday screenshots into clear, narrated training videos.</p></div><button className="primary large" disabled={busy} onClick={() => setCreating(true)}>+ CREATE TRAINING</button></div>
      <div className="sectiontitle"><h2>Training projects <span>{projects.length}</span></h2><span>Saved on this computer</span></div>
      <div className="cards">{projects.map(p => <article className="card" key={p.id}><div className="cardvisual">{p.scenes.find(s => s.image) ? <img alt="" src={`/api/projects/${p.id}/media/${p.scenes.find(s => s.image).image}`} /> : <span>JD<span>TRAINING STUDIO</span></span>}<b>{p.scenes.length} SCENES</b></div><div className="cardbody"><h3>{p.title}</h3><p>Edited {new Date(p.modified).toLocaleString()}</p><button disabled={busy} onClick={() => action(async () => { accept(await api(`/projects/${p.id}`)); setDirty(false); setSelected(0); setSaveState('Saved locally'); })}>Open training <span>↗</span></button></div></article>)}
        <button className="newcard" disabled={busy} onClick={() => setCreating(true)}><span>+</span>Create a new training<small>A few scenes. A clearer process.</small></button></div>
      <div className="workflow"><span>01 <b>Add screenshots</b></span><span>02 <b>Write your narration</b></span><span>03 <b>Export your training</b></span><p>No paid AI account required.</p></div>
    </main> : <main className="editor">
      <div className="editorheading"><div><div className="eyebrow">TRAINING EDITOR</div><input aria-label="Training title" className="projecttitle" disabled={locked || playing} maxLength={120} value={project.title} onChange={e => change({ ...project, title: e.target.value, video: null })}/><span className="savestatus">{saveState} · {project.scenes.length} scenes · {formatTime(total)}</span></div><div className="actions"><button disabled={locked} onClick={() => action(save)}>Save Project</button><button className="primary" disabled={locked || !project.scenes.length || !health?.ffmpeg} onClick={() => action(async () => { await save(); setJob(await api(`/projects/${project.id}/render`, { method: 'POST' })); })}>↗ GENERATE VIDEO</button></div></div>
      <div className="offlinebar projectoffline"><span>{onlineSceneCount ? `${onlineSceneCount} scene${onlineSceneCount === 1 ? '' : 's'} use online voices. Their narration text is sent to Microsoft when generated.` : 'All scenes use offline voices. Narration stays on this computer.'}</span>{onlineSceneCount > 0 && <button disabled={locked || playing || !health?.offline_ready} onClick={() => { setPlaying(false); change({ ...project, video: null, scenes: project.scenes.map(s => s.voice.startsWith('piper:') ? s : { ...s, voice: health.default_voice, audio: null, audio_key: null, audio_duration: null }) }); setNotice('Project switched to offline voices. Generate narration or export to create local audio.'); }}>Use offline voices for this project</button>}</div>
      {job && <div className="renderstatus"  role="status"><strong>{job.message}</strong><progress max="100" value={job.progress}/></div>}
      {project.video && <div className="videoready"><strong>✓ VIDEO READY</strong><button onClick={() => setShowVideo(!showVideo)}>{showVideo ? 'Close Video' : 'Play Video'}</button><button onClick={() => action(async () => { const r = await api(`/projects/${project.id}/open-output`, { method: 'POST' }); setNotice(r.path); })}>Open Video Location</button><a href={mediaUrl(project.video)} download>Download MP4</a></div>}
      {showVideo && project.video && <video className="exportvideo" controls autoPlay src={mediaUrl(project.video)}/>}
      <div className="editorgrid"><aside className="scenes"><div className="panelheading"><h2>Scenes</h2><span>{String(project.scenes.length).padStart(2, '0')}</span></div><div className="scenelist">{project.scenes.map((s, i) => <button className={`sceneitem ${i === selected ? 'selected' : ''}`} key={s.id} disabled={locked} onClick={() => select(i)}><div className="thumb">{s.image ? <img alt="" src={mediaUrl(s.image)}/> : <span>{s.kind === 'title' ? 'T' : '+'}</span>}<b>{String(i+1).padStart(2, '0')}</b></div><strong>{s.title || `Scene ${i+1}`}</strong><small>{formatTime(s.duration)} · {s.audio ? 'Narrated' : s.kind === 'title' ? 'Title' : 'No narration audio'}</small></button>)}</div><button className="addscene" disabled={locked || playing || project.scenes.length >= 100} onClick={() => { change({ ...project, video: null, scenes: [...project.scenes, makeScene(health?.default_voice)] }); select(project.scenes.length); }}>+ Add scene</button>
        {scene && <div className="scenetools"><button aria-label="Move scene up" disabled={locked || playing || selected === 0} onClick={() => move(-1)}>↑</button><button aria-label="Move scene down" disabled={locked || playing || selected === project.scenes.length-1} onClick={() => move(1)}>↓</button><button disabled={locked || playing || project.scenes.length >= 100} onClick={() => { const scenes = [...project.scenes]; scenes.splice(selected+1, 0, { ...scene, id: makeScene().id, title: (scene.title + ' (copy)').slice(0,120), audio: null, audio_key: null, audio_duration: null }); change({ ...project, video: null, scenes }); select(selected+1); }}>Duplicate</button><button className="danger" disabled={locked || playing} onClick={() => { change({ ...project, video: null, scenes: project.scenes.filter((_, i) => i !== selected) }); select(Math.max(0, selected-1)); }}>Delete</button></div>}
      </aside><section className="previewpanel"><div className="panelheading"><h2>Preview</h2><span>1920 × 1080 <b>·</b> 16:9</span></div><div className="previewstage"><div className="preview" style={{ opacity: playing ? Math.max(0, Math.min(1, elapsed/.3, (scene.duration-elapsed)/.3)) : 1 }}>
        {scene?.kind === 'title' ? <div className="titlescene"><span/><h2>{scene.title}</h2><p>{scene.subtitle}</p><small>JD TRAINING STUDIO</small></div> : scene?.image ? <img src={mediaUrl(scene.image)} alt={scene.title} onError={() => setError('A scene image is missing. Upload it again.')}/> : <div className="empty"><span>▧</span><h3>{scene ? 'Give this scene a visual' : 'Your story starts with a scene'}</h3><p>{scene ? 'Upload a screenshot in Scene Settings.' : 'Add a scene to begin.'}</p></div>}
        {scene?.caption && <div className="caption">{scene.caption}</div>}
      </div></div><div className="transport"><button aria-label="Previous scene" disabled={!scene || selected === 0 || locked} onClick={() => select(selected-1)}>⏮</button><button className="play" disabled={!scene || locked} onClick={() => setPlaying(!playing)}>{playing ? 'Ⅱ Pause' : '▶ Play'}</button><button aria-label="Next scene" disabled={!scene || selected === project.scenes.length-1 || locked} onClick={() => select(selected+1)}>⏭</button><span>{formatTime(elapsed)} / {formatTime(scene?.duration || 0)}</span></div><progress className="timeline" value={elapsed} max={scene?.duration || 1}/><div className="previewnote"><span>SCENE {scene ? selected+1 : 0} OF {project.scenes.length}</span><p>Play continues through every scene from your selection.</p></div>{scene && !scene.audio && <p className="hint">{scene.narration ? 'Generate narration to hear it in the preview. Export generates it automatically.' : 'This scene plays silently. Add narration text for a voiceover.'}</p>}
      </section><aside className="settings"><div className="panelheading"><h2>Scene Settings</h2><span>✎</span></div>{scene ? <fieldset disabled={locked || playing}><label>Scene title<input maxLength={120} value={scene.title} onChange={e => patchScene({ title: e.target.value })}/></label>{scene.kind === 'title' ? <label>Subtitle<input maxLength={160} value={scene.subtitle} onChange={e => patchScene({ subtitle: e.target.value })}/></label> : <label className="uploadlabel">Screenshot / image<input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => { const file = e.target.files[0]; e.target.value = ''; if (file) action(async () => { const data = new FormData(); data.append('file', file); const result = await api(`/projects/${project.id}/images`, { method: 'POST', body: data }); patchScene({ image: result.image }); }); }}/><small>PNG, JPG or WebP · up to 20 MB</small></label>}
        <label>Narration text<textarea rows={5} maxLength={10000} placeholder="Explain what the learner should do…" value={scene.narration} onChange={e => patchScene({ narration: e.target.value })}/><small>{offlineScene ? 'Generated on this computer. No internet or account required.' : 'Online voice: text is sent to Microsoft Edge TTS when generated.'}</small></label><label>On-screen caption <small>OPTIONAL</small><textarea rows={2} maxLength={220} placeholder="A short, useful takeaway" value={scene.caption} onChange={e => patchScene({ caption: e.target.value })}/></label>
        <label>Scene duration (seconds)<input type="number" min="1" max="3600" step="0.1" value={scene.duration} onChange={e => patchScene({ duration: Math.max(1, Math.min(3600, Number(e.target.value) || 1)), manual_duration: true })}/></label><label className="checkbox"><input type="checkbox" checked={!scene.manual_duration} onChange={e => patchScene({ manual_duration: !e.target.checked, ...(e.target.checked && scene.audio_duration ? { duration: Math.round((scene.audio_duration+1)*100)/100 } : {}) })}/>Auto duration: narration + 1 second</label>{scene.manual_duration && scene.audio_duration > scene.duration && <small className="warning">Narration will be cut short at this duration.</small>}
        <label>Narration voice<select value={scene.voice} onChange={e => patchScene({ voice: e.target.value })}>{!health?.voices?.[scene.voice] && <option value={scene.voice}>{scene.voice === 'piper:en_GB-northern_english_male-medium' ? 'Default Piper voice (offline)' : `${scene.voice} (not installed)`}</option>}<optgroup label="Offline — installed Piper voices">{Object.entries(health?.offline_voices || {}).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</optgroup><optgroup label="Online — Microsoft Edge TTS">{Object.entries(health?.online_voices || {}).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</optgroup></select></label><label>Narration speed <span>{scene.speed > 0 ? '+' : ''}{scene.speed}%</span><input type="range" min="-50" max="100" step="5" value={scene.speed} onChange={e => patchScene({ speed: Number(e.target.value) })}/></label>
        {offlineVoiceMissing && <small className="warning">This offline voice is unavailable. Refresh voices and choose an installed voice above.</small>}
        <button className="narrate" disabled={!scene.narration.trim() || !health?.ffmpeg || offlineVoiceMissing} onClick={() => action(async () => { await save(); accept(await api(`/projects/${project.id}/scenes/${scene.id}/narration`, { method: 'POST' })); setDirty(false); setNotice('Narration ready. Scene duration has been updated unless manually set.'); })}>{busy ? 'Working…' : '♫ Generate Narration'}</button><button disabled={!scene.audio} onClick={() => { audio.current.currentTime = 0; audio.current.play().catch(e => setError(e.message)); }}>▶ Preview Narration</button>
      </fieldset> : <p className="hint">Select or add a scene.</p>}</aside></div>
      <audio ref={audio} src={scene?.audio ? mediaUrl(scene.audio) : undefined}/>
    </main>}
    {creating && <div className="modalbackdrop"><form className="modal" onSubmit={e => { e.preventDefault(); const data = new FormData(e.currentTarget); action(async () => { if (dirty) await save(); const p = await api('/projects', { method: 'POST', body: JSON.stringify({ title: data.get('title'), subtitle: data.get('subtitle'), opening: data.get('opening') === 'on' }) }); accept(p); setSelected(0); setDirty(false); setJob(null); setCreating(false); }); }}><div className="eyebrow">A NEW LEARNING EXPERIENCE</div><h2>Create your training</h2><label>Training title<input name="title" autoFocus required maxLength={120} placeholder="e.g. Scheduler Training"/></label><label>Subtitle <small>OPTIONAL</small><input name="subtitle" maxLength={160} placeholder="Understanding lot priorities"/></label><label className="checkbox"><input type="checkbox" name="opening" defaultChecked/>Include an opening title scene</label><div className="actions"><button type="button" disabled={busy} onClick={() => setCreating(false)}>Cancel</button><button className="primary" disabled={busy}>Create Training</button></div></form></div>}
    <footer>JD TRAINING STUDIO <span>Made for clear instructions. Built around your screenshots.</span></footer>
  </>;
}
createRoot(document.getElementById('root')).render(<App/>);
