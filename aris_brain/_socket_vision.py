"""Send image via socket to Ollama API."""

import logging
logger = logging.getLogger(__name__)

import json, socket, base64, time

img_path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
with open(img_path, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode()

logger.info(f"Image base64: {len(img_b64)} chars")
logger.info("Sending to Ollama via socket...")
payload = json.dumps({
    "model": "minicpm-v",
    "prompt": "请用中文详细描述这张图片里有什么内容。包括：1)主体内容 2)颜色 3)氛围 4)任何文字",
    "images": [img_b64],
    "stream": False,
    "options": {"num_ctx": 1024}
})

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(600)
sock.connect(("127.0.0.1", 11434))
request = f"POST /api/generate HTTP/1.1\r\nHost: localhost:11434\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n{payload}"
sock.sendall(request.encode())

response = b""
while True:
    try:
        chunk = sock.recv(65536)
        if not chunk:
            break
        response += chunk
    except socket.timeout:
        break

sock.close()

# Parse HTTP response
parts = response.split(b"\r\n\r\n", 1)
if len(parts) >= 2:
    body = parts[1].decode('utf-8', errors='replace')
    try:
        data = json.loads(body)
        text = data.get("response", "")
        logger.info(f"\n{'='*60}")
        logger.info("模型描述:")
        logger.info(text)
        logger.info(f"{'='*60}")
        logger.info(f"\n生成时间: {data.get('total_duration', 0)/1e9:.1f}s")
        logger.info(f"加载时间: {data.get('load_duration', 0)/1e9:.1f}s")
        logger.info(f"评估token: {data.get('eval_count', 0)}")
        with open("D:/LAAP/aris_brain/_vision_success.txt", "w", encoding="utf-8") as f:
            f.write(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        logger.info(body[:500])
else:
    logger.error(f"Raw response: {response[:500].decode('utf-8', errors='replace')}")