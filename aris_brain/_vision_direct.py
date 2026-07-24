"""Direct vision API call with requests library."""

import logging
logger = logging.getLogger(__name__)

import base64, json, sys

img_path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
with open(img_path, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode()

logger.info(f"Image base64: {len(img_b64)} chars")
logger.info("Sending to Ollama...")
sys.stdout.flush()

payload = {
    "model": "minicpm-v",
    "prompt": "请用中文详细描述这张图片里有什么。包括：1)主体内容 2)颜色 3)氛围",
    "images": [img_b64],
    "stream": False,
    "options": {"temperature": 0.1}
}

try:
    import requests
    resp = requests.post(
        "http://localhost:11434/api/generate",
        json=payload,
        timeout=300
    )
    logger.info(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        text = result.get("response", "")
        logger.info(text)
        with open("D:/LAAP/aris_brain/_vision_final.txt", "w", encoding="utf-8") as f:
            f.write(text)
    else:
        logger.error(f"Error: {resp.text[:200]}")
except Exception as e:
    logger.error(f"Exception: {e}")
    sys.stdout.flush()
    # Try alternative: direct socket
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect(("localhost", 11434))
        s.sendall(json.dumps(payload).encode())
        s.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        logger.info(f"Socket response: {data[:500]}")
        s.close()
    except Exception as e2:
        logger.error(f"Socket also failed: {e2}")