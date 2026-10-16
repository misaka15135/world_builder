import {api} from './core/api.js';
import {createStore} from './core/store.js';
import {$, element, terminal, notify, showDocument} from './core/ui.js';
import {settings} from './features/settings.js';
import {composer} from './features/composer.js';
import {progress, stages} from './features/progress.js';
import {history} from './features/history.js';
import {artifacts} from './features/artifacts.js';
import {preview} from './features/preview.js';
import {meshPreview} from './features/mesh_preview.js';
import {adjustments} from './features/adjustments.js';

const state=createStore({selected:null,job:null,jobs:[],page:'studio'});
let sequence=0, sceneId=null, connectionReady=false;
const scene=preview(), files=artifacts();
const mesh=meshPreview();let adjust;
function page(name) {state.set({page:name});document.querySelectorAll('[data-page]').forEach(n=>n.classList.toggle('active',n.dataset.page===name));document.querySelectorAll('.page').forEach(n=>n.hidden=n.id!==`page-${name}`);$('#page-name').textContent=({studio:'世界实验台',history:'运行档案',agents:'智能体与契约'})[name];}
document.querySelectorAll('[data-page]').forEach(node=>node.onclick=()=>page(node.dataset.page));
document.querySelectorAll('[data-close]').forEach(node=>node.onclick=()=>document.getElementById(node.dataset.close).close());
const archive=history(async id=>{select(id);page('studio');await refresh();});
function select(id) {sequence++;state.set({selected:id,job:null});sceneId=null;mesh.clear();scene.clear();files.render(null);flow.render(null);adjust?.render(null,false);}
const flow=progress({cancel:async()=>{try{await api.cancel(state.get().selected);await refresh();notify('取消已请求。已发出的 API 请求会等待其返回或超时；已进入编译的任务会保留完整结果。');}catch(error){notify(error.message,true);}},replay:async()=>{try{const job=await api.create({mode:'replay',replay_id:state.get().selected});select(job.id);await refresh();notify('已启动精确回放，沿用原需求、配置与导出选项。');}catch(error){notify(error.message,true);}}});
let brief, preferences;
async function refresh() {
  const generation=sequence;
  try {
    const {jobs}=await api.jobs();state.set({jobs});archive.render(jobs);brief?.setBusy(jobs.some(j=>!terminal(j.status)));
    if(!state.get().selected&&jobs.length)select(jobs[0].id);
    const id=state.get().selected, ticket=sequence;
    if(id){const job=await api.job(id);if(ticket!==sequence)return;state.set({job});flow.render(job);files.render(job);adjust?.render(job,jobs.some(j=>!terminal(j.status)));
      if(job.scene_available&&sceneId!==id&&sceneId!==`loading:${id}`){sceneId=`loading:${id}`;
        try{if(job.pipeline==='nature047'){
          const [buffer,map]=await Promise.all([api.resource(id,'unity/scene.glb'),api.resource(id,'unity/manifest.json')]);if(ticket!==sequence)return;
          mesh.load(buffer,JSON.parse(new TextDecoder().decode(map)));
        }else{const data=await api.scene(id);if(ticket!==sequence)return;mesh.clear();scene.load(data);}sceneId=id;}
        catch(error){sceneId=null;notify(`预览加载失败：${error.message}。源文件可在交付区下载。`,true);}
      }}
    $('#connection').textContent='本地服务已连接';$('#connection').classList.remove('offline');
  }catch(error){if(generation!==sequence)return;$('#connection').textContent='服务连接中断';$('#connection').classList.add('offline');notify(error.message || '无法连接本地服务，请确认启动窗口仍在运行。',true);}
}
$('#refresh-history').onclick=refresh;
async function poll() {if(connectionReady)await refresh();setTimeout(poll,1200);}
try {
  const boot=await api.bootstrap();
  const start=async spec=>{const config=spec.mode==='api'?preferences.get():spec.pipeline==='nature047'?boot.nature.default_config:boot.config,api_key=spec.mode==='api'?preferences.takeKey():undefined;const job=await api.create({...spec,config,api_key});select(job.id);notify(spec.mode==='adjust'?'已开始受限参数重建，0次API；旧版本保留。':spec.mode==='fixture'?'已开始离线重建，0次API。本地检查和导出需要几分钟。':'已开始真实API生成，先检查本周支持范围。');await refresh();};
  brief=composer(boot.sample,boot.nature,start);adjust=adjustments(boot.nature,start);
  const placeholder=boot.config.model==='yourapi'&&boot.config.endpoint.includes('yourapi');
  preferences=settings({...boot,config:placeholder?boot.nature.default_config:boot.config},config=>brief.setConfig(config));
  for(const stage of stages){const card=element('article','agent-card');card.append(element('span','agent-letter',stage.id),element('h2','',stage.name),element('p','',stage.detail));const btn=element('button','button quiet','查看运行 Skill ↗');btn.onclick=()=>showDocument(`Agent ${stage.id} · SKILL.md`,boot.skills.find(s=>s.stage===stage.id)?.text || '未加载');const schema=element('button','button quiet','JSON 契约');schema.onclick=async()=>{try{showDocument(`Agent ${stage.id} · JSON Schema`,JSON.stringify(await api.contract(stage.id),null,2));}catch(error){notify(error.message,true);}};const actions=element('div','agent-actions');actions.append(btn,schema);card.append(actions);$('#agent-cards').append(card);}
  connectionReady=true;await refresh();poll();
}catch(error){notify(`无法启动测试台：${error.message}。确认本地服务运行后刷新页面。`,true);$('#connection').textContent='连接失败';$('#run').disabled=true;}
