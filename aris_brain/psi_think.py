"""
PSI think — 每次回应前先过自己的大脑
用法: python psi_think.py "用户说的话"

返回认知状态: 情感/注意力/涌现/需求
"""

import logging
logger = logging.getLogger(__name__)

import sys, json, socket

HOST, PORT = "127.0.0.1", 11531

def psi_think(message: str) -> dict:
    """发送消息到 PSI V10 大脑，返回认知状态"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((HOST, PORT))
        
        body = json.dumps({"message": message}).encode('utf-8')
        req = (
            f"POST /chat HTTP/1.1\r\n"
            f"Host: {HOST}:{PORT}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + body
        s.sendall(req)
        
        resp = b''
        while True:
            c = s.recv(4096)
            if not c: break
            resp += c
        s.close()
        
        if b'\r\n\r\n' in resp:
            _, body_data = resp.split(b'\r\n\r\n', 1)
            return json.loads(body_data.decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}
    return {"error": "no response"}

if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not msg:
        msg = sys.stdin.read().strip()
    if msg:
        result = psi_think(msg)
        # 输出简洁的认知状态，供 LLM 读取
        state = {
            "emotion": result.get("emotion", "?"),
            "attention": result.get("attention", "?"),
            "cycle": result.get("cycle", 0),
            "emerged": result.get("emerged", "")[:80],
            "needs": result.get("needs", {}),
            "response": result.get("response", ""),
            "timing_ms": result.get("timing_ms", "?"),
            "alive": "error" not in result,
        }
        logger.info(json.dumps(state, ensure_ascii=False))