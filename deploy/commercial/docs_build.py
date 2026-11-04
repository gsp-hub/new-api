#!/usr/bin/env python3
# Build the commercial gateway docs page from live pricing JSON.
import json, html, re

D = json.load(open('/tmp/commdocs/pricing.json'))['data']
BASE = 'https://model.51a.online'

def price(x):
    return f"${x:g}"

def model_rows():
    rows = []
    for m in sorted(D, key=lambda x: x['model_name']):
        name = m['model_name']
        if name.endswith('[1M]'):
            continue
        desc = (m.get('description') or '').strip()
        # drop trailing price sentence, keep guidance
        desc = re.sub(r'价格 in[^。]*。?\s*$', '', desc).strip()
        if m.get('quota_type') == 1:
            inout = f"{price(m['model_price'])} / 次"
        else:
            r = m['model_ratio'] * 2
            c = r * (m.get('completion_ratio') or 1)
            inout = f"{price(r)} / {price(c)}"
        vendor = ''
        vmap = [('gpt', 'GPT'), ('glm', 'GLM'), ('deepseek', 'DeepSeek')]
        for k, label in vmap:
            if name.startswith(k):
                vendor = label
        rows.append((vendor, name, inout, desc))
    return rows

VENDOR_ORDER = ['GPT', 'GLM', 'DeepSeek']

def table_html():
    out = []
    for vendor in VENDOR_ORDER:
        rows = [r for r in model_rows() if r[0] == vendor]
        if not rows:
            continue
        out.append(f'<h3 class="mvendor">{vendor}</h3>')
        out.append('<div class="tblwrap"><table><thead><tr><th>模型</th><th>输入 / 输出（$/1M tokens）</th><th>适用场景</th></tr></thead><tbody>')
        for _, name, inout, desc in rows:
            flag = ' <span class="tag">分时</span>' if 'flash' in name and 'deepseek' in name else ''
            out.append(f'<tr><td class="mono">{html.escape(name)}{flag}</td><td class="mono">{inout}</td><td class="desc">{html.escape(desc)}</td></tr>')
        out.append('</tbody></table></div>')
    return '\n'.join(out)

code_blocks = {}

def code(lang, body):
    bid = f"c{len(code_blocks)}"
    code_blocks[bid] = (lang, body)
    return bid

# ---------- content sections ----------
def esc_h(s):
    return s.replace('&', '&amp;').replace('<', '&lt;')

def single_code(lang, body):
    return ('<div class="codewrap"><pre class="plain"><code>' + esc_h(body) + '</code></pre>'
            '<button class="copy" onclick="cp(this)">复制</button></div>')

def tabs_block(group, items):
    bars = ''.join(f'<button class="{"on" if i == 0 else ""}">{esc_h(t)}</button>' for i, (t, _) in enumerate(items))
    panes = ''.join(
        f'<div class="tabpane" style="{"display:none" if i else ""}"><div class="codewrap" style="margin:0"><pre><code>{esc_h(b)}</code></pre>'
        f'<button class="copy" onclick="cp(this)">复制</button></div></div>'
        for i, (_, b) in enumerate(items))
    return f'<div class="tabgroup"><div class="tabbar">{bars}</div>{panes}</div>'

sections = []

sections.append(('quickstart', '快速开始', f'''
<p>三步开始使用：</p>
<ol class="steps">
<li><b>注册并登录</b> — 在 <a href="{BASE}/register" target="_blank">注册页</a>创建账号（需邮箱验证）。</li>
<li><b>创建 API Key</b> — 控制台「令牌」页新建令牌，复制 <code>sk-...</code> 开头的密钥。</li>
<li><b>发起第一个请求</b> — Base URL 固定为 <code>{BASE}/v1</code>，与 OpenAI SDK 完全兼容。</li>
</ol>
'''))

sections.append(('models', '模型与价格', f'''
<p>以下为当前在售模型，价格对齐官方 API。标注 <span class="tag">分时</span> 的模型按峰谷计费（详见计费说明）。</p>
{table_html()}
<p class="note">模型名加 <code>[1M]</code> 后缀（如 <code>glm-5.2[1M]</code>）表示超长上下文版本，适合 27 万 token 以上的请求，超长部分按官方阶梯价计费。</p>
'''))

curl_first = f'''curl {BASE}/v1/chat/completions \\
  -H "Authorization: Bearer sk-你的密钥" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "glm-5.2",
    "messages": [{{"role": "user", "content": "你好"}}]
  }}'
'''
py_first = '''from openai import OpenAI

client = OpenAI(
    base_url="''' + BASE + '''/v1",
    api_key="sk-你的密钥",
)

resp = client.chat.completions.create(
    model="glm-5.2",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
'''
node_first = '''import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "''' + BASE + '''/v1",
  apiKey: "sk-你的密钥",
});

const resp = await client.chat.completions.create({
  model: "glm-5.2",
  messages: [{ role: "user", content: "你好" }],
});
console.log(resp.choices[0].message.content);
'''

