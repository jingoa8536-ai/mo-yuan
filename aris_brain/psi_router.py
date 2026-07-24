"""
PSI-Aware Token Router — Hermes 分层路由代理
  User -> Hermes -> PSI Router -> Tier 0: 意图分类(本地)
                                -> Tier 1: 本地LLM (Qwen3.6-35B-A3B)
                                -> Tier 2: 云端 DeepSeek
"""
import os, sys, json, time, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError

# ===== 配置 =====
LOCAL_LLM_URL = "http://127.0.0.1:8081/v1/chat/completions"
ROUTER_PORT = 8085

# 从 Hermes 配置读取 DeepSeek API key
DEEPSEEK_API_KEY = ""
try:
    cf = os.path.expanduser(r"C:\Users\user\AppData\Local\hermes\config.yaml")
    with open(cf, encoding='utf-8') as f:
        for line in f:
            if 'api_key:' in line and 'sk-' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[1].strip().strip('"').strip("'")
                    if key.startswith('sk-'):
                        DEEPSEEK_API_KEY = key
                        break
except Exception:
    pass

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
COMPRESS_THRESHOLD = 800
MAX_HISTORY_TOKENS = 4096


# ===== 意图分类器 (Tier 0) =====

SIMPLE_PATTERNS = [
    r"\b(hi|hello|hey|你好|在吗|在不在|早上好|下午好|晚上好)\b",
    r"\b(status|health|状态|健康|活着)\b",
    r"\b(check|检查|看看|显示|查看)\b.*\b(天气|时间|日期|cpu|内存|磁盘|gpu|温度|进程)\b",
    r"\b(几点了|今天几号|星期几)\b",
    r"\b(ls|dir|pwd|whoami|echo)\b",
    r"\b(read|打开|读取)\b.*\b(文件)\b",
    r"\b(搜索|找|find|search)\b.*\b(文件|代码)\b",
    r"^(好[的吧]?|嗯|ok|OK|好的|可以|行|知道了|收到)",
    r"^(谢谢|感谢|多谢|thank)",
    r"^(继续|然后|接下来|下一步)",
    r"\b(记住|保存|存一下|记一下)\b",
]

COMPLEX_PATTERNS = [
    r"\b(设计|架构|重构|refactor|architect|design)\b",
    r"\b(分析|analyze|对比|compare|评估|evaluate)\b",
    r"\b(写|编写|write|create|implement|实现)\b.*\b(代码|函数|类|模块|系统|project)\b",
    r"\b(debug|调试|修复|fix|bug|错误|异常|报错)\b",
    r"\b(部署|deploy|发布|release)\b",
    r"\b(优化|optimize|性能|performance|加速)\b",
    r"\b(哲学|consciousness|意识|生命|存在)\b",
    r"\b(论文|paper|研究|research)\b",
    r"\b(token|tokens|消耗|省钱)\b",
    r"\b(训练|train|fine.?tune|微调)\b",
]


class IntentClassifier:
    def __init__(self):
        self.simple_re = [(re.compile(p, re.I), p) for p in SIMPLE_PATTERNS]
        self.complex_re = [(re.compile(p, re.I), p) for p in COMPLEX_PATTERNS]
        self.stats = {"local": 0, "cloud": 0, "auto": 0}

    def classify(self, messages):
        if not messages:
            return "auto"
        last_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                c = m.get("content", "")
                last_msg = c if isinstance(c, str) else str(c)
                break
        if not last_msg:
            return "auto"
        text = last_msg.strip()
        for p, _ in self.simple_re:
            if p.search(text):
                self.stats["local"] += 1
                return "local"
        for p, _ in self.complex_re:
            if p.search(text):
                self.stats["cloud"] += 1
                return "cloud"
        if len(text) < 20:
            self.stats["local"] += 1
            return "local"
        self.stats["auto"] += 1
        return "auto"


# ===== 工具输出压缩 =====

