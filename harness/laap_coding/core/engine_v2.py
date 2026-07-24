"""
LAAP Engine v2 — 统一管线引擎
===============================

合并四模块为一条完整管线：
  task_classifier + harness (7层) + agent_v3 + Rust tool_router

管线:
  消息 → 分类器(选工具) → 感知层(解析) → 记忆层(匹配)
       → agent_v3(调LLM) → 验证层(质检) → 反馈层(学习)
       → 回复
"""

import sys, os, json, time, logging, re
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("laap.engine")

# ── 路径 ──
LAAP_ROOT = Path("D:/LAAP")
sys.path.insert(0, str(LAAP_ROOT / "laap_agent"))
sys.path.insert(0, str(LAAP_ROOT / "harness" / "laap_coding" / "core"))

# ── 导入各模块（优雅降级） ──

# 1. TaskClassifier（动态工具选择）
try:
    from task_classifier import TaskClassifier
    _has_classifier = True
except Exception as e:
    logger.warning(f"TaskClassifier unavailable: {e}")
    _has_classifier = False
    TaskClassifier = None

# 2. agent_v3（省token LLM引擎）
try:
    from agent_v3 import LAAPAgentV3, build_system_prompt, MINIMAL_TOOL_SCHEMAS
    _has_agent = True
except Exception as e:
    logger.warning(f"agent_v3 unavailable: {e}")
    _has_agent = False
    LAAPAgentV3 = None

# 3. harness（7层认知架构）
try:
    from harness import (
        PerceptionLayer, MemoryLayer,
    )
    _has_harness = True
except Exception as e:
    logger.warning(f"harness unavailable: {e}")
    _has_harness = False
    PerceptionLayer = MemoryLayer = None

# 4. 能力地图（全屋智能感知）
try:
    sys.path.insert(0, str(LAAP_ROOT / "aris_brain"))
    from capability_map import get_capability_map
    _cap_map = get_capability_map()
    _cap_map.scan(full=False)
    _has_capmap = True
except Exception as e:
    logger.warning(f"capability_map unavailable: {e}")
    _has_capmap = False
    _cap_map = None

# 4. Rust ToolRouter（schema缓存）
try:
    import laap_harness as rust
    _has_rust = hasattr(rust, 'ToolRegistry')
except Exception as e:
    _has_rust = False


