import {$, notify} from '../core/ui.js';
export function composer(sample, nature, start) {
  let mode='fixture',busy=false,submitting=false,config;
  const drafts={legacy:{prompt:'',region:128,seed:1},nature047:{prompt:nature.prompt,region:768,seed:46}};
  let pipeline=$('#pipeline').value;
  function render() {
    const natural=pipeline==='nature047',fixed=natural||mode==='fixture';
    document.querySelectorAll('[data-mode]').forEach(n=>{n.classList.toggle('selected',n.dataset.mode===mode);n.disabled=busy;});
    $('#pipeline').disabled=busy;
    $('#prompt').readOnly=mode==='fixture';$('#region').readOnly=fixed;$('#seed').readOnly=fixed;
    $('#region').min=natural?768:32;$('#region').max=natural?768:512;
    $('#export-minecraft').disabled=natural;$('#export-unity').disabled=natural;
    if(natural){$('#export-minecraft').checked=false;$('#export-unity').checked=true;}
    $('#mode-note').textContent=natural ? `${nature.scope} ${mode==='fixture'?'离线重建046录制参数，不是新的模型生成。':'仅描述本周范围内的偏好；超出范围会明确拒绝。'}` : mode==='fixture'?'人工固定响应 · 不联网，用于验证旧流程。':'旧版32—512米盒体原型；不具备本周山谷详细构建能力。';
    $('#model-label').textContent=mode==='fixture'?'无需密钥 · 0 次 API':config?.model||'请先配置 API';
    $('#budget-label').textContent=mode==='fixture'?'本地验证与完整导出':`最多 ${Math.min(natural?6:128,config?.limits?.max_calls??128)} 次调用`;
    $('#run').disabled=busy;$('#run').textContent=busy?'正在构建…':natural&&mode==='fixture'?'重建山谷示例 · 无需 API':'开始构建 ↗';
  }
  function saveDraft(){if(mode==='api')drafts[pipeline]={prompt:$('#prompt').value,region:$('#region').value,seed:$('#seed').value};}
  function fill(){
    const natural=pipeline==='nature047',draft=drafts[pipeline];
    $('#prompt').value=mode==='fixture'?(natural?nature.prompt:sample.prompt):draft.prompt;
    $('#prompt').placeholder=natural?'例如：山势柔和一些、树林更茂密、河流弯曲一些。':'描述旧版原型支持的建筑街景。';
    $('#region').value=natural?768:mode==='fixture'?sample.region_m:draft.region;
    $('#seed').value=natural?46:mode==='fixture'?sample.seed:draft.seed;
    render();
  }
  $('#pipeline').onchange=()=>{saveDraft();pipeline=$('#pipeline').value;fill();};
  document.querySelectorAll('[data-mode]').forEach(n=>n.onclick=()=>{saveDraft();mode=n.dataset.mode;fill();});
  $('#composer').onsubmit=async event=>{
    event.preventDefault();if(busy)return;busy=true;submitting=true;render();
    try{await start({pipeline,mode,prompt:$('#prompt').value,region_m:Number($('#region').value),seed:Number($('#seed').value),minecraft:$('#export-minecraft').checked,unity:$('#export-unity').checked});}
    catch(error){notify(error.message,true);busy=false;render();}finally{submitting=false;}
  };
  fill();
  return {setConfig(value){config=value;render();},setBusy(value){if(!submitting&&busy!==value){busy=value;render();}}};
}
