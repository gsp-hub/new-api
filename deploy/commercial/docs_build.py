#!/usr/bin/env python3
# Build the commercial gateway docs page from live pricing JSON.
import json, html, re

D = json.load(open('/tmp/commdocs/pricing.json'))['data']
BASE = 'https://model.51a.online'

def price(x):
    return f"${x:g}"

def esc_h(s):
    return s.replace('&', '&amp;').replace('<', '&lt;')

def single_code(body):
    return ('<div class="codewrap"><pre class="plain"><code>' + esc_h(body) + '</code></pre>'
            '<button class="copy" onclick="cp(this)">复制</button></div>')

def tabs_block(items):
    bars = ''.join(f'<button class="{"on" if i == 0 else ""}">{esc_h(t)}</button>' for i, (t, _) in enumerate(items))
    panes = ''.join(
        f'<div class="tabpane" style="{"display:none" if i else ""}"><div class="codewrap" style="margin:0"><pre><code>{esc_h(b)}</code></pre>'
        f'<button class="copy" onclick="cp(this)">复制</button></div></div>'
        for i, (_, b) in enumerate(items))
    return f'<div class="tabgroup"><div class="tabbar">{bars}</div>{panes}</div>'

def table(headers, rows):
    h = ''.join(f'<th>{x}</th>' for x in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<div class="tblwrap"><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>'

def model_tables():
    out = []
    for vendor, label in [('gpt', 'GPT'), ('glm', 'GLM'), ('deepseek', 'DeepSeek')]:
        rows = []
        for m in sorted(D, key=lambda x: x['model_name']):
            name = m['model_name']
            if name.endswith('[1M]') or not name.startswith(vendor):
                continue
            desc = (m.get('description') or '').strip()
            desc = re.sub(r'价格 in[^。]*。?\s*$', '', desc).strip()
            if m.get('quota_type') == 1:
                inout = f"{price(m['model_price'])} / 次"
            else:
                r = m['model_ratio'] * 2
                c = r * (m.get('completion_ratio') or 1)
                inout = f"{price(r)} / {price(c)}"
            flag = ' <span class="tag">分时</span>' if vendor == 'deepseek' and 'flash' in name else ''
            rows.append((f'<td class="mono">{html.escape(name)}{flag}</td>', f'<td class="mono">{inout}</td>',
                         f'<td class="desc">{html.escape(desc)}</td>'))
        if rows:
            out.append(f'<h3 class="mvendor">{label}</h3>')
            out.append(table(['模型', '输入 / 输出（$/1M tokens）', '适用场景'], rows))
    return '\n'.join(out)

sections = []

# ---------------- 1 快速开始 ----------------
sections.append(('quickstart', '快速开始', f'''
<p>三步开始使用：</p>
<ol class="steps">
<li><b>注册并登录</b> — 在 <a href="{BASE}/register" target="_blank">注册页</a>创建账号（需邮箱验证）。</li>
<li><b>创建 API Key</b> — 控制台「令牌」页新建令牌，复制 <code>sk-...</code> 开头的密钥。</li>
<li><b>选工具照着填</b> — 见下方「工具接入」章节，地址和 Key 全站通用。</li>
</ol>
<p>核心信息只有两样：<b>Base URL</b> = <code>{BASE}</code>，<b>API Key</b> = 你的 <code>sk-...</code>。</p>
'''))

# ---------------- 2 模型与价格 ----------------
sections.append(('models', '模型与价格', f'''
<p>以下为当前在售模型，价格对齐官方 API。标注 <span class="tag">分时</span> 的模型按峰谷计费（详见计费说明）。</p>
{model_tables()}
<p class="note">模型名加 <code>[1M]</code> 后缀（如 <code>glm-5.2[1M]</code>）表示超长上下文版本，适合 27 万 token 以上的请求，超长部分按官方阶梯价计费。</p>
'''))

# ---------------- 3 SDK 调用 ----------------
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
sections.append(('sdk', 'SDK 调用', f'''
<p>网关同时兼容三种协议，同一密钥通用：</p>
<ul class="proto">
<li><code>/v1/chat/completions</code> — OpenAI Chat 格式（绝大多数工具和 SDK）</li>
<li><code>/v1/messages</code> — Anthropic Claude 格式（Claude Code 等原生接入）</li>
<li><code>/v1/images/generations</code> — 图像生成（gpt-image 系列）</li>
</ul>
{tabs_block([('cURL', curl_first), ('Python', py_first), ('Node.js', node_first)])}
'''))

# ---------------- 4 工具接入 ----------------
generic_tbl = table(['字段', '填写'], [
    ('<td>API 地址 / Base URL</td>', f'<td class="mono">{BASE}/v1</td>'),
    ('<td>API Key</td>', '<td>你创建的 <code>sk-...</code></td>'),
    ('<td>模型名称</td>', '<td>先用 <code>glm-4.6</code> 或 <code>gpt-6-luna</code> 测试</td>'),
])
cc_tbl = table(['模型映射', '示例值', '用途'], [
    ('<td class="mono">ANTHROPIC_MODEL</td>', '<td class="mono">gpt-6-luna</td>', '<td>主模型</td>'),
    ('<td class="mono">ANTHROPIC_DEFAULT_SONNET_MODEL</td>', '<td class="mono">gpt-6-luna</td>', '<td>Sonnet 档任务</td>'),
    ('<td class="mono">ANTHROPIC_DEFAULT_OPUS_MODEL</td>', '<td class="mono">gpt-6.1-terra</td>', '<td>Opus 档任务</td>'),
    ('<td class="mono">ANTHROPIC_DEFAULT_HAIKU_MODEL</td>', '<td class="mono">glm-4.6</td>', '<td>后台轻量任务</td>'),
])
claude_json = f'''{{
  "env": {{
    "ANTHROPIC_BASE_URL": "{BASE}",
    "ANTHROPIC_AUTH_TOKEN": "sk-填写你自己的Key",
    "ANTHROPIC_MODEL": "gpt-6-luna",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-6-luna",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-6.1-terra",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.6"
  }}
}}'''
claude_env = f'''export ANTHROPIC_BASE_URL={BASE}
export ANTHROPIC_AUTH_TOKEN=sk-你的密钥
export ANTHROPIC_MODEL=gpt-6-luna
claude'''

sections.append(('tools', '工具接入', f'''
<h3 id="tool-generic" style="margin-top:0">通用配置</h3>\n<p>大多数工具只需要填三项。在工具的「设置 → 模型服务 / 提供商」里新增自定义服务，协议选 <b>OpenAI 兼容（OpenAI Compatible）</b>：</p>
{generic_tbl}
<p>保存后新建对话，问一句"你好"，能收到回复就接好了。想换 GPT / GLM / DeepSeek，只在工具里切换模型名，<b>地址和 Key 不变</b>。</p>

<h3 id="tool-cherry">Cherry Studio</h3>
<p>打开 <b>设置 → 模型服务 → 添加提供商</b>，选择 OpenAI 兼容，按上表填三项，保存后启用模型，在聊天窗口选择刚添加的模型即可。</p>

<h3 id="tool-vscode">VS Code（Cline / Roo Code 等）</h3>
<p>提供商选 <b>OpenAI Compatible</b>，Base URL 填 <code>{BASE}/v1</code>，API Key 填自己的 Key，模型名填 <code>gpt-6-luna</code> 或 <code>glm-4.6</code>。如果插件会自动拼 <code>/v1</code>，把地址改成 <code>{BASE}</code>。</p>

<h3 id="tool-claude">Claude Code</h3>
<p>Claude Code 用 <b>Anthropic 兼容协议</b>，与其他工具不同：<b>Base URL 不带 <code>/v1</code></b>。</p>
{tabs_block([('环境变量（推荐）', claude_env), ('settings.json', claude_json)])}
<p>用 CC Switch 管理多个供应商的用户：在 <b>CC Switch → Claude Code → 添加供应商</b> 选「自定义」（不是 Anthropic 官方），API URL 填 <code>{BASE}</code>，密钥填自己的 Key，并在高级设置里核对下面的模型映射——<b>只填地址和 Key、不配四个模型映射，会出现 <code>model_not_found</code></b>：</p>
{cc_tbl}
<p class="note">如果你曾在终端设置过 <code>ANTHROPIC_BASE_URL</code> 等环境变量，旧值可能覆盖新配置；修改后完全退出并重新打开工具。</p>

<h3 id="tool-codex">Codex CLI</h3>
<p>Base URL 填 <code>{BASE}/v1</code>，API Key 填自己的 Key，模型选 GPT 系列（复杂代码任务可从 <code>gpt-6.1-terra</code> 开始）。新版 Codex CLI 使用 <code>/v1/responses</code> 端点，如遇 <code>reasoning.context</code> 相关 400 报错，需要在配置中关闭 <code>use_responses_lite</code>——这不是 Key 无效，属于进阶配置，可参考 Codex 文档或联系我们协助。</p>
'''))

# ---------------- 5 模型怎么选 ----------------
pick_tbl = table(['想做什么', '先试这个模型', '说明'], [
    ('<td>日常聊天、写文案</td>', '<td class="mono">glm-4.6 / glm-5.2</td>', '<td>GLM 系适合作为日常入口</td>'),
    ('<td>写代码：主流 GLM</td>', '<td class="mono">glm-5.2 / glm-5.3</td>', '<td>两个主流模型都值得按任务试用</td>'),
    ('<td>写代码：GPT 起步</td>', '<td class="mono">gpt-6-luna</td>', '<td>一般代码任务的性价比之选</td>'),
    ('<td>写代码：复杂任务</td>', '<td class="mono">gpt-6.1-terra</td>', '<td>复杂代码优先从这里试</td>'),
    ('<td>写代码：更强效果</td>', '<td class="mono">gpt-6-sol / gpt-6.1-sol</td>', '<td>需要更强效果时再切换</td>'),
    ('<td>写代码：最强效果</td>', '<td class="mono">gpt-6-astra</td>', '<td>效果优先，更耗时、更消耗额度</td>'),
    ('<td>看图、读截图</td>', '<td class="mono">glm-4.6v</td>', '<td>上传图片提问；"识图"不是"生图"</td>'),
    ('<td>生成一张图片</td>', '<td class="mono">gpt-image-2.5</td>', '<td>走图像生成端点，见 SDK 章节</td>'),
    ('<td>更长上下文</td>', '<td class="mono">[1M] 后缀模型</td>', '<td>模型名与模型广场完全一致</td>'),
])
sections.append(('pick', '模型怎么选', f'''
{pick_tbl}
<p class="note">GPT、GLM、DeepSeek 全系<b>共用一套 Key、一套网关地址</b>。完整模型清单与实时价格以控制台「模型广场」为准；个别渠道因上游额度暂时不可用时，网关会自动切换到其他可用渠道。</p>
'''))

# ---------------- 6 计费说明 ----------------
sections.append(('billing', '计费说明', f'''
<ul class="faq">
<li><b>计价单位</b>：按 token 用量计费，价格对齐各模型官方 API。</li>
<li><b>缓存折扣</b>：命中提示词缓存的输入按官方缓存价计费（约为输入价的 10%），长会话/Agent 场景成本大幅降低。</li>
<li><b>分时计价</b>：个别模型（详见价格表标注）在工作日 9-12 点、14-18 点按峰值价计费，其余时段 8 折。</li>
<li><b>充值汇率</b>：按充值时页面展示的汇率结算，充值余额永不过期。</li>
<li><b>账单透明</b>：控制台「日志」可逐条核对每次请求的 token 数与费用。</li>
</ul>
'''))

# ---------------- 7 FAQ ----------------
sections.append(('faq', '常见问题', '''
<ul class="faq">
<li><b>支持流式输出吗？</b> 支持，所有文本模型均可 <code>stream: true</code>。</li>
<li><b>一个密钥能换模型吗？</b> 能。密钥与模型无关，请求里改 <code>model</code> 字段即可。</li>
<li><b>401 / Invalid token？</b> Key 复制不完整或已删除，回到控制台重新复制。</li>
<li><b>404？</b> 地址路径不对。聊天工具用 <code>/v1</code> 结尾的地址，Claude Code 用不带 <code>/v1</code> 的根地址。</li>
<li><b>503 model_not_found？</b> 模型名拼写与模型广场不一致（注意大小写与 <code>[1M]</code> 后缀）。</li>
<li><b>报 429 怎么办？</b> 触发了使用限制（速率或套餐额度），稍后重试或升级套餐。</li>
<li><b>数据安全？</b> 请求内容仅用于本次转发与计费统计，不用于训练。</li>
</ul>
'''))

TOC_SUBS = {
    'tools': [
        ('tool-generic', '通用配置'),
        ('tool-cherry', 'Cherry Studio'),
        ('tool-vscode', 'VS Code 插件'),
        ('tool-claude', 'Claude Code'),
        ('tool-codex', 'Codex CLI'),
    ],
}

def toc_html():
    out = []
    for sid, title, _ in sections:
        subs = TOC_SUBS.get(sid, [])
        if subs:
            out.append(f'<div class="tocgroup"><a class="tocparent" href="#{sid}" onclick="tg(event,this)">{html.escape(title)}<span class="chev">›</span></a><div class="tocsub">')
            out.extend(f'<a href="#{ssid}">{esc_h(st)}</a>' for ssid, st in subs)
            out.append('</div></div>')
        else:
            out.append(f'<a href="#{sid}">{html.escape(title)}</a>')
    return '\n'.join(out)

# ---------------- page ----------------
html_doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<script>(function(){{try{{var m=localStorage.getItem('newapi:theme:v1:mode');if(m==='light'||m==='dark'){{document.documentElement.dataset.theme=m;}}}}catch(e){{}}}})();</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>51a Online · AI API 文档</title>
<style>
:root {{
  --bg: #ffffff; --bg2: #f6f7f9; --fg: #1a1d23; --fg2: #555b66;
  --line: #e5e7eb; --acc: #4f46e5; --accbg: #eef2ff;
  --code-bg: #0f172a; --code-fg: #e2e8f0;
}}
:root[data-theme='dark'] {{ --bg: #0f1115; --bg2: #16181e; --fg: #e6e8ec; --fg2: #9aa1ad; --line: #262a33; --acc: #818cf8; --accbg: #1e1b4b; --code-bg: #020617; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme='light']) {{ --bg: #0f1115; --bg2: #16181e; --fg: #e6e8ec; --fg2: #9aa1ad; --line: #262a33; --acc: #818cf8; --accbg: #1e1b4b; --code-bg: #020617; }} }}
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
:root[data-theme='dark'] .tag {{ color: #fcd34d; background: #3b2f0b; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme='light']) .tag {{ color: #fcd34d; background: #3b2f0b; }} }}
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
.topnav {{ position: sticky; top: 0; z-index: 50; display: flex; align-items: center; gap: 28px; padding: 0 32px; height: 56px; background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(10px); border-bottom: 1px solid var(--line); }}
.topnav .brand {{ font-weight: 700; font-size: 15px; color: var(--fg); letter-spacing: -.2px; }}
.topnav .brand span {{ color: var(--acc); }}
.topnav .tlinks {{ display: flex; gap: 4px; margin-left: auto; }}
.topnav .tlinks a {{ color: var(--fg2); font-size: 14px; padding: 6px 14px; border-radius: 8px; }}
.topnav .tlinks a:hover {{ color: var(--fg); background: var(--bg2); text-decoration: none; }}
.topnav .tlinks a.active {{ color: var(--acc); background: var(--accbg); font-weight: 500; }}
.topnav .console {{ margin-left: 12px; background: var(--acc); color: #fff !important; border-radius: 8px; padding: 6px 16px !important; font-weight: 500; }}
.topnav .console:hover {{ opacity: .88; background: var(--acc); }}
.tocgroup .tocparent {{ display: flex; justify-content: space-between; align-items: center; }}
.chev {{ display: inline-block; transition: transform .2s; color: var(--fg2); font-size: 15px; }}
.tocgroup.open .chev {{ transform: rotate(90deg); }}
.tocsub {{ display: none; }}
.tocgroup.open .tocsub {{ display: block; }}
.tocsub a {{ padding-left: 38px !important; font-size: 13px !important; }}
@media (max-width: 900px) {{ .layout {{ display: block; }} nav.toc {{ display: none; }} main {{ padding: 24px; }} }}
</style>
</head>
<body>
<nav class="topnav">
  <a class="brand" href="/">51a<span>.online</span></a>
  <div class="tlinks">
    <a href="/">首页</a>
    <a href="/pricing">模型广场</a>
    <a href="/docs" class="active">文档</a>
    <a href="/about">关于</a>
    <a href="/dashboard" class="console">控制台</a>
  </div>
</nav>
<header class="hero"><div class="in">
<h1>51a Online · AI API 文档</h1>
<p>一个密钥访问 GPT / GLM / DeepSeek —— 官方协议兼容，按量计费，缓存享折扣</p>
<div class="badges"><span>OpenAI 兼容</span><span>Claude Messages 兼容</span><span>流式输出</span><span>提示词缓存价</span></div>
</div></header>
<div class="layout">
<nav class="toc" id="toc">
{toc_html()}
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
function tg(e, el) {{ el.parentElement.classList.toggle('open'); }}
document.querySelectorAll('.tabbar').forEach(bar => {{
  bar.addEventListener('click', e => {{
    if (e.target.tagName !== 'BUTTON') return;
    bar.querySelectorAll('button').forEach(b => b.classList.remove('on'));
    e.target.classList.add('on');
    const wrap = bar.parentElement;
    wrap.querySelectorAll('.tabpane').forEach((p, i) => p.style.display = (bar.children[i] === e.target) ? '' : 'none');
  }});
}});
const links = document.querySelectorAll('#toc a');
const obs = new IntersectionObserver(entries => {{
  entries.forEach(en => {{
    if (en.isIntersecting) {{
      links.forEach(l => l.classList.toggle('active', l.getAttribute('href') === '#' + en.target.id));
    }}
  }});
}}, {{ rootMargin: '-30% 0px -60% 0px' }});
document.querySelectorAll('main section').forEach(s => obs.observe(s));
document.querySelectorAll('.tocgroup').forEach(g => {{
  const subLinks = g.querySelectorAll('.tocsub a');
  if (!subLinks.length) return;
  const subObs = new IntersectionObserver(entries => {{
    entries.forEach(en => {{
      if (en.isIntersecting) {{
        subLinks.forEach(l => l.classList.toggle('active', l.getAttribute('href') === '#' + en.target.id));
        g.classList.add('open');
      }}
    }});
  }}, {{ rootMargin: '-25% 0px -70% 0px' }});
  subLinks.forEach(l => {{
    const t = document.querySelector(l.getAttribute('href'));
    if (t) subObs.observe(t);
  }});
}});
</script>
</body>
</html>'''

open('/tmp/commdocs/index.html', 'w').write(html_doc)
print('written', len(html_doc), 'bytes,', sum(s.count('<tr>') for s in [html_doc]) , 'rows')
