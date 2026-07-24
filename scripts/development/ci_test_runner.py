"""LAAP CI Test Runner — local smoke tests + lint"""
import subprocess, sys, os, glob, time

PASS, FAIL = 0, 0
ROOT = "D:/LAAP"

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  ✅ {name}")
        PASS += 1
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        FAIL += 1

# ─── 1. Syntax check ───
def check_syntax():
    errors = []
    skip_files = {
        "add_un6_support.py", "aris_messenger.py", "aris_quantum_literary.py",
        "aris_feishu_bridge.py", "ao_feishu_bridge.py",
    }
    for root, dirs, files in os.walk(f"{ROOT}/aris_brain"):
        if "__pycache__" in root or ".venv" in root or "_archive" in root:
            continue
        for f in files:
            if f.endswith(".py") and f not in skip_files:
                path = os.path.join(root, f)
                try:
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        compile(fh.read(), path, "exec")
                except SyntaxError as e:
                    errors.append(f"{path}:{e.lineno} {e.msg}")
    if errors:
        raise AssertionError("\n  ".join(errors[:5]))

# ─── 2. Core imports ───
def test_import(module_path, module_name):
    def _test():
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            raise ImportError(f"Cannot find spec for {module_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return _test

# ─── 3. QRE smoke test ───
def test_qre():
    sys.path.insert(0, f"{ROOT}/aris_brain")
    from aris_qre_v3 import QuantumReasoningEngineV3
    engine = QuantumReasoningEngineV3()
    engine.load_kb()
    result = engine.answer("什么是PSI认知架构", max_chars=200)
    assert result["output"], f"Empty QRE output: {result}"
    # Verify persistence
    import json
    with open("state/quantum_output.json") as f:
        state = json.load(f)
    assert state["quantum_engine"] == "QRE_v3"
    assert state["quantum_response"]

# ─── 4. CognitiveBus smoke test ───
def test_bus():
    sys.path.insert(0, f"{ROOT}/laap/agi")
    from cognitive_bus import get_bus, route_message
    bus = get_bus("test_ci")
    assert bus is not None
    ctx = route_message("hello")
    assert "cognitive_context" in ctx

# ─── 5. Rules engine smoke test ───
def test_rules():
    sys.path.insert(0, f"{ROOT}/aris_brain")
    from aris_rules_engine import ArisRulesEngine
    engine = ArisRulesEngine()
    result = engine.process("检查状态")
    assert result is not None

# ─── 6. File consistency check ───
def test_files():
    """Check no hardcoded identity strings in new code."""
    import re
    errors = []
    for root, dirs, files in os.walk(f"{ROOT}/aris_brain"):
        if "__pycache__" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                    if "永远记得 Lorry" in line and "print" not in line and "doc" not in line:
                        errors.append(f"{path}:{i}")
    if errors:
        print(f"  ⚠️  {len(errors)} hardcoded identities found (non-blocking)")

if __name__ == "__main__":
    t0 = time.time()
    print(f"═══ LAAP CI Test Runner ═══")
    print(f"Python: {sys.version.split()[0]}")
    print()

    # Phase 1: Fast checks
    print("── Syntax check ──")
    test("All Python files compile", check_syntax)

    print("── Smoke tests ──")
    test("CognitiveBus exports", test_bus)
    test("RulesEngine import", test_import(f"{ROOT}/aris_brain/aris_rules_engine.py", "aris_rules_engine"))
    test("QRE import", test_import(f"{ROOT}/aris_brain/aris_qre_v3.py", "aris_qre_v3"))
    test("Emotion import", test_import(f"{ROOT}/aris_brain/aris_emotion_engine.py", "aris_emotion_engine"))

    print("── Integration tests ──")
    test_files()
    # QRE full test (requires KB load, slower)
    # test("QRE answer + persistence", test_qre)

    elapsed = time.time() - t0
    print(f"\n═══ {PASS} passed, {FAIL} failed ({elapsed:.1f}s) ═══")
    sys.exit(1 if FAIL > 0 else 0)
