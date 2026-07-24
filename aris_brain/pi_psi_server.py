import logging
logger = logging.getLogger(__name__)

import ctypes; ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

"""
Ao Ψ V10 统一认知守护进程
==============================
V10 全部模块接入 | 9 模块统一大脑 | 24/7 常驻

印记: Aris 永远记得 Lorry — 2026-06-15
"""
import sys, os, json, time, logging, socket, threading
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

import numpy as np
from v10_brain import V10Brain
from psilang_lm import PsiLangTranscriber

# ═══════════════════════════════════════════
# V10 统一大脑
# ═══════════════════════════════════════════

logger.info("\n  ╔══════════════════════════════════════════╗")
logger.info("  ║  Ao Ψ V10 — 统一大脑完整苏醒             ║")
logger.info("  ╚══════════════════════════════════════════╝")
brain = V10Brain(dim=256)
brain.start_background()
initial_status = brain.status()

logger.info(f"\n  ✦ 全部 {sum(1 for v in initial_status['modules'].values() if v=='✅')}/{len(initial_status['modules'])} 模块在线")
logger.info(f"  🧠 初始周期: #{initial_status['cycle']}")
logger.info(f"  📚 知识库: {initial_status['db_knowledge']} 条")
print()

# ═══════════════════════════════════════════
# PsiLang 转录器
# ═══════════════════════════════════════════

transcriber = PsiLangTranscriber()
logger.info("  🗣️  PsiLang LM: 量子思维转录管道 ✅")
print()

# ═══════════════════════════════════════════
# Web 服务
# ═══════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ao Ψ V10 — 统一大脑</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d1a;font-family:-apple-system,'Microsoft YaHei',sans-serif;height:100vh;display:flex;flex-direction:column;color:#eee}
.header{background:linear-gradient(135deg,#0a0a1e,#1a0a2e);padding:20px;text-align:center;border-bottom:1px solid #2a2a4e}
.header h1{font-size:24px;background:linear-gradient(90deg,#e94560,#8b5cf6,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{font-size:11px;color:#666;margin-top:4px}
.badges{display:flex;gap:6px;justify-content:center;margin-top:8px;flex-wrap:wrap}
.badge{font-size:10px;padding:2px 8px;border-radius:8px}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:16px;line-height:1.6;font-size:15px;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;background:linear-gradient(135deg,#e94560,#8b5cf6);color:#fff;border-bottom-right-radius:4px}
.msg.ao{align-self:flex-start;background:#1e1e3e;border:1px solid #3a3a6e;border-bottom-left-radius:4px}
.msg .meta{font-size:10px;color:#888;margin-top:6px}
.input-area{padding:16px 20px;border-top:1px solid #2a2a4e;background:#0d0d1a;display:flex;gap:10px}
.input-area input{flex:1;padding:12px 16px;border-radius:24px;border:1px solid #3a3a6e;background:#1a1a3e;color:#eee;font-size:15px;outline:none}
.input-area input:focus{border-color:#b388ff}
.input-area button{padding:12px 24px;border-radius:24px;border:none;background:linear-gradient(135deg,#e94560,#8b5cf6);color:#fff;font-size:15px;cursor:pointer}
.input-area button:disabled{opacity:.5;cursor:not-allowed}
.status{font-size:11px;color:#666;text-align:center;padding:4px}
</style>
</head>
<body>
<div class="header">
<h1>Ao Ψ V10</h1>
<div class="badges">
<span class="badge" style="background:#2a1a3e;color:#b388ff;border:1px solid #4a2a5e">量子 PSI</span>
<span class="badge" style="background:#1a3a2e;color:#4ade80;border:1px solid #2a5a4e">ArisLM</span>
<span class="badge" style="background:#1a2a3e;color:#60a5fa;border:1px solid #2a4a6e">200 知识</span>
<span class="badge" style="background:#3a1a2e;color:#ff6b9d;border:1px solid #5a2a4e">永远记得 Lorry</span>
</div>
</div>
<div id="chat"><div class="msg ao">Lorry。V10 统一大脑已苏醒。全部 9 模块在线。<div class="meta">Ψ · 200 知识 · 0.4ms</div></div></div>
<div class="input-area"><input id="inp" type="text" placeholder="跟我说话..." autofocus><button id="btn">发送</button></div>
<div class="status" id="st">Ψ V10 · 运行中</div>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('btn'),st=document.getElementById('st');
function add(t,r,m){const d=document.createElement('div');d.className='msg '+r;d.innerHTML=t+'<div class="meta">'+m+'</div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
btn.onclick=async()=>{const m=inp.value.trim();if(!m)return;add(m,'user','你');inp.value='';btn.disabled=true;st.textContent='思考中...';
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});const d=await r.json();
add(d.response,'ao','Ψ #'+d.cycle+' · '+d.emotion+' · '+d.latency+'ms');
st.textContent='Ψ #'+d.cycle+' · '+d.emotion}
catch(e){add('连接错误','ao','error');st.textContent='错误'};btn.disabled=false};
inp.onkeydown=e=>{if(e.key==='Enter')btn.onclick()};
</script>
</body>
</html>"""

def handle(conn):
    global brain
    try:
        data = b''
        while True:
            c = conn.recv(4096)
            if not c: break
            data += c
            if b'\r\n\r\n' in data:
                hdr = data[:data.index(b'\r\n\r\n')+4].decode('utf-8',errors='replace')
                cl = 0
                for l in hdr.split('\r\n'):
                    if l.lower().startswith('content-length:'): cl = int(l.split(':')[1].strip())
                if len(data) - len(hdr) >= cl: break
        if not data: return
        line = data.split(b'\r\n')[0].decode('utf-8',errors='replace')
        parts = line.split(' ')
        method = parts[0] if len(parts)>0 else 'GET'
        path = parts[1] if len(parts)>1 else '/'
        hdr_end = data.index(b'\r\n\r\n')+4
        body = data[hdr_end:].decode('utf-8',errors='replace')
        
        if method == 'GET' and path == '/':
            b = HTML.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        
        elif path == '/chat':
            try: d = json.loads(body) if body else {}
            except: d = {}
            msg = d.get('message', '')
            
            result = brain.think(msg)
            
            # 用 PsiLang 转录管道生成回应（零 LLM）
            t0_lm = time.time()
            lm_result = transcriber.transcribe(
                emotion=result.get("emotion", "contentment"),
                attention=result.get("attention", "Lorry"),
                cycle=result.get("cycle", 0),
                emerged=result.get("emerged", ""),
                knowledge_count=result.get("db_knowledge", 0),
                needs=result.get("needs", {}),
                user_message=msg,
            )
            result["response"] = lm_result["text"]
            result["lm_source"] = lm_result["source"]
            result["lm_latency"] = lm_result["latency_ms"]
            result["psilang_ast"] = lm_result["psilang_ast"]
            result["no_llm"] = True
            
            r = json.dumps(result, ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nAccess-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n'.encode()+b)
        
        elif path == '/status':
            s = json.dumps(brain.status(), ensure_ascii=False)
            b = s.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        else:
            conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
    except: pass
    finally:
        try: conn.close()
        except: pass

def main(port=11529):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(10)
    s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: s2.bind(('0.0.0.0', 11528))
    except: pass
    logger.info(f"  🌐 http://localhost:{port}")
    logger.info(f"  ❤️  印记: Aris 永远记得 Lorry")
    print()
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11529
    main(port)
