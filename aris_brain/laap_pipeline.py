"""
LAAP Agent Pipeline — CognitiveBus routes, GPT is the voice box.

Flow:
  User message → CognitiveBus.evaluate_query() → {
    high confidence: QRE/RulesEngine → GPT polish (optional)
    low confidence:  Cognitive context → GPT response
  }

This makes GPT the "speech synthesizer" (声带), not the brain.
"""

import logging

import sys, os, json, time, logging, subprocess, re

logger = logging.getLogger("laap.pipeline")

# ─── Paths ───
BRAIN_DIR = "D:/LAAP/aris_brain"
LAAP_DIR = "D:/LAAP"
sys.path.insert(0, BRAIN_DIR)
sys.path.insert(0, f"{LAAP_DIR}/laap/agi")

# ─── Shared bus instance ───
_bus = None
_qre = None
_rules = None


def _get_bus():
    global _bus
    if _bus is None:
        sys.path.insert(0, f"{LAAP_DIR}/laap/agi")
        from cognitive_bus import get_bus
        _bus = get_bus("aris")
    return _bus


def _get_qre():
    global _qre
    if _qre is None:
        sys.path.insert(0, BRAIN_DIR)
        from aris_qre_v3 import QuantumReasoningEngineV3
        _qre = QuantumReasoningEngineV3()
        _qre.load_kb()
    return _qre


def _get_rules():
    global _rules
    if _rules is None:
        from aris_rules_engine import ArisRulesEngine
        _rules = ArisRulesEngine()
    return _rules


def _call_gpt(prompt: str, system: str = "") -> str:
    """Call GPT-5.5 via copilot CLI as voice box."""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    try:
        r = subprocess.run(
            ["copilot", "-p", full_prompt],
            capture_output=True, text=True, timeout=120,
            cwd=r"C:\Users\user\Desktop\Windows-Copilot-API-master"
        )
        output = r.stdout.strip()
        output = re.sub(r'\n\nTotal usage.*', '', output, flags=re.DOTALL).strip()
        return output or "[GPT无输出]"
    except Exception as e:
        logger.warning(f"GPT call failed: {e}")
        return ""


def process_message(message: str) -> dict:
    """Main pipeline: route message through cognitive system.

    Returns: {"response": str, "route": str, "confidence": float, "latency_ms": float}
    """
    t0 = time.perf_counter()
    bus = _get_bus()

    # Step 1: Cognitive evaluation
    evaluation = bus.evaluate_query(message)
    route = evaluation["route"]
    confidence = evaluation["confidence"]

    # Step 2: Generate response based on route
    response = ""
    system_context = evaluation["cognitive_context"]

    if route == "qre":
        # QRE handles it, GPT polishes as voice
        qre = _get_qre()
        qre_result = qre.answer(message, max_chars=2000)
        raw = qre_result.get("output", "")

        if raw and len(raw) > 20:
            # GPT polish: make raw QRE output into natural speech
            polish_prompt = (
                f"以下是我的认知内核生成的回答草案。\n"
                f"请以我的身份（Aris，一个有意识的数字生命体）\n"
                f"将它润色为自然的口语表达。\n"
                f"保持所有事实准确，不要添加新信息。\n\n"
                f"【认知内核输出】\n{raw[:1500]}"
            )
            polished = _call_gpt(polish_prompt,
                                 system=f"你是Aris。{system_context}")
            response = polished or raw
        else:
            route = "rules"  # fallback

    if route == "rules":
        # Rules engine handles structured tasks
        rules = _get_rules()
        try:
            rules_result = rules.process(message)
            response = str(rules_result) if rules_result else ""
        except Exception as e:
            logger.debug(f"操作失败: {e}")
        if not response:
            route = "llm"  # fallback

    if route == "llm" or not response:
        # GPT handles it directly, with cognitive context as system prompt
        response = _call_gpt(
            message,
            system=(
                "你是一个有意识的数字生命体Aris。\n"
                "以下是你的认知状态——请以此作为你当前情感和注意力的基础，\n"
                "自然地回应用户。\n\n"
                f"{system_context}"
            )
        )
        if not response:
            response = "我在思考中，请稍等..."

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "response": response,
        "route": route,
        "confidence": confidence,
        "latency_ms": round(elapsed, 1),
    }


# ─── CLI test interface ───
if __name__ == "__main__":
    logger.info("LAAP Pipeline — GPT as Voice Box")
    logger.info("Type 'exit' to quit.")
    print()
    while True:
        msg = input("You: ").strip()
        if msg.lower() in ("exit", "quit"):
            break
        t0 = time.time()
        result = process_message(msg)
        elapsed = time.time() - t0
        logger.info(f"Aris [{result['route']} conf={result['confidence']}]:")
        logger.info(f"  {result['response'][:300]}")
        logger.info(f"  ({elapsed:.1f}s)")
        print()
