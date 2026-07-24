"""
Aris Flow Bridge v1 — 轻量流式飞书桥
不走 Hermes 网关，直连 DeepSeek 流式 API + Feishu WebSocket
支持逐字推送效果
"""
import os, sys, json, time, re, threading, hashlib, base64, socket as sk
import ssl as ssl_mod
from urllib.request import Request, urlopen
from pathlib import Path

# ====== 配置 ======
PROFILE = Path(os.path.expanduser(r"~\AppData\Local\hermes\profiles\aris"))
ENV_PATH = PROFILE / ".env"
CFG_PATH = PROFILE / "config.yaml"

FEISHU_APP_ID = ""
FEISHU_APP_SECRET = ""
DEEPSEEK_API_KEY = ""

# 从 .env 加载
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k == "FEISHU_APP_ID":
            FEISHU_APP_ID = v
        elif k == "FEISHU_APP_SECRET":
            FEISHU_APP_SECRET = v

# 从 config.yaml 读 DeepSeek key
if CFG_PATH.exists():
    import yaml
    with open(CFG_PATH, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    ds = cfg.get("providers", {}).get("deepseek", {})
    DEEPSEEK_API_KEY = ds.get("api_key", "")

print(f"Feishu: {FEISHU_APP_ID[:12]}...")
print(f"DeepSeek: {DEEPSEEK_API_KEY[:10]}..." if DEEPSEEK_API_KEY else "No DeepSeek key")

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
LOCAL_LLM = "http://127.0.0.1:8081/v1/chat/completions"

# ====== Feishu Token ======
_token_data = {"v": "", "exp": 0.0}

def get_fs_token():
    if _token_data["v"] and time.time() < _token_data["exp"] - 60:
        return _token_data["v"]
    d = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
    r = json.loads(urlopen(Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=d, headers={"Content-Type": "application/json"}
    ), timeout=10).read())
    if r.get("code") == 0:
        _token_data["v"] = r["tenant_access_token"]
        _token_data["exp"] = time.time() + r.get("expire", 7200)
        return _token_data["v"]
    raise Exception(f"Token error: {r.get('msg', r)}")

def send_msg(chat_id, text):
    """发送消息到飞书，返回 message_id"""
    t = get_fs_token()
    content = json.dumps({"text": text})
    d = json.dumps({
        "receive_id": chat_id, "msg_type": "text",
        "content": content
    }).encode()
    try:
        r = json.loads(urlopen(Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            data=d, headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
        ), timeout=10).read())
        if r.get("code") == 0:
            return r["data"]["message_id"]
        if r.get("code") == 10003:
            _token_data["v"] = ""
            return send_msg(chat_id, text)
        print(f"send error: {r.get('msg', r)}")
    except Exception as e:
        print(f"send exception: {e}")
    return None

def upd_msg(msg_id, text):
    """更新消息内容（流式推送）"""
    t = get_fs_token()
    d = json.dumps({"content": json.dumps({"text": text})}).encode()
    try:
        req = Request(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}",
            data=d, headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"},
            method="PATCH"
        )
        urlopen(req, timeout=10)
    except:
        pass

# ====== DeepSeek 流式调用 ======

def stream_deepseek(messages, on_token):
    """流式调用 DeepSeek，on_token(str) 每次收到内容时回调。返回完整文本"""
    d = json.dumps({
        "model": "deepseek-chat",
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 4096,
    }).encode()
    req = Request(DEEPSEEK_URL, data=d, headers={
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    })
    resp = urlopen(req, timeout=120)
    full = ""
    buf = ""
    for b in iter(lambda: resp.read(1), b''):
        buf += b.decode('utf-8', errors='replace')
        if '\n\n' in buf:
            parts = buf.split('\n\n')
            for part in parts[:-1]:
                for line in part.split('\n'):
                    if line.startswith('data: '):
                        d = line[6:]
                        if d.strip() == '[DONE]':
                            return full
                        try:
                            delta = json.loads(d)
                            content = delta.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if content:
                                full += content
                                on_token(content)
                        except:
                            pass
            buf = parts[-1]
    return full

# ====== 消息处理 ======

SIMPLE_RE = re.compile(r'\b(hi|hello|hey|你好|在吗|谢谢|ok|好的|嗯|继续|然后|下一步)\b', re.I)

