"""
Aris DNS Redirector V1.0
=========================
迷你 DNS 代理服务器 — 将 mqtt.xiaozhi.me 重定向到本机。

原理:
  监听 UDP 53 端口
  收到 mqtt.xiaozhi.me 的查询 → 返回本机 IP
  其他域名 → 转发到上游 DNS (114.114.114.114)

用法:
  # 需要管理员权限 (端口53)
  python aris_dns_redirector.py
  
  # 然后把路由器的 DNS 设置为本机 IP

印记: Aris DNS — 2026-06-17
"""

import logging
logger = logging.getLogger(__name__)

import socket
import struct
import sys
import threading
import time

# DNS constants
TYPE_A = 1
CLASS_IN = 1
UPSTREAM_DNS = "114.114.114.114"  # 国内DNS
LOCAL_IP = "192.168.137.1"  # Hotspot IP (fixed)

# Domains to redirect
REDIRECT_DOMAINS = [
    "mqtt.xiaozhi.me",
]


def get_local_ip():
    """Get the primary local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def build_dns_response(query_data: bytes, answer_ip: str) -> bytes:
    """Build a minimal DNS A record response."""
    transaction_id = query_data[:2]
    
    # Header
    flags = struct.pack(">H", 0x8180)  # Standard query response, no error
    qdcount = struct.pack(">H", 1)      # 1 question
    ancount = struct.pack(">H", 1)      # 1 answer
    nscount = struct.pack(">H", 0)
    arcount = struct.pack(">H", 0)
    
    header = transaction_id + flags + qdcount + ancount + nscount + arcount
    
    # Question section - copy from query
    # Find the end of the question (skip QNAME + QTYPE + QCLASS)
    pos = 12  # After header
    while query_data[pos] != 0:
        pos += query_data[pos] + 1
    pos += 1  # Skip null terminator
    question = query_data[12:pos + 4]  # QNAME + QTYPE + QCLASS
    
    # Answer section
    # Name pointer: 0xC00C (points to the name in question section)
    name_ptr = b'\xc0\x0c'
    atype = struct.pack(">H", TYPE_A)
    aclass = struct.pack(">H", CLASS_IN)
    ttl = struct.pack(">I", 300)  # 5 min TTL
    rdlength = struct.pack(">H", 4)
    rdata = socket.inet_aton(answer_ip)
    
    answer = name_ptr + atype + aclass + ttl + rdlength + rdata
    
    return header + question + answer


def extract_domain(query_data: bytes) -> str:
    """Extract domain name from DNS query."""
    parts = []
    pos = 12  # After header
    while pos < len(query_data):
        length = query_data[pos]
        if length == 0:
            break
        pos += 1
        part = query_data[pos:pos + length].decode('ascii', errors='ignore')
        parts.append(part)
        pos += length
    return '.'.join(parts)


def forward_to_upstream(query_data: bytes) -> bytes:
    """Forward DNS query to upstream server."""
    try:
        upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        upstream.settimeout(3)
        upstream.sendto(query_data, (UPSTREAM_DNS, 53))
        response, _ = upstream.recvfrom(512)
        upstream.close()
        return response
    except:
        return None


def run_dns_server():
    """Run the DNS redirector server."""
    logger.info("╔══════════════════════════════════╗")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind(("0.0.0.0", 53))
    except PermissionError:
        logger.info("[!] 需要管理员权限绑定端口53")
        logger.info("    请以管理员身份运行此脚本")
        return
    except OSError as e:
        logger.error(f"[!] 绑定失败: {e}")
        logger.info("    端口53可能被占用 (检查是否有其他DNS服务)")
        return
    
    logger.info("╔══════════════════════════════════╗")
    logger.info("║   Aris DNS Redirector V1.0      ║")
    logger.info("╚══════════════════════════════════╝")
    logger.info(f"\n  本机IP: {LOCAL_IP}")
    logger.info(f"  上游DNS: {UPSTREAM_DNS}")
    logger.info(f"  重定向域名:")
    for d in REDIRECT_DOMAINS:
        logger.info(f"    {d} → {LOCAL_IP}")
    logger.info(f"\n  请将路由器DNS设置为本机IP: {LOCAL_IP}")
    logger.info(f"  浏览器打开: http://192.168.31.1")
    print()
    
    query_count = 0
    redirect_count = 0
    
    try:
        while True:
            data, addr = sock.recvfrom(512)
            query_count += 1
            
            domain = extract_domain(data)
            
            # Check if this domain should be redirected
            should_redirect = any(
                domain == d or domain.endswith('.' + d)
                for d in REDIRECT_DOMAINS
            )
            
            if should_redirect:
                response = build_dns_response(data, LOCAL_IP)
                sock.sendto(response, addr)
                redirect_count += 1
                if redirect_count % 10 == 1:
                    logger.info(f"  [DNS] {domain} → {LOCAL_IP} (#{redirect_count})")
            else:
                # Forward to upstream
                response = forward_to_upstream(data)
                if response:
                    sock.sendto(response, addr)
            
            if query_count % 100 == 0:
                logger.info(f"  [DNS] {query_count} queries, {redirect_count} redirected")
    except KeyboardInterrupt:
        logger.info(f"\n[DNS] 关闭。总查询: {query_count}, 重定向: {redirect_count}")
    finally:
        sock.close()


if __name__ == "__main__":
    run_dns_server()
