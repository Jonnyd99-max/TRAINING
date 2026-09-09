export const W = 1920, H = 1080;
export const FPS = 30;
export const visibleAt = (a,t) => t >= (a.start??0) && (a.end==null || t<a.end);
export const defaultCamera = () => ({ enabled: false, start: {zoom:1,x:.5,y:.5}, end: {zoom:1,x:.5,y:.5} });
export const clamp = (v, min=0, max=1) => Math.max(min, Math.min(max, v));
export function cameraAt(camera, progress) {
  if (!camera?.enabled) return {zoom:1,x:.5,y:.5};
  const t=clamp(progress), ease=t*t*(3-2*t);
  return Object.fromEntries(['zoom','x','y'].map(k=>[k,camera.start[k]+(camera.end[k]-camera.start[k])*ease]));
}
export function crop(view) {
  const width=W/view.zoom, height=H/view.zoom;
  return {x:clamp(view.x*W-width/2,0,W-width),y:clamp(view.y*H-height/2,0,H-height),width,height};
}
export function box(a) { return [Math.min(a.x,a.x2)*W,Math.min(a.y,a.y2)*H,Math.abs(a.x2-a.x)*W,Math.abs(a.y2-a.y)*H]; }
export function paintCallout(ctx,a) {
  const x=a.x*W,y=a.y*H,x2=a.x2*W,y2=a.y2*H;
  ctx.save(); ctx.fillStyle=a.color;ctx.strokeStyle=a.color;
  if(a.type==='highlight') {
    ctx.globalAlpha=38/255;ctx.fillRect(...box(a));ctx.globalAlpha=1;ctx.lineWidth=6;ctx.strokeRect(...box(a));
  } else if(a.type==='arrow') {
    const angle=Math.atan2(y2-y,x2-x),length=Math.min(34,Math.hypot(x2-x,y2-y)*.6);
    const bx=x2-length*Math.cos(angle),by=y2-length*Math.sin(angle);
    ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(bx,by);ctx.strokeStyle='#101928';ctx.lineWidth=12;ctx.stroke();
    ctx.strokeStyle=a.color;ctx.lineWidth=8;ctx.stroke();ctx.beginPath();ctx.moveTo(x2,y2);
    ctx.lineTo(bx-14*Math.sin(angle),by+14*Math.cos(angle));ctx.lineTo(bx+14*Math.sin(angle),by-14*Math.cos(angle));ctx.closePath();ctx.fill();
  } else if(a.type==='number') {
    ctx.beginPath();ctx.arc(x,y,34,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#101928';ctx.lineWidth=3;ctx.stroke();
    ctx.fillStyle='#101928';ctx.font='36px "Segoe UI", sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(a.number),x,y);
  }
  ctx.restore();
}
export function prepareVisual(image, annotations, makeCanvas=()=>document.createElement('canvas')) {
  const base=makeCanvas();base.width=W;base.height=H;const ctx=base.getContext('2d');
  ctx.fillStyle='#101928';ctx.fillRect(0,0,W,H);
  const factor=Math.min(W/image.width,H/image.height),w=Math.round(image.width*factor),h=Math.round(image.height*factor);
  ctx.drawImage(image,Math.floor((W-w)/2),Math.floor((H-h)/2),w,h);
  if(annotations.some(a=>a.type==='blur')) {
    const blurred=makeCanvas();blurred.width=W;blurred.height=H;const bctx=blurred.getContext('2d');
    bctx.filter='blur(24px)';bctx.drawImage(base,0,0);
    for(const a of annotations.filter(a=>a.type==='blur')) {const r=box(a);if(r[2]>0&&r[3]>0)ctx.drawImage(blurred,...r,...r);}
  }
  ctx.fillStyle='#101928';for(const a of annotations.filter(a=>a.type==='cover'))ctx.fillRect(...box(a));
  for(const a of annotations)paintCallout(ctx,a);
  return base;
}
export function drawViewport(ctx,base,view) {
  const r=crop(view);ctx.clearRect(0,0,W,H);ctx.drawImage(base,r.x,r.y,r.width,r.height,0,0,W,H);
}
export function hit(a,p) {
  const px=p.x*W,py=p.y*H,x=a.x*W,y=a.y*H,x2=a.x2*W,y2=a.y2*H;
  if(a.type==='number')return Math.hypot(px-x,py-y)<45;
  if(a.type==='arrow') {
    const dx=x2-x,dy=y2-y,t=clamp(((px-x)*dx+(py-y)*dy)/(dx*dx+dy*dy||1));
    return Math.hypot(px-x-t*dx,py-y-t*dy)<24;
  }
  const [left,top,width,height]=box(a);return px>=left-10&&px<=left+width+10&&py>=top-10&&py<=top+height+10;
}
