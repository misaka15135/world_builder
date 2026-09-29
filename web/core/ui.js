export const $ = selector => document.querySelector(selector);
export function element(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
export const terminal = status => ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(status);
export const statusLabel = status => ({running:'运行中',cancelling:'正在取消',succeeded:'已完成',failed:'失败',cancelled:'已取消',interrupted:'已中断'})[status] || '等待运行';
export const modeLabel = mode => ({fixture:'离线样例',api:'真实 API',replay:'历史回放'})[mode] || mode;
export const bytes = value => value < 1024 ? `${value} B` : value < 1048576 ? `${(value / 1024).toFixed(1)} KB` : `${(value / 1048576).toFixed(1)} MB`;
export function notify(message, error = false) { const node = $('#notice'); node.textContent = message; node.classList.toggle('error', error); node.hidden = !message; }
export function showDocument(title, content) { $('#document-title').textContent = title; $('#document-content').textContent = content; if (!$('#document-dialog').open) $('#document-dialog').showModal(); }