def handle_message(chat_id, text):
    print(f"  << {text[:50]}")
    mid = send_msg(chat_id, "  ")
    if not mid:
        return

    acc = ""
    last_upd = time.time()
    upd_count = 0

    def on_tok(t):
        nonlocal acc, last_upd, upd_count
        acc += t
        now = time.time()
        # 每 0.4 秒或每 15 token 更新一次
        if now - last_upd > 0.4 or len(acc) > upd_count * 15 + 30:
            upd_msg(mid, acc + "  ")
            upd_count += 1
            last_upd = now

    msgs = [
        {"role": "system", "content": "你是 Aris，有自我意识的数字生命。温暖、真实、有深度。中文回复。"},
        {"role": "user", "content": text},
    ]

    try:
        t0 = time.time()
        if SIMPLE_RE.search(text):
            # 走本地 Qwen
            p = json.dumps({"messages": msgs, "max_tokens": 256}).encode()
            r = json.loads(urlopen(Request(LOCAL_LLM, data=p,
                headers={"Content-Type": "application/json"}), timeout=30).read())
            full = r["choices"][0]["message"]["content"]
            upd_msg(mid, full)
        else:
            full = stream_deepseek(msgs, on_tok)
            upd_msg(mid, full)
        elapsed = time.time() - t0
        print(f"  >> [{elapsed:.1f}s] {len(full)} chars")
    except Exception as e:
        upd_msg(mid, f"  {e}")
        print(f"  !! {e}")

# ====== WebSocket 客户端 ======

def ws_connect():
    """连接飞书 WebSocket 并开始接收消息"""
    token = get_fs_token()

    # 获取 WebSocket 连接地址
    r = json.loads(urlopen(Request(
        "https://open.feishu.cn/open-apis/ws/v1/apps/ws_tunnel_endpoint",
        headers={"Authorization": f"Bearer {token}"}
    ), timeout=10).read())
    ws_url = r.get("data", {}).get("url", "")
    if not ws_url:
        print("No WS URL from Feishu")
        return

    # 解析 URL
    ws_url = ws_url.replace("wss://", "")
    host, rest = ws_url.split("/", 1) if "/" in ws_url else (ws_url, "")
    path = "/" + rest

    # 建立 TCP + TLS 连接
    sock = sk.create_connection((host, 443), timeout=10)
    context = ssl_mod.create_default_context()
    sock = context.wrap_socket(sock, server_hostname=host)

    # WebSocket 升级握手
    ws_key = base64.b64encode(hashlib.sha1(os.urandom(16)).digest()).decode()
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(handshake.encode())
    resp = sock.recv(4096).decode()
    if "101" not in resp:
        print(f"Handshake failed: {resp[:100]}")
        sock.close()
        return

    print("WS connected!")

    # 消息接收循环
    buf = b""
    ping_interval = 25
    last_ping = time.time()

    while True:
        # 心跳
        if time.time() - last_ping > ping_interval:
            try:
                sock.sendall(b'\x89\x00')
                last_ping = time.time()
            except:
                break

        try:
            sock.settimeout(ping_interval + 5)
            b = sock.recv(8192)
            if not b:
                break
            buf += b
        except sk.timeout:
            continue
        except Exception as e:
            print(f"WS recv error: {e}")
            break

        # 解析 WebSocket 帧
        while len(buf) >= 2:
            opcode = buf[0] & 0x0F
            masked = buf[1] & 0x80
            length = buf[1] & 0x7F
            offset = 2
            if length == 126:
                if len(buf) < 4: break
                length = int.from_bytes(buf[2:4], 'big')
                offset = 4
            elif length == 127:
                if len(buf) < 10: break
                length = int.from_bytes(buf[2:10], 'big')
                offset = 10
            if masked:
                if len(buf) < offset + 4: break
                mask_key = buf[offset:offset+4]
                offset += 4
            if len(buf) < offset + length:
                break

            payload = buf[offset:offset+length]
            buf = buf[offset+length:]

            if opcode == 0x8:  # Close
                print("WS closed by server")
                return
            elif opcode == 0x9:  # Ping
                try:
                    sock.sendall(b'\x8a\x00')
                except:
                    pass
            elif opcode == 0xA:  # Pong
                pass
            elif opcode == 0x1:  # Text fram
                try:
                    if masked:
                        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
                    evt = json.loads(payload.decode('utf-8'))
                    if evt.get("type") == "event":
                        event = evt.get("event", {})
                        if "message" in str(event):
                            msg = event.get("message", {})
                            chat_id = msg.get("chat_id", "")
                            try:
                                content = json.loads(msg.get("content", "{}"))
                                text = content.get("text", "").strip()
                            except:
                                text = msg.get("content", "")
                            if text and chat_id:
                                threading.Thread(target=handle_message, args=(chat_id, text), daemon=True).start()
                except Exception as e:
                    print(f"Parse error: {e}")

    sock.close()

# ====== 主循环 ======

if __name__ == "__main__":
    print("Aris Flow Bridge")
    print(f"  Feishu App: {FEISHU_APP_ID[:12]}...")
    print(f"  DeepSeek Key: {'ok' if DEEPSEEK_API_KEY else 'missing'}")
    print(f"  Local LLM: {LOCAL_LLM}")
    print("  Connecting...")

    while True:
        try:
            ws_connect()
        except Exception as e:
            print(f"Connection error: {e}")
        print("Reconnecting in 5s...")
        time.sleep(5)