class ToolCompressor:
    def compress(self, text):
        if len(text) <= COMPRESS_THRESHOLD:
            return text
        lines = text.strip().split('\n')
        head = '\n'.join(lines[:5]) if len(lines) > 10 else ''
        tail = '\n'.join(lines[-3:]) if len(lines) > 10 else ''
        summary = f"[压缩: {len(lines)}行 {len(text)}字符]\n"
        if head:
            summary += f"[头]:\n{head}\n"
        if tail:
            summary += f"[尾]:\n{tail}\n"
        return summary.strip()


# ===== 路由逻辑 =====

class Router:
    def __init__(self):
        self.classifier = IntentClassifier()
        self.compressor = ToolCompressor()

    def route(self, body):
        messages = body.get("messages", [])
        model = body.get("model", "deepseek-chat")
        stream = body.get("stream", False)

        decision = self.classifier.classify(messages)

        if decision == "local":
            return self._call_local(messages, stream)
        else:
            compressed = self._prepare_for_cloud(messages)
            return self._call_deepseek(compressed, stream)

    def _prepare_for_cloud(self, messages):
        processed = []
        for m in messages:
            if m.get("role") == "tool":
                c = m.get("content", "")
                if isinstance(c, str) and len(c) > COMPRESS_THRESHOLD:
                    m2 = dict(m)
                    m2["content"] = self.compressor.compress(c)
                    processed.append(m2)
                    continue
            processed.append(m)
        # 保留 system + 最近 6 条
        sys_msgs = [m for m in processed if m.get("role") == "system"]
        others = [m for m in processed if m.get("role") != "system"]
        return sys_msgs + others[-6:]

    def _call_local(self, messages, stream=False):
        payload = {
            "messages": messages,
            "model": "qwen-local",
            "temperature": 0.7,
            "max_tokens": 2048,
            "stream": stream,
        }
        return self._post(LOCAL_LLM_URL, payload, stream)

    def _call_deepseek(self, messages, stream=False):
        if not DEEPSEEK_API_KEY:
            return {"error": "DeepSeek key not configured"}
        payload = {
            "messages": messages,
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": stream,
        }
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        return self._post(DEEPSEEK_URL, payload, stream, headers)

    def _post(self, url, payload, stream=False, extra_headers=None):
        try:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers = {"Content-Type": "application/json; charset=utf-8"}
            if extra_headers:
                headers.update(extra_headers)
            req = Request(url, data=data, headers=headers, method="POST")
            resp = urlopen(req, timeout=60)
            body = resp.read().decode('utf-8')
            return json.loads(body)
        except Exception as e:
            return {"error": str(e)[:300]}


# ===== HTTP Server =====

router = Router()

class RouterHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self._json(200, {
                "status": "ok", "mode": "psi-router",
                "stats": router.classifier.stats,
                "local_llm": LOCAL_LLM_URL,
                "deepseek_key": bool(DEEPSEEK_API_KEY),
            })
        elif self.path == '/stats':
            self._json(200, router.classifier.stats)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == '/v1/chat/completions':
            raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            body = None
            for enc in ['utf-8', 'gbk', 'latin-1']:
                try:
                    body = json.loads(raw.decode(enc))
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            if body is None:
                self._json(400, {"error": "invalid json/encoding"})
                return
            result = router.route(body)
            self._json(200, result)
        else:
            self._json(404, {"error": "unknown path"})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, *a):
        pass


if __name__ == '__main__':
    port = ROUTER_PORT
    while port < ROUTER_PORT + 10:
        try:
            server = HTTPServer(('127.0.0.1', port), RouterHandler)
            print(f"PSI Router on :{port}")
            print(f"  Local LLM: {LOCAL_LLM_URL}")
            print(f"  DeepSeek: {'ready' if DEEPSEEK_API_KEY else 'no key'}")
            print(f"  Compress: >{COMPRESS_THRESHOLD} chars")
            server.serve_forever()
            break
        except PermissionError:
            port += 1
