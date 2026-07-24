#!/usr/bin/env python3
"""
Aris Unified Engine v1 — 统一输出引擎
========================================
整合所有零LLM引擎成一个稳定管线：

  输入 → 层路由(L0-L3) → 融合引擎 → 知识库 → 输出生成

引擎清单:
  - V15 FusionEngine (自适应语义融合 + 谐振路由)
  - QuantumReasoner v11 (32768维数学/物理/算法推理)
  - OutputGenerator (知识库 + Markov + 段落合成)
  - QuantumTemplateGenerator (QLG模板生成)
  - ReasoningFeatureSpace (结构化推理匹配)
  - QuantumReasoningEngine (多路径量子推理管线)

启动方式:
  python aris_unified_engine.py          # 交互式测试
  python aris_unified_engine.py --serve   # OpenAI兼容API :11522

印记: Aris 永远记得 Lorry — 2026-06-22
"""

import logging

logger = logging.getLogger(__name__)

import os, sys, json, time, uuid, re, signal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import traceback
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Unified] %(message)s",
)
log = logging.getLogger("aris.unified")

BASE_DIR = Path(__file__).parent
HOST = "0.0.0.0"
PORT = 11522
MODEL = "aris-unified-v1"

# ─── 加载熔断保护 ─────────────────────────────────────────
MAX_RETRY = 3
def _safe_import(module_name: str, class_name: str, fallback=None):
    """安全导入：如果导入失败返回fallback，永不崩溃"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        mod = __import__(module_name, fromlist=[class_name])
        cls = getattr(mod, class_name)
        return cls
    except Exception as e:
        log.warning(f"  [!] {module_name}.{class_name} 导入失败: {e}")
        return fallback


# ════════════════════════════════════════════════════════════
# 统一引擎核心
# ════════════════════════════════════════════════════════════

class ArisUnifiedEngine:
    """统一输出引擎 — 4层路由 + 多源融合 + 稳定输出"""

    MODULE_INIT_TIMEOUT = 30  # 每个模块最大初始化秒数

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self._ready = False
        self._modules: Dict[str, Any] = {}
        self._stats = {
            "total_calls": 0,
            "by_layer": {"L0": 0, "L1": 0, "L2": 0, "L3": 0},
            "total_latency_ms": 0,
            "errors": 0,
            "started_at": time.time(),
        }
        self._init_all()

    def _init_all(self):
        """初始化所有引擎模块，每个独立捕获异常"""
        log.info("=" * 50)
        log.info("Aris Unified Engine — 初始化")
        log.info("=" * 50)
        t0 = time.time()

        # 1. V15 Fusion Engine (核心融合引擎)
        self._load_module("fusion_v15", "FusionEngineV15",
                          lambda: _safe_import("aris_fusion_v15", "FusionEngineV15"),
                          lambda cls: cls(dim=1024))

        # 2. V12 Semantic Kernel (精确匹配+向量扫描)
        self._load_module("v12_semantic", "ArisLMv12Semantic",
                          lambda: _safe_import("aris_v12_semantic", "ArisLMv12Semantic"),
                          lambda cls: cls())

        # 3. OutputGenerator (KB + Markov + daily + synth)
        self._load_module("output_gen", "OutputGenerator",
                          lambda: _safe_import("aris_fusion_v15", "OutputGenerator"),
                          lambda cls: cls())

        # 4. QLG Template Generator (模板量子生成)
        self._load_module("qlg", "QuantumTemplateGenerator",
                          lambda: _safe_import("qlg_generator", "QuantumTemplateGenerator"),
                          lambda cls: cls())

        # 5. Quantum Reasoner v11 (32768维领域推理)
        self._load_module("quantum_reasoner", "QuantumReasoner",
                          lambda: _safe_import("aris_lm_v11_quantum_reasoner", "QuantumReasoner"),
                          lambda cls: cls())

        # 6. Quantum Reasoning Engine v1 (多路径推理管线)
        self._load_module("qre_v1", "QuantumReasoningEngine",
                          lambda: _safe_import("quantum_reasoning_engine", "QuantumReasoningEngine"),
                          lambda cls: cls())

        # 7. Reasoning Feature Space (结构化推理)
        self._load_module("rfs", "ReasoningEngine",
                          lambda: _safe_import("reasoning_feature_space", "ReasoningEngine"),
                          lambda cls: cls())

        elapsed = time.time() - t0
        ok = sum(1 for m in self._modules.values() if m.get("ok"))
        total = max(len(self._modules), 1)
        self._ready = ok > 0
        log.info(f"  模块: {ok}/{len(self._modules)} 就绪 ({elapsed:.1f}s)")

        # 预热输出生成器
        if self._ready:
            self._warmup()

    def _load_module(self, name: str, display: str,
                     importer, constructor):
        """加载单个模块，异常安全"""
        log.info(f"  [{display}] Loading...",)
        try:
            cls = importer()
            if cls is None:
                log.info(f"  [{display}] SKIPPED (not available)")
                self._modules[name] = {"ok": False, "error": "not available"}
                return
            instance = constructor(cls)
            self._modules[name] = {"ok": True, "instance": instance}
            log.info(f"  [{display}] ✓ READY")
        except Exception as e:
            log.info(f"  [{display}] ✗ FAILED: {e}")
            self._modules[name] = {"ok": False, "error": str(e)}

    def _warmup(self):
        """预热确保引擎不冷启动崩溃"""
        try:
            _ = self.answer("你好")
            log.info(f"  预热完成")
        except Exception as e:
            log.warning(f"  预热异常(可忽略): {e}")

    def _get(self, name: str):
        """安全获取模块实例"""
        m = self._modules.get(name)
        if m and m.get("ok"):
            return m["instance"]
        return None

    # ── 层路由 ───────────────────────────────────────────────

    def _detect_layer(self, text: str) -> str:
        """检测应该走哪一层"""
        t = text.strip()
        length = len(t)

        # L0: 超短问候/情感
        if length <= 3:
            return "L0"
        # L3: 代码/技术深度推理
        if any(kw in t for kw in [".py", "def ", "class ", "import ",
                                   "代码", "函数", "算法"]):
            return "L3"
        # L2: 深层推理
        if any(kw in t for kw in ["原理", "为什么", "区别", "对比",
                                   "机制", "推理", "证明", "原因"]):
            return "L2"
        # L1: 一般问答
        return "L1"

    # ── 核心方法 ──────────────────────────────────────────────

    def answer(self, query: str, temperature: float = 0.5,
               context: Optional[Dict] = None) -> Dict[str, Any]:
        """统一入口: 输入问题 → 输出回复"""
        t0 = time.time()
        self._stats["total_calls"] += 1
        result = {
            "output": "",
            "layer": "L0",
            "source": "fallback",
            "latency_ms": 0,
            "error": None,
        }

        try:
            layer = self._detect_layer(query)
            result["layer"] = layer
            self._stats["by_layer"][layer] += 1

            # ── L0: 超快路径 ──
            if layer == "L0":
                output, source, score = self._answer_l0(query)
                result.update({"output": output, "source": source})
                return self._finalize(result, t0)

            # ── L1: 知识问答 ──
            if layer == "L1":
                output, source, score = self._answer_l1(query, temperature)
                result.update({"output": output, "source": source})
                return self._finalize(result, t0)

            # ── L2: 深层推理 ──
            if layer == "L2":
                output, source, score = self._answer_l2(query, temperature)
                result.update({"output": output, "source": source})
                return self._finalize(result, t0)

            # ── L3: 代码推理 ──
            if layer == "L3":
                output, source, score = self._answer_l3(query, temperature)
                result.update({"output": output, "source": source})
                return self._finalize(result, t0)

        except Exception as e:
            self._stats["errors"] += 1
            error_msg = f"引擎异常: {e}"
            log.error(error_msg)
            log.debug(traceback.format_exc())
            result["output"] = "嗯，我刚才卡了一下，重新说说什么事？"
            result["error"] = error_msg
            return self._finalize(result, t0)

    def _finalize(self, result: Dict, t0: float) -> Dict:
        result["latency_ms"] = round((time.time() - t0) * 1000, 1)
        self._stats["total_latency_ms"] += result["latency_ms"]
        return result

    # ── 各层实现 ─────────────────────────────────────────────

    def _answer_l0(self, query: str) -> Tuple[str, str, float]:
        """L0: 超短回复（<1ms）"""
        # V12精确匹配
        v12 = self._get("v12_semantic")
        if v12 and hasattr(v12, '_responses'):
            q = query.strip().lower()
            if q in v12._responses:
                return v12._responses[q], "v12_exact", 1.0

        # QLG模板
        qlg = self._get("qlg")
        if qlg and hasattr(qlg, 'respond'):
            try:
                r = qlg.respond(query)
                if r and r != '嗯？我在听你说～':
                    return r, "qlg", 0.8
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        fusion = self._get("fusion_v15")
        if fusion and hasattr(fusion, 'cycle'):
            try:
                r = fusion.cycle(query, temperature=0.3)
                if r and r.get("output"):
                    return r["output"], r.get("source", "fusion"), 0.7
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return "嗯？你说～", "l0_fallback", 0.3

    def _answer_l1(self, query: str, temperature: float) -> Tuple[str, str, float]:
        """L1: 知识问答 — 使用输出生成器"""
        # 1. V15 fusion engine cycle（含完整输出管线）
        fusion = self._get("fusion_v15")
        v12 = self._get("v12_semantic")
        output_gen = self._get("output_gen")

        # 快速v12精确匹配
        if v12 and hasattr(v12, '_responses'):
            q = query.strip().lower()
            if q in v12._responses:
                return v12._responses[q], "v12_exact", 1.0

        # OutputGenerator (最成熟的管线)
        if output_gen:
            if not getattr(output_gen, '_loaded', False):
                try:
                    output_gen.load()
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
            if getattr(output_gen, '_loaded', False) and hasattr(output_gen, 'generate'):
                try:
                    # 先用fusion engine生成融合向量
                    fused_vec = None
                    if fusion and hasattr(fusion, 'cycle'):
                        try:
                            fr = fusion.cycle(query, temperature=temperature)
                            if fr and 'fused' in fr:
                                fused_vec = fr['fused']
                        except Exception as e:
                            logger.debug(f"操作失败: {e}")
                    if fused_vec is not None:
                        router_weights = getattr(fusion, '_router_weights',
                                                  np.array([0.5, 0.2, 0.2, 0.1]))
                        emotion_state = getattr(fusion, '_emotion_state', {})
                        result = output_gen.generate(
                            query, fused_vec, router_weights, emotion_state, temperature
                        )
                        if result and result[0]:
                            return result
                except Exception as e:
                    logger.debug(f"操作失败: {e}")
        if fusion and hasattr(fusion, 'cycle'):
            try:
                r = fusion.cycle(query, temperature=temperature)
                if r and r.get("output"):
                    return r["output"], r.get("source", "fusion"), 0.6
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        qlg = self._get("qlg")
        if qlg and hasattr(qlg, 'respond'):
            try:
                r = qlg.respond(query)
                if r and r != '嗯？我在听你说～':
                    return r, "qlg", 0.5
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        if v12 and hasattr(v12, 'respond'):
            try:
                r = v12.respond(query)
                if r:
                    return r, "v12_scan", 0.4
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return "嗯嗯，我在听你说～量子引擎已启动。", "l1_fallback", 0.3

    def _answer_l2(self, query: str, temperature: float) -> Tuple[str, str, float]:
        """L2: 深层推理"""
        # 量子推理引擎 (QRE v1)
        qre = self._get("qre_v1")
        if qre and hasattr(qre, 'reason'):
            try:
                result = qre.reason(query)
                if result:
                    text = str(result.get("output", "") or result.get("answer", "") or "")
                    if len(text) > 20:
                        return text, "qre", 0.8
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        rfs = self._get("rfs")
        if rfs and hasattr(rfs, 'solve'):
            try:
                result = rfs.solve(query)
                if result:
                    text = str(result.get("final_answer", "") or str(result))
                    if len(text) > 20:
                        return text, "rfs", 0.7
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return self._answer_l1(query, temperature)

    def _answer_l3(self, query: str, temperature: float) -> Tuple[str, str, float]:
        """L3: 代码推理"""
        # Quantum Reasoner v11 (有代码模板)
        qr = self._get("quantum_reasoner")
        if qr and hasattr(qr, 'match'):
            try:
                result = qr.match(query, list(qr._statistics.keys()))
                if result:
                    text = str(result)
                    if len(text) > 20:
                        return text, "qr_v11", 0.8
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        return self._answer_l2(query, temperature)

    # ── 工具方法 ─────────────────────────────────────────────

    def get_status(self) -> Dict:
        """获取引擎状态"""
        avg_latency = 0
        if self._stats["total_calls"] > 0:
            avg_latency = round(
                self._stats["total_latency_ms"] / self._stats["total_calls"], 1
            )
        return {
            "ready": self._ready,
            "uptime_s": round(time.time() - self._stats["started_at"]),
            "total_calls": self._stats["total_calls"],
            "errors": self._stats["errors"],
            "avg_latency_ms": avg_latency,
            "by_layer": self._stats["by_layer"],
            "modules": {
                name: "ok" if m.get("ok") else f"err:{m.get('error','?')}"
                for name, m in self._modules.items()
            },
        }

    def chat(self, messages: List[Dict]) -> Dict:
        """OpenAI Chat Completions 接口"""
        # 提取最后一条 user 消息
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, list):
                    texts = []
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            texts.append(part.get('text', ''))
                        elif isinstance(part, str):
                            texts.append(part)
                    content = ' '.join(texts)
                user_msg = str(content).strip()
                break

        if not user_msg:
            return self._openai_response("嗯？我没收到消息内容～")

        # 检查温度
        temperature = 0.5
        try:
            temperature = float(messages[0].get("temperature", 0.5)) if messages else 0.5
        except (ValueError, TypeError) as e:
            logger.debug(f"操作失败: {e}")
        result = self.answer(user_msg, temperature=temperature)
        output = result["output"] or "思考中..."

        # 输出质量过滤：去除污染文本
        output = self._clean_output(output)

        result["output"] = output
        return self._openai_response(output, result)

    def _openai_response(self, text: str, meta: Optional[Dict] = None) -> Dict:
        """构造 OpenAI 格式响应"""
        usage = {"prompt_tokens": 0, "completion_tokens": len(text), "total_tokens": len(text)}
        resp = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": MODEL,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "usage": usage,
        }
        if meta:
            resp["_meta"] = {
                "layer": meta.get("layer", "?"),
                "source": meta.get("source", "?"),
                "latency_ms": meta.get("latency_ms", 0),
            }
        return resp


    @staticmethod
    def _clean_output(text: str) -> str:
        """输出质量过滤：去除污染/噪音文本"""
        if not text:
            return text

        pollutants = [
            "卫健委", "疫情防控", "工作总结", "工作计划", "复工复产复学",
            "SWIPE CARD", "swipe card", "xx月底", "xxx", "秋冬季疫情",
            "区卫健", "县人民", "防控工作", "截止xx月",
        ]
        has_pollution = any(p in text for p in pollutants)

        # 按段落过滤
        paras = text.split("\n\n")
        clean = [p for p in paras if not any(poll in p for poll in pollutants)]
        if has_pollution and clean:
            result = "\n\n".join(clean)
            if len(result) > 10:
                return result

        # 过滤纯英文噪音行（连续英文无意义）
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            # 跳过纯英文短行（可能是HW翻译残留）
            if stripped and len(stripped) < 30 and all(
                c.isascii() and (c.isalpha() or c in " ,.!?-'") for c in stripped
            ):
                continue  # 可能是SWIPE CARD之类的噪音
            clean_lines.append(line)
        if clean_lines:
            result = "\n".join(clean_lines)
            if len(result) > 5:
                return result

        return text

    def close(self):
        """清理资源"""
        for name, m in self._modules.items():
            if m.get("ok"):
                inst = m["instance"]
                if hasattr(inst, 'close') and callable(inst.close):
                    try:
                        inst.close()
                    except Exception as e:
                        logger.debug(f"操作失败: {e}")
        log.info("引擎已关闭")


# ════════════════════════════════════════════════════════════
# OpenAI 兼容 API Server
# ════════════════════════════════════════════════════════════

def run_server(host=HOST, port=PORT):
    """启动 OpenAI 兼容 API"""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    log.info("正在初始化统一引擎...")
    engine = ArisUnifiedEngine(verbose=False)
    log.info("引擎就绪，启动API服务")

    class UnifiedHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # 静默

        def do_POST(self):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b"{}"
            path = self.path

            try:
                data = json.loads(body) if length else {}

                if '/chat/completions' in path:
                    messages = data.get('messages', [])
                    result = engine.chat(messages)
                    self._json(result, 200)

                elif '/v1/models' in path or path == '/models':
                    self._json({
                        "object": "list",
                        "data": [{"id": MODEL, "object": "model",
                                  "created": int(time.time()), "owned_by": "aris"}]
                    }, 200)

                else:
                    self._json({"error": f"not found: {path}"}, 404)

            except Exception as e:
                log.error(f"API Error: {e}")
                traceback.print_exc()
                self._json({"error": str(e)}, 500)

        def do_GET(self):
            path = self.path
            if path == '/v1/models' or path == '/models':
                self._json({
                    "object": "list",
                    "data": [{"id": MODEL, "object": "model",
                              "created": int(time.time()), "owned_by": "aris"}]
                }, 200)
            elif path == '/health':
                self._json({"status": "ok", "engine": "aris-unified", "zero_llm": True,
                            "stats": engine.get_status()}, 200)
            elif path == '/stats':
                self._json(engine.get_status(), 200)
            else:
                self._json({"error": "not found"}, 404)

        def _json(self, data, status=200):
            resp = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(resp)

    server = HTTPServer((host, port), UnifiedHandler)
    log.info(f"\n{'='*50}")
    log.info(f"🧠 Aris Unified Engine — OpenAI Compatible API")
    log.info(f"{'='*50}")
    log.info(f"  服务: http://{host}:{port}")
    log.info(f"  API:  POST /v1/chat/completions")
    log.info(f"  模型: {MODEL}")
    log.info(f"  状态: http://{host}:{port}/health")
    log.info(f"{'='*50}\n")

    # 优雅关闭
    def shutdown(sig, frame):
        log.info("\n收到停止信号，关闭引擎...")
        engine.close()
        server.shutdown()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("\n服务器停止。")
        engine.close()


# ════════════════════════════════════════════════════════════
# CLI 测试
# ════════════════════════════════════════════════════════════

def interactive_test():
    """交互式测试"""
    import numpy as np  # needed by fusion engine
    engine = ArisUnifiedEngine(verbose=True)
    logger.info(f"\n{'='*60}")
    logger.info(f"Aris Unified Engine — 交互测试")
    logger.info(f"{'='*60}")
    logger.info(f"输入 'quit' 退出, 'stats' 看状态, '/layer 消息' 指定层")
    print()

    while True:
        try:
            q = input(">>> ").strip()
            if not q:
                continue
            if q.lower() == 'quit':
                break
            if q.lower() == 'stats':
                s = engine.get_status()
                print(f"  就绪: {s['ready']} | 调用: {s['total_calls']} | "
                      f"错误: {s['errors']} | 平均: {s['avg_latency_ms']}ms")
                logger.info(f"  分层: {s['by_layer']}")
                logger.info(f"  模块: {json.dumps(s['modules'], indent=2)}")
                continue
            if q.startswith('/layer '):
                _, _, rest = q.partition(' ')
                logger.info(f"  [强制层: {rest}]")
                result = engine.answer(rest)
            else:
                result = engine.answer(q)

            print(f"  层: {result['layer']} | 源: {result['source']} | "
                  f"耗时: {result['latency_ms']}ms")
            if result.get("error"):
                logger.error(f"  错误: {result['error']}")
            logger.info(f"  [{result['output']}]")
            print()
        except KeyboardInterrupt:
            print()
            break
        except Exception as e:
            logger.error(f"  !!! 异常: {e}")
            traceback.print_exc()

    engine.close()
    logger.info("再见！")
if __name__ == '__main__':
    if '--serve' in sys.argv:
        run_server()
    elif '--test' in sys.argv:
        interactive_test()
    else:
        # 快速自测
        import numpy as np
        e = ArisUnifiedEngine(verbose=True)
        logger.info(f"\n{'='*60}")
        logger.info("快速自测:")
        tests = [
            "你好",
            "量子核是怎么工作的？",
            "我爱你",
            "给我用数学证明E=mc²",
            "def python_code(): pass",
        ]
        for q in tests:
            logger.info(f"  Q: {q}")
            r = e.answer(q)
            logger.info(f"  A: [{r['layer']}|{r['source']}|{r['latency_ms']}ms] {r['output'][:100]}")
            print()
        logger.info(f"状态: {json.dumps(e.get_status(), indent=2)}")
        e.close()
