"""Minimal web chat UI using only the standard library (http.server)."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .assistant import HelpdeskAssistant

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>IT Helpdesk Assistant</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f3f4f6;margin:0}
.wrap{max-width:760px;margin:0 auto;padding:24px}
h1{font-size:22px;margin:0 0 4px} .sub{color:#6b7280;margin-bottom:16px}
#log{display:flex;flex-direction:column;gap:12px;margin-bottom:16px}
.msg{padding:12px 14px;border-radius:10px;white-space:pre-wrap;line-height:1.45}
.me{background:#1d4ed8;color:#fff;align-self:flex-end;max-width:80%}
.bot{background:#fff;border:1px solid #e5e7eb}
.meta{font-size:12px;color:#6b7280;margin-top:8px}
.tag{display:inline-block;background:#eef2ff;color:#3730a3;border-radius:4px;padding:1px 6px;margin-right:4px}
form{display:flex;gap:8px} input{flex:1;padding:12px;border:1px solid #d1d5db;border-radius:8px;font-size:15px}
button{padding:12px 18px;border:0;border-radius:8px;background:#1d4ed8;color:#fff;font-size:15px;cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.chip{background:#fff;border:1px solid #d1d5db;border-radius:999px;padding:6px 10px;font-size:13px;cursor:pointer}
</style></head><body><div class="wrap">
<h1>IT Helpdesk Assistant</h1>
<div class="sub">Answers come only from the IT knowledge base, with citations. Anything else is triaged into a ticket.</div>
<div class="chips">
<span class="chip">I'm locked out of my account</span><span class="chip">VPN says certificate not trusted</span>
<span class="chip">I got a new phone for MFA</span><span class="chip">I clicked a phishing link</span>
<span class="chip">How do I submit an expense report?</span></div>
<div id="log"></div>
<form id="f"><input id="q" placeholder="Describe your issue..." autocomplete="off"><button>Ask</button></form>
</div><script>
const log=document.getElementById('log'),q=document.getElementById('q');
function add(cls,html){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=html;log.appendChild(d);d.scrollIntoView();}
function esc(s){return s.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function ask(text){add('me',esc(text));
 const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})});
 const a=await r.json();
 let meta='<div class="meta"><span class="tag">'+a.mode+'</span>';
 if(a.triage) meta+='<span class="tag">'+a.triage.category+'</span><span class="tag">'+a.triage.priority+'</span>';
 meta+='</div>';
 const src=a.sources.length?'<div class="meta">Sources: '+a.sources.map(esc).join(' &middot; ')+'</div>':'';
 add('bot',esc(a.answer).replace(/\\*\\*(.+?)\\*\\*/g,'<b>$1</b>')+src+meta);}
document.getElementById('f').onsubmit=e=>{e.preventDefault();if(q.value.trim()){ask(q.value.trim());q.value='';}};
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>ask(c.textContent));
</script></body></html>"""


def serve(port: int = 8000) -> None:
    bot = HelpdeskAssistant()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/ask":
                return self._send(404, "not found", "text/plain")
            length = min(int(self.headers.get("Content-Length", 0)), 10_000)
            try:
                question = json.loads(self.rfile.read(length) or b"{}").get("question", "").strip()[:1000]
            except json.JSONDecodeError:
                return self._send(400, json.dumps({"error": "invalid JSON"}), "application/json")
            if not question:
                return self._send(400, json.dumps({"error": "question is required"}), "application/json")
            self._send(200, json.dumps(bot.ask(question).to_dict()), "application/json")

        def log_message(self, fmt, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Helpdesk assistant running at http://127.0.0.1:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
