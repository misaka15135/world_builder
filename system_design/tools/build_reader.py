#!/usr/bin/env python3
"""Build a self-contained offline architecture reader from Markdown and SVG."""
from pathlib import Path
import base64
import html
import re
import markdown
root = Path(__file__).resolve().parents[1]
files = [root / 'README.md'] + sorted(root.glob('[0-9][0-9]_*.md')) + [root / 'VERIFICATION.md']
nav, body = [], []
for file in files:
    if not file.exists():
        continue
    text = file.read_text(encoding='utf-8')
    title = text.splitlines()[0].lstrip('# ')
    section_id = file.stem
    nav.append(f'<a href="#{section_id}">{html.escape(title)}</a>')
    rendered = markdown.markdown(text, extensions=['tables', 'fenced_code', 'sane_lists'])
    rendered = rendered.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    for other in files:
        rendered = rendered.replace('href="' + other.name + '"', 'href="#' + other.stem + '"')
    def image(match):
        path = root / match.group(1)
        if path.suffix == '.svg' and path.exists():
            data = base64.b64encode(path.read_bytes()).decode()
            return 'src="data:image/svg+xml;base64,' + data + '"'
        return match.group(0)
    rendered = re.sub(r'src="([^"]+)"', image, rendered)
    body.append(f'<article id="{section_id}">{rendered}</article>')
style = '''
:root{--ink:#193047;--muted:#607286;--line:#dce4ea;--accent:#196d7d;--paper:#fff}
*{box-sizing:border-box}body{overflow-wrap:anywhere;margin:0;background:#f2f5f7;color:var(--ink);font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Noto Sans CJK SC",sans-serif}nav{position:fixed;width:270px;height:100vh;overflow:auto;background:#142b3e;color:#fff;padding:28px 20px}nav strong{font-size:21px;display:block;margin-bottom:20px}nav a{display:block;color:#d9e8f1;font-size:13px;text-decoration:none;padding:8px 9px;border-bottom:1px solid #ffffff16}nav a:hover{background:#24435a}nav input{width:100%;padding:9px;margin-bottom:16px;border:1px solid #476174;background:#203d51;color:white;border-radius:5px}main{margin-left:270px;padding:38px 48px;max-width:1510px}article{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:40px 46px;margin-bottom:28px;scroll-margin-top:24px}h1{font-size:30px;line-height:1.45;margin-top:0;color:#153e55}h2{font-size:22px;margin-top:34px;border-bottom:2px solid #dbe9ee;padding-bottom:9px}h3{font-size:18px;margin-top:25px}p{margin:13px 0}a{color:var(--accent)}table{width:100%;border-collapse:collapse;font-size:14px;margin:20px 0;display:table} .table-wrap{overflow:auto}th{background:#eaf1f5;text-align:left}td,th{border:1px solid var(--line);padding:10px 12px;vertical-align:top;min-width:110px}tr:nth-child(even){background:#fafcfd}pre{background:#142b3e;color:#e6f2fb;padding:18px;border-radius:6px;overflow:auto;font-size:13px;line-height:1.6}code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:.89em}p code,td code{background:#eff3f6;padding:2px 4px;overflow-wrap:anywhere}img{display:block;max-width:100%;max-height:1100px;margin:22px auto;border:1px solid #e5ebef;padding:12px;background:#fff}blockquote{border-left:4px solid #4790a2;padding:8px 18px;margin:18px 0;background:#eff7f8}.hidden{display:none}.meta{font-size:12px;color:#b4cad9}@media(max-width:850px){nav{position:relative;width:100%;height:auto}nav a{display:inline-block}main{margin:0;padding:15px}article{padding:24px 20px}h1{font-size:25px}}@media print{nav{display:none}main{margin:0;padding:0}article{border:0;break-before:page;padding:0}table{font-size:10px}body{font-size:12px}img{max-height:800px}}
'''
script = '''document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('main article').forEach(a=>a.classList.toggle('hidden',q&&!a.textContent.toLowerCase().includes(q)));});document.querySelectorAll('nav a').forEach(a=>a.addEventListener('click',()=>{document.querySelector('#search').value='';document.querySelectorAll('article').forEach(x=>x.classList.remove('hidden'));}));'''
page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>World Builder · 系统架构设计</title><style>'+style+'</style><nav><strong>WORLD BUILDER</strong><div class="meta">系统架构 · design-2026-11-11<br>目标设计 / 尚未实施</div><br><input id="search" aria-label="搜索章节内容" placeholder="搜索章节内容">'+''.join(nav)+'</nav><main>'+''.join(body)+'</main><script>'+script+'</script></html>'
(root / 'index.html').write_text(page, encoding='utf-8')
print('Built offline reader:', len(files), 'chapters')
