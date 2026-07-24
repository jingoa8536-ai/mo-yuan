"""Debug script for the JSONRPC client."""
import sys
import socket
import threading
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(r"D:\LAAP\harness\godot_bridge\python")))
from godot_jsonrpc_client import GodotJSONRPCClient, JSONRPCError


def make_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(8)
    port = server_socket.getsockname()[1]
    print(f"[server] listening on 127.0.0.1:{port}")

    def handler(req):
        print(f"[server] got request: {req}")
        return {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": req["id"]}

    def handle(conn):
        try:
            print("[server-conn] handling")
            decoder = json.JSONDecoder()
            buffer = ""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    print("[server-conn] connection closed")
                    break
                print(f"[server-conn] received {len(chunk)} bytes: {chunk!r}")
                buffer += chunk.decode("utf-8")
                while buffer:
                    try:
                        obj, end = decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        print("[server-conn] incomplete json, waiting for more")
                        break
                    resp = handler(obj)
                    payload = (json.dumps(resp) + "\n").encode("utf-8")
                    print(f"[server-conn] sending {len(payload)} bytes: {payload!r}")
                    conn.sendall(payload)
                    buffer = buffer[end:].lstrip()
        except Exception as e:
            print(f"[server-conn] error: {e}")
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def accept_loop():
        while True:
            try:
                conn, _ = server_socket.accept()
            except OSError:
                break
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    t = threading.Thread(target=accept_loop, daemon=True)
    t.start()
    return server_socket, port


def main():
    server_socket, port = make_server()
    print(f"[client] connecting to 127.0.0.1:{port}")
    client = GodotJSONRPCClient("127.0.0.1", port, backoff=0.05, timeout=5.0)
    try:
        print("[client] calling ping")
        result = client.call_method("ping", {"hello": "world"})
        print(f"[client] result: {result}")
    except Exception as e:
        print(f"[client] error: {e}")
    finally:
        client.close()
        server_socket.close()
    print("[main] done")


if __name__ == "__main__":
    main()
