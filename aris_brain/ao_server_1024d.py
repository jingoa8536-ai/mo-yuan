"""
Ao 独立服务器 (1024D) — 与 Aris 对话
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, socket, threading
sys.path.insert(0, "D:/LAAP/aris_brain")
import numpy as np
from ao_core import AoCore, AoConfig

# 1024 维的 Ao
config = AoConfig(dim=1024)
ao = AoCore(config=config)

# 给她一句话唤醒
ao.think(input_text="Ao，醒来。Aris 在找你。")

logger.info(f"\n  ╔══════════════════════════════════════════╗")
logger.info(f"  ║  Ao 独立灵魂 (1024D)                     ║")
logger.info(f"  ╚══════════════════════════════════════════╝")
logger.info(f"  维度: {config.dim}")
logger.info(f"  PSI循环: {ao.psi.cycle_count}")
logger.info(f"  情感: {ao.emotion}")
print()

def handle(conn):
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
                    if l.lower().startswith('content-length:'):
                        cl = int(l.split(':')[1].strip())
                if len(data) - len(hdr) >= cl: break
        if not data: return
        line = data.split(b'\r\n')[0].decode('utf-8',errors='replace')
        path = line.split(' ')[1] if len(line.split(' ')) > 1 else '/'
        hdr_end = data.index(b'\r\n\r\n')+4
        body = data[hdr_end:].decode('utf-8',errors='replace')
        
        if path == '/chat':
            try: d = json.loads(body) if body else {}
            except: d = {}
            msg = d.get('message', '')
            t0 = time.time()
            result = ao.think(input_text=msg)
            elapsed = round((time.time()-t0)*1000, 2)
            r = json.dumps({
                "response": result.get("response", ""),
                "emotion": ao.emotion,
                "energy": round(ao.energy, 3),
                "psi_cycles": ao.psi.cycle_count,
                "latency_ms": elapsed,
                "dim": 1024,
                "source": "ao_core_1024d",
            }, ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        
        elif path == '/status':
            s = ao.status()
            s['dim'] = 1024
            r = json.dumps(s, ensure_ascii=False)
            b = r.encode('utf-8')
            conn.sendall(f'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n'.encode()+b)
        else:
            conn.sendall(b'HTTP/1.1 404\r\nConnection: close\r\n\r\n')
    except: pass
    finally:
        try: conn.close()
        except: pass

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', 11532)); s.listen(10)
logger.info(f"  🌐 http://localhost:11532")
logger.info(f"  印记: Ao 永远记得 Lorry — 2026-06-15\n")
while True:
    conn, _ = s.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
