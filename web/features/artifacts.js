import {api} from '../core/api.js';
import {$, element, bytes, notify, showDocument} from '../core/ui.js';
export function artifacts() {
  let job;
  $('#inspect-document').onclick = async () => {
    const path = $('#document-select').value; if (!job || !path) return;
    const id = job.id;
    try { const doc = await api.document(id, path); let content = doc.text; if (path.endsWith('.json')) content = JSON.stringify(JSON.parse(content), null, 2); showDocument(path, content); }
    catch (error) { notify(error.message, true); }
  };
  return {render(value) {
    const signature = JSON.stringify([value?.id, value?.resources]); if (job?._signature === signature) return;
    job = value ? {...value, _signature:signature} : null;
    const files = job?.resources || [], list = $('#artifacts'); list.replaceChildren();
    $('#resource-count').textContent = `${files.length} 个文件`;
    const featured = files.filter(item => ['.worldpkg','.glb','.schem'].some(ext => item.path.endsWith(ext)) || ['result.json','repository/scene.world.json'].includes(item.path));
    for (const file of featured) { const link = element('a','artifact'); link.href = api.download(job.id,file.path); link.setAttribute('download',''); const label = file.path.endsWith('.worldpkg') ? 'WIR 世界包' : file.path.endsWith('.glb') ? 'Unity · GLB 网格' : file.path.endsWith('.schem') ? 'Minecraft · '+file.path.split('/').pop() : file.path === 'result.json' ? '运行结果摘要' : 'WIR 源数据'; link.append(element('span','file-icon','↧'),element('span','',label),element('small','',bytes(file.bytes))); list.append(link); }
    if (!featured.length) list.append(element('p','empty-note','完成后可下载世界包、目标文件与运行记录。'));
    const select = $('#document-select'), previous = select.value; select.replaceChildren(element('option','','选择运行文件')); select.firstChild.value = '';
    for (const file of files.filter(f => /\.jsonl?$/.test(f.path))) {
      const hash = file.path.split('/')[1], event = file.kind === 'call' ? job.events.find(e => e.event === 'request' && e.request_id === `sha256:${hash}`) : null;
      const label = event ? `${event.stage} / ${event.scope_id} · 尝试 ${event.attempt} · ${file.path.split('/').pop()}` : file.path;
      const option = element('option','',label); option.value = file.path; select.append(option);
    }
    if (files.some(f => f.path === previous)) select.value = previous;
  }};
}
