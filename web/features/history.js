import {$, element, statusLabel, modeLabel} from '../core/ui.js';
export function history(open) {
  return {render(jobs) {
    $('#history-count').textContent = jobs.length; const list = $('#history-list'); list.replaceChildren();
    if (!jobs.length) { list.append(element('div','history-empty','还没有运行档案。返回实验台，开始第一次构建。')); return; }
    for (const job of jobs) {
      const card = element('button','history-card'); card.type = 'button'; card.onclick = () => open(job.id);
      const top = element('div','history-card-top'); top.append(element('span','small muted',`${modeLabel(job.mode)} / ${job.id.slice(0,8)}`),element('span',`pill ${job.status}`,statusLabel(job.status)));
      card.append(top,element('h3','',job.prompt),element('p','',`${job.region_m} m · seed ${job.seed} · ${new Date(job.created_at).toLocaleString('zh-CN')}`),element('span','history-open','打开运行 →')); list.append(card);
    }
  }};
}
