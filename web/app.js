import {api} from './core/api.js';
import {createStore} from './core/store.js';
import {$, element, terminal, notify, showDocument} from './core/ui.js';
import {settings} from './features/settings.js';
import {composer} from './features/composer.js';
import {progress, stages} from './features/progress.js';
import {history} from './features/history.js';
import {artifacts} from './features/artifacts.js';
import {preview} from './features/preview.js';

const state=createStore({selected:null,job:null,jobs:[],page:'studio'});
let sequence=0, sceneId=null, connectionReady=false;
const scene=preview(), files=artifacts();
function page(name) {state.set({page:name});document.querySelectorAll('[data-page]').forEach(n=>n.classList.toggle('active',n.dataset.page===name));document.querySelectorAll('.page').forEach(n=>n.hidden=n.id!==`page-${name}`);$('#page-name').textContent=({studio:'世界实验台',history:'运行档案',agents:'智能体与契约'})[name];}
document.querySelectorAll('[data-page]').forEach(node=>node.onclick=()=>page(node.dataset.page));
document.querySelectorAll('[data-close]').forEach(node=>node.onclick=()=>document.getElementById(node.dataset.close).close());
const archive=history(async id=>{select(id);page('studio');await refresh();});
function select(id) {sequence++;state.set({selected:id,job:null});sceneId=null;scene.clear();files.render(null);flow.render(null);}
const flow=progress({cancel:async()=>{try{await api.cancel(state.get().selected);await refresh();notify('取消已请求。已发出的 API 请求会等待其返回或超时；已进入编译的任务会保留完整结果。');}catch(error){notify(error.message,true);}},replay:async()=>{try{const job=await api.create({mode:'replay',replay_id:state.get().selected});select(job.id);await refresh();notify('已启动精确回放，沿用原需求、配置与导出选项。');}catch(error){notify(error.message,true);}}});
let brief, preferences;
async function refresh() {
  const generation=sequence;
  try {
    const {jobs}=await api.jobs();state.set({jobs});archive.render(jobs);brief?.setBusy(jobs.some(j=>!terminal(j.status)));
    if(!state.get().selected&&jobs.length)select(jobs[0].id);
    const id=state.get().selected, ticket=sequence;
    if(id){const job=await api.job(id);if(ticket!==sequence)return;state.set({job});flow.render(job);files.render(job);
      if(job.scene_available&&sceneId!==id){const data=await api.scene(id);if(ticket!==sequence)return;scene.load(data);sceneId=id;}}
    $('#connection').textContent='本地服务已连接';$('#connection').classList.remove('offline');
  }catch(error){if(generation!==sequence)return;$('#connection').textContent='服务连接中断';$('#connection').classList.add('offline');notify(error.message || '无法连接本地服务，请确认启动窗口仍在运行。',true);}
}
$('#refresh-history').onclick=refresh;
async function poll() {if(connectionReady)await refresh();setTimeout(poll,1200);}
try {
  const boot=await api.bootstrap();
  brief=composer(boot.sample,async spec=>{const config=preferences.get(),api_key=spec.mode==='api'?preferences.takeKey():undefined;const job=await api.create({...spec,config,api_key});select(job.id);notify(spec.mode==='fixture'?'已启动固定响应样例。它验证程序闭环，不代表真实模型质量。':'已启动模型生成。');await refresh();});
  preferences=settings(boot,config=>brief.setConfig(config));
  for(const stage of stages){const card=element('article','agent-card');card.append(element('span','agent-letter',stage.id),element('h2','',stage.name),element('p','',stage.detail));const btn=element('button','button quiet','查看运行 Skill ↗');btn.onclick=()=>showDocument(`Agent ${stage.id} · SKILL.md`,boot.skills.find(s=>s.stage===stage.id)?.text || '未加载');const schema=element('button','button quiet','JSON 契约');schema.onclick=async()=>{try{showDocument(`Agent ${stage.id} · JSON Schema`,JSON.stringify(await api.contract(stage.id),null,2));}catch(error){notify(error.message,true);}};const actions=element('div','agent-actions');actions.append(btn,schema);card.append(actions);$('#agent-cards').append(card);}
  connectionReady=true;await refresh();poll();
}catch(error){notify(`无法启动测试台：${error.message}。确认本地服务运行后刷新页面。`,true);$('#connection').textContent='连接失败';$('#run').disabled=true;}
