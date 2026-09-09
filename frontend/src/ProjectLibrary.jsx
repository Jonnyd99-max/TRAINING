import React, {useState} from 'react';
import './ProjectLibrary.css';

export default function ProjectLibrary({projects,busy,request,onProjects,onOpen,onCreate,onNotice}) {
  const [query,setQuery]=useState(''),[folder,setFolder]=useState(null),[sort,setSort]=useState('recent');
  const [modal,setModal]=useState(null),[pending,setPending]=useState(false),[error,setError]=useState('');
  const folders=[...new Set(projects.map(p=>p.folder||'').filter(Boolean))].sort((a,b)=>a.localeCompare(b));
  const visible=projects.filter(p=>(folder===null||(p.folder||'')===folder)&&`${p.title} ${p.folder||''}`.toLowerCase().includes(query.toLowerCase().trim()))
    .sort((a,b)=>sort==='name'?a.title.localeCompare(b.title):b.modified.localeCompare(a.modified));
  const locked=busy||pending;
  function show(kind,project){setError('');setModal({kind,project});}
  async function submit(event){
    event.preventDefault();const data=new FormData(event.currentTarget);setPending(true);setError('');
    try {
      const p=modal.project;
      if(modal.kind==='move')await request(`/projects/${p.id}/organization`,{method:'PUT',body:JSON.stringify({folder:data.get('folder'),revision:p.revision})});
      else await request(`/projects/${p.id}`,{method:'DELETE',body:JSON.stringify({confirm_title:data.get('confirmation'),revision:p.revision})});
      const next=await request('/projects');onProjects(next);
      if(folder!==null&&folder!==''&&!next.some(p=>p.folder===folder))setFolder(null);
      onNotice(modal.kind==='move'?'Project folder updated.':'Project and its local files deleted. Videos in Training output were kept.');setModal(null);
    }catch(e){setError(e.message);}finally{setPending(false);}
  }
  return <>
    <div className="librarycontrols"><label>Search projects<input type="search" placeholder="Search by title or folder" value={query} onChange={e=>setQuery(e.target.value)}/></label>
      <label>Folder<select value={JSON.stringify(folder)} onChange={e=>setFolder(JSON.parse(e.target.value))}><option value="null">All projects ({projects.length})</option><option value={'""'}>Unfiled ({projects.filter(p=>!p.folder).length})</option>{folders.map(name=><option key={name} value={JSON.stringify(name)}>{name} ({projects.filter(p=>p.folder===name).length})</option>)}</select></label>
      <label>Sort by<select value={sort} onChange={e=>setSort(e.target.value)}><option value="recent">Recently edited</option><option value="name">Project name</option></select></label><button disabled={locked} onClick={async()=>{setPending(true);setError('');try{onProjects(await request('/projects'));}catch(e){setError(e.message);}finally{setPending(false);}}}>Refresh projects</button></div>
    <p className="librarycount">Showing {visible.length} of {projects.length} projects. Use Move to folder to create a folder or choose an existing one.</p>
    {!modal&&error&&<p role="alert" className="banner error">{error}</p>}
    {!visible.length&&<p>No projects match this search or folder.</p>}
    <div className="cards">{visible.map(p=><article className="card" key={p.id}><div className="cardvisual">{p.scenes.find(s=>s.image)?<img alt="" src={`/api/projects/${p.id}/media/${p.scenes.find(s=>s.image).image}`}/>:<span>JD<span>TRAINING STUDIO</span></span>}<b>{p.scenes.length} SCENES</b></div>
      <div className="cardbody"><small className="folderbadge">{p.folder||'Unfiled'}</small><h3>{p.title}</h3><p>Edited {new Date(p.modified).toLocaleString()}</p><button disabled={locked} onClick={()=>onOpen(p)}>Open training <span>↗</span></button>
      <div className="projectmanagement"><button disabled={locked} aria-label={`Move ${p.title} to folder`} onClick={()=>show('move',p)}>Move to folder</button><button disabled={locked} className="danger" aria-label={`Delete project ${p.title}`} onClick={()=>show('delete',p)}>Delete project</button></div></div></article>)}
      <button className="newcard" disabled={locked} onClick={onCreate}><span>+</span>Create a new training<small>A few scenes. A clearer process.</small></button></div>
    {modal&&<div className="modalbackdrop"><form className="modal" role="dialog" aria-modal="true" aria-labelledby="library-modal-title" onSubmit={submit} onKeyDown={e=>{if(e.key==='Escape'&&!pending)setModal(null);}}><h2 id="library-modal-title">{modal.kind==='move'?'Move project to folder':'Delete project permanently?'}</h2><p><strong>{modal.project.title}</strong></p>
      {modal.kind==='move'?<><label>Folder name<input autoFocus name="folder" maxLength={80} defaultValue={modal.project.folder||''} list="project-folders" placeholder="e.g. Induction, Production, Drafts"/></label><datalist id="project-folders">{folders.map(name=><option key={name} value={name}/>)}</datalist><p>Choose an existing folder or type a new name. Leave blank to move to Unfiled. This organizes projects within the app.</p></>:<><p>This permanently removes the project, its uploaded screenshots, narration audio and internal video copies from this computer. It cannot be undone in the app.</p><p><strong>Videos already saved in your Training output folder will be kept.</strong></p><label>Type the project title to confirm<input autoFocus name="confirmation" required autoComplete="off" maxLength={120}/></label></>}
      {error&&<p role="alert" className="warning">{error}</p>}<div className="actions"><button type="button" disabled={pending} onClick={()=>setModal(null)}>Cancel</button><button disabled={pending} className={modal.kind==='delete'?'danger':'primary'}>{pending?'Working…':modal.kind==='move'?'Move project':'Delete project and local files'}</button></div></form></div>}
  </>;
}
