"""Try Ollama API with socket (not urllib)."""

import logging
logger = logging.getLogger(__name__)

import json, socket, base64, time

img_path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
with open(img_path, 'rb') as f:
    img_b64 = base64.b64encode(f.read()).decode()

# First test: text-only
logger.info("Test 1: Text-only generation...")
payload = json.dumps({
    "model": "minicpm-v",
    "prompt": "Say hello in 3 words",
    "stream": False,
    "options": {"num_ctx": 512}
})

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(600)
sock.connect(("127.0.0.1", 11434))
request = f"POST /api/generate HTTP/1.1\r\nHost: localhost:11434\r\nContent-Type: application/json\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n{payload}"
sock.sendall(request.encode())

response = b""
while True:
    try:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    except socket.timeout:
        break

sock.close()

# Parse HTTP response
parts = response.split(b"\r\n\r\n")
if len(parts) >= 2:
    body = parts[1]
    logger.error(f"Response ({len(body)} bytes): {body[:500].decode('utf-8', errors='replace')}")
else:
    logger.error(f"Raw response: {response[:500].decode('utf-8', errors='replace')}")