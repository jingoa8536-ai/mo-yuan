"""
Aether Monitor — 监控仪表盘 v1
================================
实时显示 Token 消耗、延迟、成本、系统状态。

用法:
    python -m aether.monitor          # 启动 Web 仪表盘
    打开 http://localhost:11529

    或集成到现有 Web 网关：
    from aether.monitor import Monitor
    monitor = Monitor()
"""
import json, os, sys, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path = [p for p in sys.path if p is not None]
for p in ["D:/LAAP/aris_brain", "D:/LAAP"]:
    if p not in sys.path: sys.path.insert(0, p)

HOST, PORT = "127.0.0.1", 11529


class Monitor:
    """系统监控 — 追踪 Token、延迟、调用统计。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[dict] = []
        self._max_records = 1000
        self._start_time = time.time()

    def record(self, turn_type: str, latency_ms: float, tokens: int = 0,
               cost: float = 0.0, rule: str = "", detail: str = ""):
        """记录一次调用。"""
        with self._lock:
            self._records.append({
                "time": time.time(),
                "type": turn_type,        # "zero_llm" | "llm" | "tool"
                "latency_ms": latency_ms,
                "tokens": tokens,
                "cost": cost,
                "rule": rule,
                "detail": detail[:100],
            })
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]

    def get_stats(self) -> dict:
        """获取汇总统计。"""
        with self._lock:
            total = len(self._records)
            if total == 0:
                return {"uptime_seconds": time.time() - self._start_time,
                        "total_calls": 0, "zero_llm": 0, "llm": 0,
                        "avg_latency_ms": 0, "total_tokens": 0, "total_cost": 0}

            zero_llm = sum(1 for r in self._records if r["type"] == "zero_llm")
            llm = sum(1 for r in self._records if r["type"] == "llm")
            total_tokens = sum(r["tokens"] for r in self._records)
            total_cost = sum(r["cost"] for r in self._records)
            avg_latency = sum(r["latency_ms"] for r in self._records) / total

            # 每小时趋势
            now = time.time()
            hour_ago = now - 3600
            recent = [r for r in self._records if r["time"] > hour_ago]

            return {
                "uptime_seconds": round(time.time() - self._start_time),
                "total_calls": total,
                "zero_llm": zero_llm,
                "llm": llm,
                "zero_llm_pct": f"{zero_llm / total * 100:.0f}%",
                "avg_latency_ms": round(avg_latency, 1),
                "total_tokens": total_tokens,
                "total_cost": round(total_cost, 6),
                "calls_last_hour": len(recent),
                "tokens_last_hour": sum(r["tokens"] for r in recent),
            }

    def get_recent(self, n: int = 20) -> List[dict]:
        with self._lock:
            return list(self._records[-n:])


# ─── 全局单例 ──────────────────────────────────────

_monitor: Optional[Monitor] = None


def get_monitor() -> Monitor:
    global _monitor
    if _monitor is None:
        _monitor = Monitor()
    return _monitor


# ─── Web 仪表盘 ────────────────────────────────────

class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        mon = get_monitor()
        if self.path == "/api/stats":
            self._json(mon.get_stats())
        elif self.path == "/api/recent":
            self._json(mon.get_recent(50))
        else:
            self._html()

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def log_message(self, *a): pass


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Aether Monitor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{background:#0d0d1a;color:#e0e0e0;font-family:'Inter',system-ui,sans-serif;padding:24px;max-width:900px;margin:0 auto;}
h1{font-size:20px;font-weight:600;background:linear-gradient(135deg,#4ECDC4,#DDA0DD);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:20px;}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px;}
.card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:16px;}
.card .label{font-size:11px;color:rgba(255,255,255,0.4);margin-bottom:4px;}
.card .value{font-size:22px;font-weight:600;}
.card .value.green{color:#4ECDC4;}
.card .value.purple{color:#DDA0DD;}
.card .value.orange{color:#FFB347;}
.card .value.red{color:#FF6B6B;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{text-align:left;color:rgba(255,255,255,0.4);padding:8px;border-bottom:1px solid rgba(255,255,255,0.06);}
td{padding:8px;border-bottom:1px solid rgba(255,255,255,0.03);}
.tag{padding:2px 6px;border-radius:3px;font-size:10px;}
.tag.zero{background:rgba(78,205,196,0.2);color:#4ECDC4;}
.tag.llm{background:rgba(255,107,107,0.2);color:#FF6B6B;}
</style></head>
<body>
<h1>Aether Monitor</h1>
<div class="grid" id="cards"></div>
<h2 style="font-size:14px;margin-bottom:12px;color:rgba(255,255,255,0.5);">Recent Calls</h2>
<table><thead><tr><th>Time</th><th>Type</th><th>Latency</th><th>Tokens</th><th>Cost</th><th>Detail</th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
function fmt(t){return new Date(t*1000).toLocaleTimeString();}
function load(){
fetch('/api/stats').then(r=>r.json()).then(d=>{
document.getElementById('cards').innerHTML=
  '<div class="card"><div class="label">Total Calls</div><div class="value green">'+d.total_calls+'</div></div>'+
  '<div class="card"><div class="label">Zero-LLM Rate</div><div class="value purple">'+d.zero_llm_pct+'</div></div>'+
  '<div class="card"><div class="label">Avg Latency</div><div class="value orange">'+d.avg_latency_ms+'ms</div></div>'+
  '<div class="card"><div class="label">Total Tokens</div><div class="value red">'+d.total_tokens+'</div></div>'+
  '<div class="card"><div class="label">Cost (USD)</div><div class="value">$'+d.total_cost+'</div></div>'+
  '<div class="card"><div class="label">Uptime</div><div class="value">'+Math.floor(d.uptime_seconds/60)+'m</div></div>';
});
fetch('/api/recent').then(r=>r.json()).then(d=>{
document.getElementById('rows').innerHTML=d.map(r=>
'<tr><td>'+fmt(r.time)+'</td><td><span class="tag '+(r.type==='zero_llm'?'zero':'llm')+'">'+r.type+'</span></td>'+
'<td>'+r.latency_ms+'ms</td><td>'+r.tokens+'</td><td>$'+r.cost+'</td><td>'+(r.rule||r.detail||'')+'</td></tr>'
).join('');
});
}
load();setInterval(load,3000);
</script></body></html>"""


if __name__ == "__main__":
    print(f"  Aether Monitor v1")
    print(f"  Open: http://{HOST}:{PORT}")
    server = HTTPServer((HOST, PORT), MonitorHandler)
    try: server.serve_forever()
    except KeyboardInterrupt: server.shutdown()
