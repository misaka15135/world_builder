import {$, notify} from '../core/ui.js';
export function composer(sample, start) {
  let mode = 'fixture', busy = false, submitting = false, config, draft = {prompt:'', region:128, seed:1};
  function render() {
    document.querySelectorAll('[data-mode]').forEach(node => { node.classList.toggle('selected', node.dataset.mode === mode); node.disabled = busy; });
    $('#prompt').readOnly = mode === 'fixture'; $('#region').readOnly = mode === 'fixture'; $('#seed').readOnly = mode === 'fixture';
    $('#mode-note').textContent = mode === 'fixture' ? '人工固定响应 · 不联网、不消耗 API 额度。用于验证完整流程。' : '使用自己的模型理解场景。首次可从小区域、少量建筑开始。';
    $('#model-label').textContent = mode === 'fixture' ? '无需密钥 · 固定响应' : config?.model || '请先配置 API';
    $('#budget-label').textContent = `最多 ${config?.limits?.max_calls ?? '—'} 次调用`;
    $('#run').disabled = busy;
    $('#run').textContent = busy ? '正在构建…' : '开始构建 ↗';
  }
  function switchMode(next) {
    if (mode === 'api') draft = {prompt:$('#prompt').value, region:$('#region').value, seed:$('#seed').value};
    mode = next;
    $('#prompt').value = mode === 'fixture' ? sample.prompt : draft.prompt;
    $('#prompt').placeholder = '例如：一条河畔商业街，包含两层旅店、木构商铺与公共广场……';
    $('#region').value = mode === 'fixture' ? sample.region_m : draft.region;
    $('#seed').value = mode === 'fixture' ? sample.seed : draft.seed;
    render();
  }
  document.querySelectorAll('[data-mode]').forEach(node => node.onclick = () => switchMode(node.dataset.mode));
  $('#composer').onsubmit = async event => {
    event.preventDefault(); if (busy) return;
    busy = true; submitting = true; render();
    try { await start({mode, prompt:$('#prompt').value, region_m:Number($('#region').value), seed:Number($('#seed').value), minecraft:$('#export-minecraft').checked, unity:$('#export-unity').checked}); }
    catch (error) { notify(error.message, true); busy = false; render(); }
    finally { submitting = false; }
  };
  switchMode(mode);
  return {setConfig(value) { config = value; render(); }, setBusy(value) { if (!submitting && busy !== value) { busy = value; render(); } }};
}
