import {$, notify} from '../core/ui.js';
import {api} from '../core/api.js';
const STORAGE = 'world-builder.settings.v1';
export function settings(bootstrap, changed) {
  let config = structuredClone(bootstrap.config), pendingKey = '';
  const desktop = bootstrap.settings_persistence === 'application';
  if (!desktop) try { const saved = JSON.parse(localStorage.getItem(STORAGE)); if (saved?.contract_version === config.contract_version) config = saved; } catch { /* Storage is optional. */ }
  const fill = () => {
    $('#setting-endpoint').value = config.endpoint; $('#setting-model').value = config.model;
    $('#setting-protocol').value = config.protocol; $('#setting-key').value = pendingKey;
    const {endpoint, model, protocol, ...advanced} = config;
    $('#advanced-config').value = JSON.stringify(advanced, null, 2);
    $('#settings-error').textContent = '';
    $('#credential-note').textContent = bootstrap.credential_available ? '服务启动时已检测到默认密钥环境变量。' : '服务端默认密钥环境变量尚未配置。';
  };
  const open = () => { fill(); $('#settings-dialog').showModal(); };
  $('#settings-top').onclick = open; $('#settings-side').onclick = open;
  $('#reset-settings').onclick = () => { config = structuredClone(bootstrap.config); pendingKey = ''; fill(); };
  $('#settings-form').onsubmit = async event => {
    event.preventDefault();
    try {
      const advanced = JSON.parse($('#advanced-config').value);
      const allowed = ['contract_version','api_key_env','response_format','token_parameter','stage_models','limits'];
      if (!advanced || Array.isArray(advanced) || Object.keys(advanced).some(k => !allowed.includes(k)) || allowed.some(k => !(k in advanced))) throw new Error('高级配置只能包含原有六个配置字段，密钥请填写在专用输入框。');
      if (!advanced.limits || !advanced.stage_models) throw new Error('缺少 limits 或 stage_models。');
      const candidate = {...advanced, endpoint: $('#setting-endpoint').value.trim(), model: $('#setting-model').value.trim(), protocol: $('#setting-protocol').value};
      await api.validateConfig(candidate);
      if (desktop) await api.savePreferences(candidate);
      config = candidate;
      pendingKey = $('#setting-key').value; $('#setting-key').value = '';
      if (!desktop) try { localStorage.setItem(STORAGE, JSON.stringify(config)); } catch { notify('浏览器存储不可用，设置仅在当前页面有效。'); }
      changed(config); $('#settings-dialog').close(); notify('设置已保存。填写的密钥仅用于下一次 API 运行。');
    } catch (error) { $('#settings-error').textContent = error.message; }
  };
  // Closing without saving must also clear the password DOM node.
  $('#settings-dialog').addEventListener('close', () => { $('#setting-key').value = ''; });
  changed(config);
  return {get: () => structuredClone(config), takeKey() { const key = pendingKey; pendingKey = ''; return key; }, open};
}
