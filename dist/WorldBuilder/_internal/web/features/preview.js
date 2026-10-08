// Read-only WIR cuboid renderer. No planner, API call, or world mutation here.
import {$} from '../core/ui.js';
const colors = {stone:[151,155,147],wood:[166,120,77],glass:[162,199,204],brick:[174,109,89],metal:[115,131,128],grass:[153,174,128],white:[230,224,204],water:[112,168,185]};
export function preview() {
  const canvas = $('#scene'), ctx = canvas.getContext('2d');
  let records = [], region = 32, angle = -.62, elevation = .62, zoom = 1, selected = null, hitFaces = [], drag = null, dirty = false;
  function project(p) { const x = p[0]-region/2, y=p[1]-region/2; const u=x*Math.cos(angle)-y*Math.sin(angle), v=x*Math.sin(angle)+y*Math.cos(angle); return [u, v*Math.sin(elevation)-p[2]*Math.cos(elevation), v*Math.cos(elevation)+p[2]*Math.sin(elevation)]; }
  function redraw() { if (!dirty) { dirty=true; requestAnimationFrame(draw); } }
  function draw() {
    dirty=false; const rect=canvas.getBoundingClientRect(), width=rect.width, height=rect.height; if (!width || !height) return;
    const dpr=Math.min(devicePixelRatio || 1,2); canvas.width=width*dpr; canvas.height=height*dpr; ctx.scale(dpr,dpr); ctx.clearRect(0,0,width,height);
    const heightLimit=Number($('#cut-height').value), showTerrain=$('#show-terrain').checked;
    const visible=records.filter(r => (showTerrain || r.kind !== 'terrain') && r.bounds.min[2] < heightLimit);
    const corners=[[0,0,0],[region,0,0],[region,region,0],[0,region,0]];
    const all=[...corners.map(project),...visible.flatMap(r => [project(r.bounds.min),project(r.bounds.max)])];
    const minY=Math.min(...all.map(p=>p[1])), maxY=Math.max(...all.map(p=>p[1]));
    const span=region*(Math.abs(Math.cos(angle))+Math.abs(Math.sin(angle)));
    const scale=Math.min((width-90)/span,(height-110)/Math.max(maxY-minY,region*.4))*zoom;
    const point=p=>{const q=project(p); return [width/2+q[0]*scale,height/2+(q[1]-(minY+maxY)/2)*scale,q[2]];};
    ctx.strokeStyle='#ccd2c3'; ctx.lineWidth=.7;
    for(let i=0;i<=16;i++) { const at=region*i/16; for (const pair of [[[at,0,0],[at,region,0]],[[0,at,0],[region,at,0]]]) {const [a,b]=pair.map(point);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();} }
    const faces=[];
    for (const record of visible) {
      const [x,y,z]=record.bounds.min,[X,Y,Z0]=record.bounds.max,Z=Math.min(Z0,heightLimit);
      const vertices=[[x,y,z],[X,y,z],[X,Y,z],[x,Y,z],[x,y,Z],[X,y,Z],[X,Y,Z],[x,Y,Z]];
      const definitions=[[[4,5,6,7],[0,0,1],1.08],[[0,1,5,4],[0,-1,0],.91],[[1,2,6,5],[1,0,0],.8],[[2,3,7,6],[0,1,0],.87],[[3,0,4,7],[-1,0,0],.95]];
      for (const [indices,n,shade] of definitions) {
        const towardCamera=(n[0]*Math.sin(angle)+n[1]*Math.cos(angle))*Math.cos(elevation)+n[2]*Math.sin(elevation);
        if(towardCamera <= .0001) continue;
        const points=indices.map(i=>point(vertices[i]));
        faces.push({points,depth:points.reduce((s,p)=>s+p[2],0)/4,record,shade});
      }
    }
    faces.sort((a,b)=>a.depth-b.depth); hitFaces=faces;
    for(const face of faces) {
      const color=colors[face.record.attributes.agent_material] || colors.stone;
      ctx.beginPath(); face.points.forEach((p,i)=>i ? ctx.lineTo(p[0],p[1]) : ctx.moveTo(p[0],p[1]));ctx.closePath();
      ctx.fillStyle=`rgb(${color.map(c=>Math.min(255,Math.round(c*face.shade))).join(',')})`;ctx.fill();
      ctx.strokeStyle=face.record.id===selected ? '#f5cb62' : 'rgba(48,67,47,.2)';ctx.lineWidth=face.record.id===selected ? 2 : .55;ctx.stroke();
    }
    const north=point([region/2,region+2,0]);ctx.fillStyle='#72816d';ctx.font='11px sans-serif';ctx.fillText('N ↑',north[0],north[1]+12);
  }
  function inside(x,y,points) {let value=false; for(let i=0,j=points.length-1;i<points.length;j=i++) {const a=points[i],b=points[j]; if ((a[1]>y)!==(b[1]>y) && x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]) value=!value;}return value;}
  canvas.addEventListener('pointerdown',event=>{drag={x:event.clientX,y:event.clientY,start:event.clientX,moved:false};canvas.setPointerCapture(event.pointerId);});
  canvas.addEventListener('pointermove',event=>{if(!drag)return;const delta=event.clientX-drag.x;if(Math.abs(event.clientX-drag.start)>4)drag.moved=true;angle+=delta*.008;drag.x=event.clientX;redraw();});
  canvas.addEventListener('pointerup',event=>{if(!drag)return;if(!drag.moved){const rect=canvas.getBoundingClientRect();const face=[...hitFaces].reverse().find(f=>inside(event.clientX-rect.left,event.clientY-rect.top,f.points));selected=face?.record.id || null; if(face){const r=face.record;$('#selection').textContent=`${r.kind} · ${r.attributes.agent_material} · ${r.bounds.max.map((v,i)=>v-r.bounds.min[i]).join(' × ')} m · ${r.id}`;}else $('#selection').textContent='选择构件可查看类型、材质、尺寸与源 ID。';}drag=null;redraw();});
  canvas.addEventListener('pointercancel',()=>{drag=null;});
  canvas.addEventListener('wheel',event=>{event.preventDefault();zoom=Math.max(.45,Math.min(3,zoom*Math.exp(-event.deltaY*.001)));redraw();},{passive:false});
  $('#reset-view').onclick=()=>{angle=-.62;elevation=.62;zoom=1;redraw();};
  $('#top-view').onclick=()=>{elevation=elevation>1.5 ? .62 : Math.PI/2;redraw();};
  $('#show-terrain').onchange=redraw;
  $('#cut-height').oninput=()=>{$('#cut-value').textContent=Number($('#cut-height').value)===Number($('#cut-height').max) ? '全部' : `${$('#cut-height').value} m`;redraw();};
  new ResizeObserver(redraw).observe(canvas);
  return {clear() {records=[];selected=null;$('#scene-empty').hidden=false;$('#scene-badge').textContent='等待生成';$('#scene-stats').textContent='源几何 · 米制 · Z 向上';$('#selection').textContent='选择构件可查看类型、材质、尺寸与源 ID。';redraw();},load(scene){records=scene.records.filter(r=>r.record_type==='entity'&&r.geometry?.representation==='box');const spec=scene.records.find(r=>r.record_type==='world_spec');region=spec?.region_bounds.max[0] || 32;const max=Math.ceil(Math.max(...records.map(r=>r.bounds.max[2]),1));$('#cut-height').max=max;$('#cut-height').value=max;$('#cut-value').textContent='全部';$('#scene-empty').hidden=true;$('#scene-badge').textContent='源几何已加载';$('#scene-stats').textContent=`${records.length} 个构件 · ${region} × ${region} m`;
    $('#selection').textContent='选择构件可查看类型、材质、尺寸与源 ID。';selected=null;zoom=1;redraw();}};
}
