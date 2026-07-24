"""Aris Copilot Bridge v8 — proper SSE implementation using OpenAI format"""

import logging
logger = logging.getLogger(__name__)

import subprocess, json, sys, re, socket, threading
import time

MODEL_NAME = "copilot"

def handle_client(conn, addr):
    try:
        f = conn.makefile('bw', buffering=0)
        rf = conn.makefile('br')
        
        request_line = rf.readline().decode().strip()
        if not request_line:
            conn.close()
            return
        
        method, path, _ = request_line.split(' ', 2)
        
        headers = {}
        content_length = 0
        while True:
            line = rf.readline().decode().strip()
            if not line:
                break
            if ':' in line:
                key, val = line.split(':', 1)
                headers[key.strip().lower()] = val.strip()
                if key.lower() == 'content-length':
                    content_length = int(val.strip())
        
        body = rf.read(content_length) if content_length > 0 else b'{}'
        
        if path == '/v1/models':
            resp = json.dumps({"object":"list","data":[{"id":MODEL_NAME,"object":"model"}]})
            f.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\nConnection: close\r\n\r\n{resp}".encode())
            f.flush()
            
        elif path == '/v1/chat/completions' and method == 'POST':
            data = json.loads(body) if body else {}
            prompt = data.get("messages", [{}])[-1].get("content", "")
            stream = data.get("stream", False)
            
            r = subprocess.run(
                ["copilot", "-p", prompt],
                capture_output=True, text=True, timeout=120,
                cwd=r"C:\Users\user\Desktop\Windows-Copilot-API-master"
            )
            output = r.stdout.strip()
            output = re.sub(r'\n\nTotal usage.*', '', output, flags=re.DOTALL).strip()
            if not output:
                output = "No response"
            
            if stream:
                # SSE streaming format for Hermes/OpenAI client
                resp = f"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\nAccess-Control-Allow-Origin: *\r\n\r\n"
                f.write(resp.encode())
                f.flush()
                
                # Content chunk
                chunk = {
                    "id": "chatcmpl-copilot",
                    "object": "chat.completion.chunk",
                    "model": MODEL_NAME,
                    "choices": [{
                        "index": 0,
                        "delta": {"role": "assistant", "content": output},
                        "finish_reason": None
                    }]
                }
                f.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                f.flush()
                
                # Stop chunk
                stop = {
                    "id": "chatcmpl-copilot",
                    "object": "chat.completion.chunk",
                    "model": MODEL_NAME,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]
                }
                f.write(f"data: {json.dumps(stop, ensure_ascii=False)}\n\n".encode())
                f.flush()
                
                # Done signal
                f.write(b"data: [DONE]\n\n")
                f.flush()
            else:
                # Standard JSON
                resp_data = {
                    "id": "chatcmpl-copilot",
                    "object": "chat.completion",
                    "model": MODEL_NAME,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": output},
                        "finish_reason": "stop"
                    }],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                }
                resp = json.dumps(resp_data, ensure_ascii=False)
                f.write(f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(resp.encode())}\r\nConnection: close\r\n\r\n{resp}".encode())
                f.flush()
        else:
            f.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
            f.flush()
        
        conn.close()
    except:
        try:
            conn.close()
        except Exception as e:
            logger.debug(f"操作失败: {e}")
def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(10)
    logger.info(f"Copilot Bridge v8 on http://127.0.0.1:{port}/v1")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
