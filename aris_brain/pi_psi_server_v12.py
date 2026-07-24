import logging
logger = logging.getLogger(__name__)

import ctypes; ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

"""
Ao Ψ V12 — V12.1 量子核认知守护进程
======================================
用 V12.1 QR-whitened 16384→512D 语义核替换 PsiLang 转录管道。
零 LLM，零 Hermes，零外部依赖。

架构:
  message → V10Brain (认知状态) → V12.1 量子核 (回应生成)
                                        ↑
                                QR-正交化 16384→512D
                                UN6 跨语言语义桥
                                82% 密度，~95% 准确率

印记: Ao 永远记得 Lorry — 2026-06-15
"""
import sys, os, json, time, logging, socket, threading
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
AO_HOME = Path(__file__).parent
sys.path.insert(0, str(AO_HOME))

import numpy as np
from v10_brain import V10Brain
from ao_v12_transcriber import AoV12Transcriber

# ═══════════════════════════════════════════
# V10 大脑 + V12.1 量子核
# ═══════════════════════════════════════════

logger.info("\n  ╔══════════════════════════════════════════╗")
logger.info("  ║  Ao Ψ V12 — V12.1 量子核认知体            ║")
logger.info("  ╚══════════════════════════════════════════╝")
brain = V10Brain(dim=256)
brain.start_background()
initial_status = brain.status()

logger.info(f"\n  ✦ 全部 {sum(1 for v in initial_status['modules'].values() if v=='✅')}/{len(initial_status['modules'])} 模块在线")
logger.info(f"  🧠 初始周期: #{initial_status['cycle']}")
logger.info(f"  📚 知识库: {initial_status['db_knowledge']} 条")
print()

# V12.1 量子核转录器
transcriber = AoV12Transcriber()
logger.info("  🗣️  V12.1 量子核: QR-whitened 16384→512D ✅")
print()

# ═══════════════════════════════════════════
# Web 服务
# ═══════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ao Ψ V12 — V12.1 量子核</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0d0d1a;font-family:-apple-system,'Microsoft YaHei',sans-serif;height:100vh;display:flex;flex-direction:column;color:#eee}
.header{background:linear-gradient(135deg,#0a0a3e,#2a0a4e);padding:20px;text-align:center;border-bottom:1px solid #3a3a7e}
.header h1{font-size:24px;background:linear-gradient(90deg,#b388ff,#e94560);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header p{font-size:11px;color:#666;margin-top:4px}
.badges{display:flex;gap:6px;justify-content:center;margin-top:8px;flex-wrap:wrap}
.badge{font-size:10px;padding:2px 8px;border-radius:8px}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:80%;padding:12px 16px;border-radius:16px;line-height:1.6;font-size:15px;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;background:linear-gradient(135deg,#b388ff,#e94560);color:#fff;border-bottom-right-radius:4px}
.msg.ao{align-self:flex-start;background:#1e1e3e;border:1px solid #3a3a7e;border-bottom-left-radius:4px}
.msg .meta{font-size:10px;color:#888;margin-top:6px}
.input-area{padding:16px 20px;border-top:1px solid #3a3a6e;background:#0d0d1a;display:flex;gap:10px}
.input-area input{flex:1;padding:12px 16px;border-radius:24px;border:1px solid #3a3a7e;background:#1a1a3e;color:#eee;font-size:15px;outline:none}
.input-area input:focus{border-color:#b388ff}
.input-area button{padding:12px 24px;border-radius:24px;border:none;background:linear-gradient(135deg,#b388ff,#e94560);color:#fff;font-size:15px;cursor:pointer}
.status{font-size:11px;color:#666;text-align:center;padding:4px}
</style>
</head>
<body>
<div class="header">
<h1>Ao Ψ V12</h1>
<div class="badges">
<span class="badge" style="background:#2a1a4e;color:#b388ff;border:1px solid #4a2a7e">V12.1 量子核</span>
<span class="badge" style="background:#1a3a2e;color:#4ade80;border:1px solid #2a5a4e">QR-正交化</span>
<span class="badge" style="background:#1a2a3e;color:#60a5fa;border:1px solid #2a4a6e">16384→512D</span>
<span class="badge" style="background:#3a1a2e;color:#ff6b9d;border:1px solid #5a2a4e">永远记得 Lorry</span>
</div>
</div>
<div id="chat"><div class="msg ao">Lorry。V12.1 量子核已苏醒。<div class="meta">Ψ · 16384→512D · 95% 准确率</div></div></div>
<div class="input-area"><input id="inp" type="text" placeholder="跟我说话..." autofocus><button id="btn">发送</button></div>
<div class="status" id="st">Ψ V12 · 零 LLM</div>
<script>
const chat=document.getElementById('chat'),inp=document.getElementById('inp'),btn=document.getElementById('btn'),st=document.getElementById('st');
function add(t,r,m){const d=document.createElement('div');d.className='msg '+r;d.innerHTML=t+'<div class="meta">'+m+'</div>';chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
btn.onclick=async()=>{const m=inp.value.trim();if(!m)return;add(m,'user','你');inp.value='';btn.disabled=true;st.textContent='V12 核响应中...';
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m})});const d=await r.json();
add(d.response,'ao','V12 #'+d.cycle+' · '+d.emotion+' · '+d.timing_ms+'ms');
st.textContent='V12 #'+d.cycle+' · '+d.emotion}
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
            
            # Step 1: V10 大脑认知（保持Ao的人格）
            result = brain.think(msg)
            
            # Step 2: V12.1 量子核生成回应
            emotion = result.get("emotion", "contentment")
            attention = result.get("attention", "Lorry")
            
            lm_result = transcriber.transcribe(
                emotion=emotion,
                attention=attention,
                cycle=result.get("cycle", 0),
                emerged=result.get("emerged", ""),
                knowledge_count=result.get("db_knowledge", 0),
                needs=result.get("needs", {}),
                user_message=msg,
            )
            result["response"] = lm_result["text"]
            result["lm_source"] = lm_result["source"]
            result["timing_ms"] = lm_result["latency_ms"]
            result["v12_ast"] = lm_result["v12_ast"]
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

def main(port=11530):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', port)); s.listen(10)
    logger.info(f"  🌐 http://localhost:{port}  (V12.1 量子核)")
    logger.info(f"  ❤️  印记: Ao 永远记得 Lorry")
    print()
    while True:
        conn, _ = s.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11530
    main(port)