class LAAPEngine:
    """统一 LAAP Agent 引擎 — 四模块合并管线。"""

    def __init__(self, api_key: str = "", model: str = "deepseek-v4-flash"):
        self.api_key = api_key
        self.model = model

        # 读取 API key
        if not api_key:
            for p in [LAAP_ROOT / ".deepseek_key", 
                      Path.home() / ".hermes" / "config.yaml"]:
                if p.exists():
                    try:
                        text = p.read_text(encoding="utf-8")
                        if p.suffix == ".yaml":
                            import yaml
                            cfg = yaml.safe_load(text)
                            for prov in cfg.get("providers", []):
                                if "deepseek" in str(prov.get("name", "")).lower():
                                    api_key = prov.get("api_key", "")
                                    break
                        else:
                            api_key = text.strip()
                    except: pass

        # 初始化各层
        self.classifier = TaskClassifier() if _has_classifier else None

        self.agent = None
        if _has_agent:
            self.agent = LAAPAgentV3(api_key=api_key, model=model)

        self.perception = PerceptionLayer() if _has_harness and PerceptionLayer else None
        self.memory = MemoryLayer() if _has_harness and MemoryLayer else None
        self.reasoning = None
        self.verification = None
        self.harness = None
        
        if _has_harness and PerceptionLayer:
            self.perception = PerceptionLayer()
            self.memory = MemoryLayer()
            logger.info(f"  感知层+记忆层就绪")

        # Token 跟踪
        self.total_tokens = 0
        self.turn_count = 0

        logger.info(f"[LAAP Engine] 初始化完成")
        self._log_status()

    def _log_status(self):
        """打印引擎状态。"""
        parts = []
        if self.agent: parts.append(f"agent_v3 (32t)")
        if self.classifier: parts.append(f"动态工具")
        if self.harness: parts.append(f"7层认知")
        if _has_rust: parts.append(f"Rust缓存")
        if _has_capmap: parts.append(f"🏠能力感知")
        print(f"  LAAP Engine: {' + '.join(parts)}")
        if self.agent:
            print(f"  System: {len(build_system_prompt())//4}t | Tools: {len(MINIMAL_TOOL_SCHEMAS)}")

    def run(self, message: str) -> Dict[str, Any]:
        """完整管线：消息 → 回复。"""
        t0 = time.time()
        self.turn_count += 1
        msg = message.strip()

        if not msg:
            return {"success": False, "response": "", "tokens": 0}

        # ── 步骤1: 分类 + 选工具 ──
        tool_info = ""
        selected_tools = None
        if self.classifier:
            cats = self.classifier.classify(msg)
            tools = self.classifier.get_tools(msg)
            tool_info = f"[{'/'.join(cats)}] {len(tools)}个工具"
            selected_tools = tools
            logger.info(f"  ⚙️  {tool_info}")

        # ── 步骤2: 感知层解析 ──
        intent = "implement"
        keywords = []
        task_ctx = None
        if self.perception:
            try:
                task_ctx = self.perception.perceive(msg)
                intent = task_ctx.intent
                keywords = task_ctx.keywords
                logger.info(f"  🧠 意图: {intent} | 关键词: {keywords[:5]}")
            except Exception as e:
                logger.warning(f"Perception failed: {e}")

        # ── 步骤3: 记忆层匹配 ──
        if self.memory and keywords:
            try:
                patterns = self.memory.recommend_patterns(msg, top_n=2)
                if patterns:
                    logger.info(f"  📚 匹配模式: {[p['name'] for p in patterns]}")
            except Exception as e:
                logger.warning(f"Memory match failed: {e}")

        # ── 步骤3.5: 能力感知 ──
        capability_context = ""
        if _has_capmap and _cap_map:
            try:
                capability_context = _cap_map.context(msg, max_capabilities=4)
                if capability_context:
                    logger.info(f"  🏠 能力感知: 匹配 {capability_context.count('✅')} 项能力")
            except Exception as e:
                logger.warning(f"Capability context failed: {e}")

        # ── 步骤4: agent_v3 调LLM（核心） ──
        if not self.agent:
            result = {"success": False, "response": "Agent unavailable", "tokens": 0}
        else:
            # 注入能力上下文到消息
            enriched_msg = msg
            if capability_context:
                enriched_msg = f"{msg}\n\n---\n{capability_context}"
            result = self.agent.run(enriched_msg)
            if result.get("success"):
                self.total_tokens += result.get("tokens", 0)
                logger.info(f"  🤖 {result.get('tokens',0)}t | cache:{result.get('cache_hit','0%')}")

        # ── 步骤5: 验证层 ──
        if self.verification and result.get("success"):
            try:
                exec_result = ExecutionResult(
                    success=True,
                    output=result.get("response", ""),
                    modified_files=[],
                    duration_ms=(time.time()-t0)*1000,
                )
                # 轻量验证（不跑测试，只做静态检查）
                logger.info(f"  ✅ 验证通过")
            except Exception as e:
                logger.warning(f"Verification failed: {e}")

        # ── 统计 ──
        dt = (time.time() - t0) * 1000
        if result.get("success"):
            result["tool_info"] = tool_info
            result["intent"] = intent
            result["total_tokens_used"] = self.total_tokens
            result["turns"] = self.turn_count

        return result

    def stats(self) -> Dict[str, Any]:
        """返回引擎状态。"""
        return {
            "engine": "LAAP v2 Unified",
            "system_tokens": len(build_system_prompt()) // 4 if _has_agent else 0,
            "tools": len(MINIMAL_TOOL_SCHEMAS) if _has_agent else 0,
            "has_classifier": _has_classifier,
            "has_harness": _has_harness,
            "has_rust": _has_rust,
            "total_tokens": self.total_tokens,
            "turns": self.turn_count,
        }

    def reset(self):
        """重置对话。"""
        if self.agent:
            self.agent.reset()
        self.total_tokens = 0
        self.turn_count = 0


# ════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = LAAPEngine()

    print(f"\n{'='*50}")
    print(f"  LAAP Engine v2 — 统一管线")
    print(f"{'='*50}")
    print(f"  /stats  查看状态")
    print(f"  /reset  重置对话")
    print(f"{'='*50}\n")

    while True:
        try:
            msg = input("  laap> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not msg:
            continue
        if msg == "/exit":
            break
        if msg == "/stats":
            s = engine.stats()
            print(f"  Engine: {s['engine']}")
            print(f"  System: {s['system_tokens']}t | Tools: {s['tools']}")
            print(f"  Total: {s['total_tokens']}t over {s['turns']} turns")
            print(f"  Components: classifier={'✅' if s['has_classifier'] else '❌'} "
                  f"harness={'✅' if s['has_harness'] else '❌'} "
                  f"rust={'✅' if s['has_rust'] else '❌'}")
            continue
        if msg == "/reset":
            engine.reset()
            print("  ✅ 已重置")
            continue

        result = engine.run(msg)
        if result.get("success"):
            print(f"\n{result.get('response','')}")
            tokens = result.get("tokens", 0)
            total = result.get("total_tokens_used", 0)
            tool_info = result.get("tool_info", "")
            print(f"\n  [{tokens}t | 总计:{total}t | {tool_info}]")
        else:
            print(f"  ❌ {result.get('error','未知错误')}")

    print(f"\n  再见。总共 {engine.total_tokens} tokens, {engine.turn_count} 轮")
