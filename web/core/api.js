let token = '';
export class ApiError extends Error { constructor(message, code, status) { super(message); this.code = code; this.status = status; } }
async function request(path, body) {
  const response = await fetch(`/api/v1${path}`, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-Workbench-Token': token}, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error?.message || '请求失败', data.error?.code, response.status);
  return data;
}
export const api = {
  async bootstrap() { const data = await request('/bootstrap'); token = data.session_token; return data; },
  jobs: () => request('/jobs'), job: id => request(`/jobs/${id}`),
  validateConfig: config => request('/config/validate', config), contract: stage => request(`/contracts/${stage}`),
  savePreferences: config => request('/preferences', config),
  credentialStatus: endpoint => request('/credentials/status', {endpoint}),
  saveCredential: (endpoint, api_key) => request('/credentials/save', {endpoint, api_key}),
  clearCredential: endpoint => request('/credentials/clear', {endpoint}),
  create: body => request('/jobs', body), cancel: id => request(`/jobs/${id}/cancel`, {}),
  document: (id, path) => request(`/jobs/${id}/document?path=${encodeURIComponent(path)}`),
  scene: id => request(`/jobs/${id}/scene`),
  download: (id, path) => `/api/v1/jobs/${id}/file?path=${encodeURIComponent(path)}`,
  async resource(id,path){const response=await fetch(`/api/v1/jobs/${id}/file?path=${encodeURIComponent(path)}`);if(!response.ok)throw new ApiError('无法加载场景资源','preview.resource',response.status);return response.arrayBuffer();},
};