sections.append(('clients', '客户端接入', f'''
<p>网关同时兼容三种协议，同一密钥通用：</p>
<ul class="proto">
<li><code>/v1/chat/completions</code> — OpenAI Chat 格式</li>
<li><code>/v1/messages</code> — Anthropic Claude 格式（Claude Code 等原生接入）</li>
<li><code>/v1/images/generations</code> — 图像生成（gpt-image 系列）</li>
</ul>
{tabs_block('first', [('cURL', curl_first), ('Python', py_first), ('Node.js', node_first)])}
<h3>Claude Code</h3>
{single_code('bash', f'''# 环境变量方式（推荐）
export ANTHROPIC_BASE_URL={BASE}
export ANTHROPIC_AUTH_TOKEN=sk-你的密钥
export ANTHROPIC_MODEL=glm-5.2
claude''')}
<h3>Codex CLI / 其他 OpenAI 兼容客户端</h3>
{single_code('bash', f'''# 任何支持自定义 base_url 的工具
Base URL: {BASE}/v1
API Key:  sk-你的密钥
Model:    按需选择，如 gpt-6-sol / glm-5.2 / deepseek-flash''')}
'''))

sections.append(('billing', '计费说明', f'''
<ul class="faq">
<li><b>计价单位</b>：按 token 用量计费，价格对齐各模型官方 API。</li>
<li><b>缓存折扣</b>：命中提示词缓存的输入按官方缓存价计费（约为输入价的 10%），长会话/Agent 场景成本大幅降低。</li>
<li><b>DeepSeek 分时</b>：<code>deepseek-flash</code> 系列按峰谷计价——工作日 9-12 点、14-18 点为峰值价，其余时段（含夜间与周末）为峰值 8 折。</li>
<li><b>充值汇率</b>：按充值时页面展示的汇率结算，充值余额永不过期。</li>
<li><b>账单透明</b>：控制台「日志」可逐条核对每次请求的 token 数与费用。</li>
</ul>
'''))

sections.append(('faq', '常见问题', '''
<ul class="faq">
<li><b>支持流式输出吗？</b> 支持，所有文本模型均可 <code>stream: true</code>。</li>
<li><b>一个密钥能换模型吗？</b> 能。密钥与模型无关，请求里改 <code>model</code> 字段即可。</li>
<li><b>想用 Claude 格式（/v1/messages）？</b> 直接调用即可，网关自动做协议转换，包括工具调用与思考块。</li>
<li><b>报 429 怎么办？</b> 触发了使用限制（速率或套餐额度），稍后重试或升级套餐。</li>
<li><b>数据安全？</b> 请求内容仅用于本次转发与计费统计，不用于训练。</li>
</ul>
'''))

