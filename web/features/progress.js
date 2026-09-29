import {$, element, terminal, statusLabel, modeLabel} from '../core/ui.js';
export const stages = [{id:'A',name:'场景理解',detail:'需求与约束'}, {id:'B',name:'地形规划',detail:'地势与水体'}, {id:'C',name:'风物清单',detail:'类型与数量'}, {id:'D',name:'空间分配',detail:'区块与选址'}, {id:'E',name:'单体设计',detail:'构件与通路'}, {id:'F',name:'场景审查',detail:'验收与返工'}];
export function progress({cancel, replay}) {
  const nodes = new Map();
  for (const stage of stages) { const card = element('div', 'stage-card'); card.append(element('div','stage-letter',stage.id),element('h3','',stage.name),element('p','',stage.detail)); const state = element('span','stage-state','等待'); card.append(state); $('#stages').append(card); nodes.set(stage.id,{card,state}); }
  $('#cancel-run').onclick = cancel; $('#replay-run').onclick = replay;
  return {render(job) {
    const events = job?.events || [], scopes = {}, invalid = new Set();
    for (const event of events) {
      if (event.event === 'invalidated') { invalid.add(event.stage); scopes[event.stage] = {}; }
      if (['request','accepted','rejected'].includes(event.event)) { invalid.delete(event.stage); (scopes[event.stage] ||= {})[event.scope_id] = event.event; }
    }
    for (const [id,{card,state}] of nodes) {
      const values = Object.values(scopes[id] || {}), accepted = values.filter(x => x === 'accepted').length;
      let cls = 'waiting', label = invalid.has(id) ? '待重新生成' : '等待';
      if (values.length) {
        if (values.every(x => x === 'accepted')) { cls = 'done'; label = id === 'E' ? `${accepted} 个场地通过` : '已通过'; }
        else if (values.includes('request')) { cls = terminal(job.status) ? 'failed' : 'active'; label = terminal(job.status) ? '未完成' : id === 'E' ? `${accepted}/${values.length} 已通过` : '进行中'; }
        else { cls = 'failed'; label = terminal(job.status) ? '未通过' : '修复中'; }
      }
      card.className = `stage-card ${cls}`; state.textContent = label;
    }
    $('#job-status').textContent = job?.phase === 'compiling' ? '本地编译与导出' : job ? statusLabel(job.status) : '尚未运行';
    $('#job-status').className = `pill ${job?.status || ''}`;
    $('#cancel-run').hidden = !job || terminal(job.status); $('#cancel-run').disabled = job?.status === 'cancelling';
    $('#cancel-run').textContent = job?.status === 'cancelling' ? '等待请求结束…' : '取消运行';
    $('#replay-run').hidden = !job || !terminal(job.status) || !events.some(e => e.event === 'request');
    $('#run-meta').textContent = job ? `${modeLabel(job.mode)} · ${job.id.slice(0,8)} · ${job.region_m} × ${job.region_m} m · seed ${job.seed}` : 'A → B / C 并行 → D → 多个 E → F → 本地编译';
    const result = job?.result;
    $('#usage').textContent = result ? `${result.provider_calls ?? 0} 次调用 · ${result.accounted_tokens ?? 0} tokens · ${result.elapsed_s ?? '—'} s` : `${events.filter(e => e.event === 'request').length} 次调用记录`;
    $('#job-error').hidden = !job?.error; $('#job-error').textContent = job?.error ? `${job.error.code} · ${job.error.message}` : '';
    const list = $('#event-list'); list.replaceChildren();
    const visible = events.filter(e => ['request','accepted','rejected','invalidated','revision_requested','planning_completed','failed'].includes(e.event));
    if (!visible.length) list.append(element('p','empty-note','开始构建后，在这里查看每个阶段的接受、拒绝与返工。'));
    visible.slice(-70).reverse().forEach(event => {
      const row = element('div',`event-row ${event.event}`);
      row.append(element('span','event-dot',event.event === 'accepted' ? '✓' : event.event === 'rejected' ? '!' : '·'));
      const text = element('div'); const label = ({request:'发起调用',accepted:'本地校验通过',rejected:'响应被拒绝',invalidated:'依赖变化，结果失效',revision_requested:'请求局部返工',planning_completed:'全部计划已接受',failed:'运行终止'})[event.event];
      text.append(element('strong','',`${event.stage || '系统'} ${event.scope_id && event.scope_id !== 'scene' ? ' / '+event.scope_id : ''}`),element('span','',label + (event.code ? ` · ${event.code}` : ''))); row.append(text); list.append(row);
    });
  }};
}
