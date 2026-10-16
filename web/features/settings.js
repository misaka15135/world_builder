import {$, notify} from '../core/ui.js';
import {api} from '../core/api.js';
const STORAGE = 'world-builder.settings.v1';
export function settings(bootstrap, changed) {
  let config = structuredClone(bootstrap.config), pendingKey = '', statusSequence = 0;
  const desktop = bootstrap.settings_persistence === 'application';
  const secure = desktop && bootstrap.credential_storage === 'windows_dpapi';
  let remember = secure;
  if (!desktop) try { const saved = JSON.parse(localStorage.getItem(STORAGE)); if (saved?.contract_version === config.contract_version) config = saved; } catch { /* Storage is optional. */ }
  const updateCredential = async () => {
    const ticket = ++statusSequence, endpoint = $('#setting-endpoint').value.trim();
    $('#clear-key').disabled = true;
    if (!secure) { $('#credential-note').textContent = '此入口不支持安全记住密钥。填写的密钥仅供下一次API运行；不会以明文保存。'; return; }
    try {
      const status = await api.credentialStatus(endpoint);
      if (ticket !== statusSequence || endpoint !== $('#setting-endpoint').value.trim()) return;
      $('#clear-key').disabled = !status.saved && !status.error;
      $('#credential-note').textContent = status.error || (status.saved
        ? '当前API地址已保存密钥，重启后自动复用；密码框留空，不会读回显示。'
        : '当前API地址尚未保存密钥。勾选“记住”并保存后，重启无需重复输入。');
      if (!$('#remember-key').checked) $('#credential-note').textContent += ' 不勾选并保存将清除该地址已保存密钥，新输入仅用于下一次运行。';
    } catch (error) { if (ticket === statusSequence) $('#credential-note').textContent = error.message; }
  };
  const fill = () => {
    $('#setting-endpoint').value = config.endpoint; $('#setting-model').value = config.model;
    $('#setting-protocol').value = config.protocol; $('#setting-key').value = pendingKey;
    $('#remember-key').checked = remember; $('#remember-key').disabled = !secure;
    $('#clear-key').hidden = !secure;
    const {endpoint, model, protocol, ...advanced} = config;
    $('#advanced-config').value = JSON.stringify(advanced, null, 2);
    $('#settings-error').textContent = ''; updateCredential();
  };
  const open = () => { fill(); $('#settings-dialog').showModal(); };
  $('#settings-top').onclick = open; $('#settings-side').onclick = open;
  $('#setting-endpoint').oninput = updateCredential;
  $('#remember-key').onchange = updateCredential;
  $('#reset-settings').onclick = () => { config = structuredClone(bootstrap.config); pendingKey = ''; fill(); };
  $('#deepseek-preset').onclick = () => { config = structuredClone(bootstrap.nature.default_config); pendingKey = ''; fill(); };
  $('#clear-key').onclick = async () => {
    const endpoint = $('#setting-endpoint').value.trim();
    if (!confirm('清除当前API地址在本机保存的密钥？不会删除历史场景或服务端环境变量。')) return;
    try { await api.clearCredential(endpoint); pendingKey = ''; $('#setting-key').value = ''; await updateCredential(); notify('已清除该API地址在本机保存的密钥。'); }
    catch (error) { $('#settings-error').textContent = error.message; }
  };
  $('#settings-form').onsubmit = async event => {
    event.preventDefault();
    try {
      const advanced = JSON.parse($('#advanced-config').value);
      const required = ['contract_version','api_key_env','response_format','token_parameter','stage_models','limits'];
      const allowed = (bootstrap.config_fields || required).filter(k => !['endpoint','model','protocol'].includes(k));
      if (!advanced || Array.isArray(advanced) || Object.keys(advanced).some(k => !allowed.includes(k)) || required.some(k => !(k in advanced))) throw new Error('高级配置包含未知字段或缺少必要字段；密钥只能填写在专用输入框。');
      if (!advanced.limits || !advanced.stage_models) throw new Error('缺少 limits 或 stage_models。');
      const candidate = {...advanced, endpoint: $('#setting-endpoint').value.trim(), model: $('#setting-model').value.trim(), protocol: $('#setting-protocol').value};
      const key = $('#setting-key').value.trim(), keep = secure && $('#remember-key').checked;
      await api.validateConfig(candidate);
      if (desktop) await api.savePreferences(candidate);
      let saved = false;
      if (secure) {
        if (keep && key) saved = (await api.saveCredential(candidate.endpoint, key)).saved;
        else if (keep) saved = (await api.credentialStatus(candidate.endpoint)).saved;
        if (!keep) await api.clearCredential(candidate.endpoint);
      }
      config = candidate; remember = keep;
      pendingKey = keep ? '' : key; $('#setting-key').value = '';
      if (!desktop) try { localStorage.setItem(STORAGE, JSON.stringify(config)); } catch { notify('浏览器存储不可用，设置仅在当前页面有效。'); }
      changed(config); $('#settings-dialog').close();
      notify(saved ? '设置已保存。该API地址的已保存密钥将在重启后自动复用。' : keep ? '设置已保存；尚未填写并保存密钥。' : '设置已保存。新输入的密钥仅用于下一次API运行，未保存在本机。');
    } catch (error) { $('#settings-error').textContent = error.message; }
  };
  $('#settings-dialog').addEventListener('close', () => { statusSequence++; $('#setting-key').value = ''; });
  changed(config);
  return {get: () => structuredClone(config), takeKey() { const key = pendingKey; pendingKey = ''; return key; }, open};
}