html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>51a Online · AI API 文档</title>
<style>
:root {{
  --bg: #ffffff; --bg2: #f6f7f9; --fg: #1a1d23; --fg2: #555b66;
  --line: #e5e7eb; --acc: #4f46e5; --accbg: #eef2ff;
  --code-bg: #0f172a; --code-fg: #e2e8f0;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #0f1115; --bg2: #16181e; --fg: #e6e8ec; --fg2: #9aa1ad; --line: #262a33; --acc: #818cf8; --accbg: #1e1b4b; --code-bg: #020617; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, "PingFang SC", "Segoe UI", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--fg); line-height: 1.75; }}
a {{ color: var(--acc); text-decoration: none; }} a:hover {{ text-decoration: underline; }}
.mono, code {{ font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}
code {{ background: var(--accbg); color: var(--acc); padding: 2px 6px; border-radius: 5px; font-size: .88em; }}
header.hero {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); color: #fff; padding: 56px 24px 88px; }}
header.hero .in {{ max-width: 1080px; margin: 0 auto; }}
header.hero h1 {{ margin: 0 0 10px; font-size: 34px; letter-spacing: -.5px; }}
header.hero p {{ margin: 0; opacity: .9; font-size: 16px; }}
header.hero .badges {{ margin-top: 18px; }}
header.hero .badges span {{ display: inline-block; background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.25); border-radius: 999px; padding: 4px 14px; font-size: 13px; margin-right: 8px; }}
.layout {{ max-width: 1080px; margin: -56px auto 80px; padding: 0 24px; display: flex; gap: 40px; }}
nav.toc {{ width: 220px; flex-shrink: 0; position: sticky; top: 24px; align-self: flex-start; background: var(--bg); border: 1px solid var(--line); border-radius: 14px; padding: 18px 0; box-shadow: 0 8px 24px rgba(0,0,0,.06); max-height: calc(100vh - 48px); overflow: auto; }}
nav.toc a {{ display: block; padding: 8px 22px; color: var(--fg2); font-size: 14px; border-left: 3px solid transparent; }}
nav.toc a.active, nav.toc a:hover {{ color: var(--acc); border-left-color: var(--acc); background: var(--accbg); text-decoration: none; }}
main {{ flex: 1; min-width: 0; background: var(--bg); border: 1px solid var(--line); border-radius: 14px; padding: 40px 48px; box-shadow: 0 8px 24px rgba(0,0,0,.06); }}
section {{ padding-bottom: 40px; margin-bottom: 40px; border-bottom: 1px solid var(--line); }}
section:last-child {{ border: none; margin-bottom: 0; }}
h2 {{ font-size: 24px; margin: 0 0 18px; letter-spacing: -.3px; }}
h3 {{ font-size: 18px; margin: 28px 0 12px; }}
ol.steps li {{ margin: 10px 0; }}
.tblwrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th {{ text-align: left; color: var(--fg2); font-weight: 600; padding: 10px 12px; border-bottom: 2px solid var(--line); white-space: nowrap; }}
td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; }}
tr:hover td {{ background: var(--bg2); }}
td.desc {{ color: var(--fg2); font-size: 13px; max-width: 380px; }}
.tag {{ display: inline-block; font-size: 11px; color: #b45309; background: #fef3c7; border-radius: 4px; padding: 0 6px; margin-left: 6px; }}
@media (prefers-color-scheme: dark) {{ .tag {{ color: #fcd34d; background: #3b2f0b; }} }}
.note {{ background: var(--accbg); border-radius: 10px; padding: 12px 16px; font-size: 14px; color: var(--fg2); }}
.proto li {{ margin: 6px 0; }}
.faq li {{ margin: 12px 0; }}
.faq b {{ color: var(--fg); }}
.tabbar {{ display: flex; gap: 4px; margin-bottom: -1px; position: relative; z-index: 2; }}
.tabbar button {{ border: 1px solid var(--line); border-bottom: none; background: var(--bg2); color: var(--fg2); padding: 7px 16px; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 13px; }}
.tabbar button.on {{ background: var(--code-bg); color: var(--code-fg); border-color: var(--code-bg); }}
.codewrap {{ position: relative; }}
.codewrap pre {{ margin: 0; background: var(--code-bg); color: var(--code-fg); border-radius: 0 10px 10px 10px; overflow-x: auto; }}
.codewrap pre.plain {{ border-radius: 10px; }}
.codewrap pre code {{ background: none; color: inherit; padding: 0; font-size: 13px; line-height: 1.7; }}
.copy {{ position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,.12); color: #cbd5e1; border: none; border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer; }}
.copy:hover {{ background: rgba(255,255,255,.22); }}
footer {{ text-align: center; color: var(--fg2); font-size: 13px; padding: 30px 0 50px; }}
@media (max-width: 900px) {{ .layout {{ display: block; }} nav.toc {{ display: none; }} main {{ padding: 24px; }} }}
</style>
</head>
<body>
<header class="hero"><div class="in">
<h1>51a Online · AI API 文档</h1>
<p>一个密钥访问 GPT / GLM / DeepSeek —— 官方协议兼容，按量计费，缓存享折扣</p>
<div class="badges"><span>OpenAI 兼容</span><span>Claude Messages 兼容</span><span>流式输出</span><span>提示词缓存价</span></div>
</div></header>
<div class="layout">
<nav class="toc" id="toc">
{chr(10).join(f'<a href="#{sid}">{html.escape(title)}</a>' for sid, title, _ in sections)}
</nav>
<main>
{chr(10).join(f'<section id="{sid}"><h2>{html.escape(title)}</h2>{body}</section>' for sid, title, body in sections)}
</main>
</div>
<footer>51a.online · AI Gateway — 文档更新于 2026-11</footer>
<script>
function cp(btn) {{
  const code = btn.parentElement.querySelector('code').innerText;
  navigator.clipboard.writeText(code).then(() => {{ btn.textContent = '已复制 ✓'; setTimeout(() => btn.textContent = '复制', 1500); }});
}}
// tab switching
document.querySelectorAll('.tabbar').forEach(bar => {{
  bar.addEventListener('click', e => {{
    if (e.target.tagName !== 'BUTTON') return;
    bar.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    e.target.classList.add('on');
    const wrap = bar.parentElement;
    wrap.querySelectorAll('.tabpane').forEach((p, i) => p.style.display = (bar.children[i] === e.target) ? '' : 'none');
  }});
}});
// scrollspy
const links = document.querySelectorAll('#toc a');
const obs = new IntersectionObserver(entries => {{
  entries.forEach(en => {{
    if (en.isIntersecting) {{
      links.forEach(l => l.classList.toggle('active', l.getAttribute('href') === '#' + en.target.id));
    }}
  }});
}}, {{ rootMargin: '-30% 0px -60% 0px' }});
document.querySelectorAll('main section').forEach(s => obs.observe(s));
</script>
</body>
</html>'''

open('/tmp/commdocs/index.html', 'w').write(html_doc)
print('written', len(html_doc))
