// Bounded 046 GLB dialect: real world-space source triangles, never AABB proxies.
import {$} from '../core/ui.js';
export function meshPreview(){
  const canvas=document.createElement('canvas');canvas.id='mesh-scene';canvas.hidden=true;canvas.setAttribute('aria-label','真实三角网地形与旋转建筑预览');$('#scene').after(canvas);
  const gl=canvas.getContext('webgl2',{antialias:true,preserveDrawingBuffer:true});
  let active=false,angle=-.62,elevation=.68,zoom=1,dirty=false,drag=null,program,vbo,ibo,solidCount=0,totalCount=0,pieces=[],region=768,maxZ=100,selected=0;
  const uniforms={};
  function shader(type,source){const value=gl.createShader(type);gl.shaderSource(value,source);gl.compileShader(value);if(!gl.getShaderParameter(value,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(value));return value;}
  function initialize(){
    if(program)return;
    program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,`#version 300 es
      in vec3 position;in vec3 normal;in vec4 color;in float terrain;in float objectId;
      uniform vec3 centre,right,up,toward;uniform vec2 halfSize;
      out vec3 N;out vec4 C;out float Z;flat out float T;flat out float ID;
      void main(){vec3 p=position-centre;gl_Position=vec4(dot(p,right)/halfSize.x,dot(p,up)/halfSize.y,-dot(p,toward)/1800.0-(terrain>1.5?.000001:0.0),1.0);N=normal;C=color;Z=position.z;T=terrain;ID=objectId;}`));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`#version 300 es
      precision highp float;in vec3 N;in vec4 C;in float Z;flat in float T;flat in float ID;
      uniform float cutHeight,showTerrain,selectedId,picking;out vec4 outputColor;
      void main(){if(Z>cutHeight||(T>.5&&T<1.5&&showTerrain<.5))discard;
        if(picking>.5){int id=int(ID+.5);outputColor=vec4(float(id%256),float((id/256)%256),float(id/65536),255.0)/255.0;return;}
        float light=.65+.35*max(dot(normalize(N),normalize(vec3(-.4,-.6,1))),0.0);
        vec3 rgb=abs(ID-selectedId)<.1?mix(C.rgb,vec3(1,.72,.22),.5):C.rgb*light;
        outputColor=vec4(pow(max(rgb,vec3(0)),vec3(1.0/2.2)),C.a);}`));
    gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
    for(const key of ['centre','right','up','toward','halfSize','cutHeight','showTerrain','selectedId','picking'])uniforms[key]=gl.getUniformLocation(program,key);
    gl.disable(gl.DITHER);gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);
  }
  function bind(){gl.useProgram(program);gl.bindBuffer(gl.ARRAY_BUFFER,vbo);gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ibo);let offset=0;for(const [name,size] of [['position',3],['normal',3],['color',4],['terrain',1],['objectId',1]]){const loc=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,48,offset*4);offset+=size;}}
  function draw(picking=false){
    dirty=false;if(!active)return;
    const rect=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2),w=Math.round(rect.width*dpr),h=Math.round(rect.height*dpr);if(!w||!h)return;
    if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
    gl.viewport(0,0,w,h);gl.clearColor(.91,.93,.87,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);bind();
    const c=Math.cos(angle),s=Math.sin(angle),se=Math.sin(elevation),ce=Math.cos(elevation);
    const spanX=region*(Math.abs(c)+Math.abs(s)),spanY=spanX*se+maxZ*ce,scale=Math.min((w-60*dpr)/spanX,(h-80*dpr)/spanY)*zoom;
    gl.uniform3f(uniforms.centre,region/2,region/2,maxZ/2);gl.uniform3f(uniforms.right,c,-s,0);gl.uniform3f(uniforms.up,-s*se,-c*se,ce);gl.uniform3f(uniforms.toward,s*ce,c*ce,se);
    gl.uniform2f(uniforms.halfSize,w/(2*scale),h/(2*scale));gl.uniform1f(uniforms.cutHeight,Number($('#cut-height').value));gl.uniform1f(uniforms.showTerrain,$('#show-terrain').checked?1:0);gl.uniform1f(uniforms.selectedId,selected);gl.uniform1f(uniforms.picking,picking?1:0);
    gl.disable(gl.BLEND);gl.depthMask(true);gl.drawElements(gl.TRIANGLES,solidCount,gl.UNSIGNED_INT,0);
    if(!picking){gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);}
    gl.drawElements(gl.TRIANGLES,totalCount-solidCount,gl.UNSIGNED_INT,solidCount*4);gl.depthMask(true);
  }
  function redraw(){if(active&&!dirty){dirty=true;requestAnimationFrame(()=>draw());}}
  canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY,total:0};canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.total+=Math.abs(dx)+Math.abs(dy);angle+=dx*.008;elevation=Math.max(.14,Math.min(1.57,elevation+dy*.006));drag.x=e.clientX;drag.y=e.clientY;redraw();});
  canvas.addEventListener('pointerup',e=>{if(!drag)return;if(drag.total<5){draw(true);const r=canvas.getBoundingClientRect(),pixel=new Uint8Array(4);gl.readPixels(Math.floor((e.clientX-r.left)*canvas.width/r.width),Math.floor((r.bottom-e.clientY)*canvas.height/r.height),1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);selected=pixel[0]+pixel[1]*256+pixel[2]*65536;const part=pieces[selected-1];$('#selection').textContent=part?`${part.group} · ${part.component} · 源ID ${part.source_id}`:'选择三角网构件可查看源ID。';}drag=null;redraw();});
  canvas.addEventListener('pointercancel',()=>drag=null);
  canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.4,Math.min(5,zoom*Math.exp(-e.deltaY*.001)));redraw();},{passive:false});
  $('#reset-view').addEventListener('click',()=>{angle=-.62;elevation=.68;zoom=1;redraw();});
  $('#top-view').addEventListener('click',()=>{elevation=elevation>1.5?.68:1.57;redraw();});
  $('#cut-height').addEventListener('input',redraw);$('#show-terrain').addEventListener('change',redraw);new ResizeObserver(redraw).observe(canvas);
  return {clear(){active=false;canvas.hidden=true;$('#scene').hidden=false;pieces=[];selected=0;if(gl){if(vbo)gl.deleteBuffer(vbo);if(ibo)gl.deleteBuffer(ibo);}vbo=ibo=null;},load(buffer,manifest){
    if(!gl)throw new Error('此环境不支持WebGL2；请下载GLB到Unity查看，不会用包围盒假装真实场景。');initialize();
    const header=new DataView(buffer);if(header.getUint32(0,true)!==0x46546c67)throw new Error('GLB头无效');
    const jsonSize=header.getUint32(12,true),doc=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,20,jsonSize))),binary=28+jsonSize;
    function accessor(index){const a=doc.accessors[index],view=doc.bufferViews[a.bufferView],offset=binary+(view.byteOffset||0)+(a.byteOffset||0);if(view.byteStride)throw new Error('不支持此预览网格布局');const size=a.count*(a.type==='VEC3'?3:1);return a.componentType===5126?new Float32Array(buffer,offset,size):a.componentType===5125?new Uint32Array(buffer,offset,size):(()=>{throw new Error('不支持此预览索引类型');})();}
    const parts=doc.meshes.map((m,i)=>({p:m.primitives[0],piece:manifest.pieces[i],id:i+1}));
    if(parts.length!==manifest.piece_count||parts.some((p,i)=>doc.meshes[i].name!==p.piece.name))throw new Error('GLB与源映射不一致');
    let vertexCount=0,indexCount=0;parts.forEach(({p})=>{vertexCount+=doc.accessors[p.attributes.POSITION].count;indexCount+=doc.accessors[p.indices].count;});
    const data=new Float32Array(vertexCount*12),indices=new Uint32Array(indexCount);let vertex=0,at=0;maxZ=1;
    const ordered=[...parts.filter(p=>doc.materials[p.p.material].pbrMetallicRoughness.baseColorFactor[3]>=.99),...parts.filter(p=>doc.materials[p.p.material].pbrMetallicRoughness.baseColorFactor[3]<.99)];solidCount=0;
    for(const {p,piece,id} of ordered){const positions=accessor(p.attributes.POSITION),normals=accessor(p.attributes.NORMAL),ix=accessor(p.indices),color=doc.materials[p.material].pbrMetallicRoughness.baseColorFactor,start=vertex;
      for(let i=0;i<positions.length;i+=3){const o=vertex++*12;data.set([-positions[i],positions[i+2],positions[i+1],-normals[i],normals[i+2],normals[i+1],...color,piece.group==='terrain'?1:piece.group==='bridges'?2:0,id],o);maxZ=Math.max(maxZ,positions[i+1]);}
      for(const i of ix)indices[at++]=i+start;
      if(color[3]>=.99)solidCount=at;
    }
    if(vbo)gl.deleteBuffer(vbo);if(ibo)gl.deleteBuffer(ibo);vbo=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vbo);gl.bufferData(gl.ARRAY_BUFFER,data,gl.STATIC_DRAW);ibo=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ibo);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,indices,gl.STATIC_DRAW);
    totalCount=indexCount;pieces=manifest.pieces;region=768;selected=0;zoom=1;active=true;$('#scene').hidden=true;canvas.hidden=false;$('#scene-empty').hidden=true;$('#scene-badge').textContent='真实网格已加载';$('#scene-stats').textContent=`${pieces.length} 个源网格 · ${Math.round(indexCount/3).toLocaleString()} 三角形 · 768 × 768 m`;
    $('#cut-height').max=Math.ceil(maxZ);$('#cut-height').value=Math.ceil(maxZ);$('#cut-value').textContent='全部';$('#selection').textContent='实际GLB三角网；拖动旋转、上下拖动俯仰、滚轮缩放、点击查看源ID。';redraw();
  }};
}
