"""
Ψ-Semiotics 引擎预热脚本 — Hermes 启动时自动加载

在 Hermes 新会话开始时预热量子引擎，使引擎立即可用。
同时验证所有组件是否正常。
"""

import sys
import os
import time
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("psi_preload")

BRAIN = Path("D:/LAAP/aris_brain")
SEMIOTICS = BRAIN / "psi_semiotics"

for p in [str(BRAIN), str(SEMIOTICS)]:
    if p not in sys.path:
        sys.path.insert(0, p)


def preheat() -> dict:
    """预热引擎，返回状态报告"""
    start = time.time()
    status = {"preloaded": False, "components": {}, "latency_ms": 0, "error": None}
    
    try:
        # 1. 加载结构化编码器
        from structured_encoder import StructuredSemanticEncoder
        enc = StructuredSemanticEncoder(output_dim=1024)
        status["components"]["encoder"] = True
        logger.info("[Ψ预加载] 编码器 OK")
        
        # 2. 加载 Ψ-Semiotics 引擎
        from psi_semiotics_core import PsiSemioticsEngine
        engine = PsiSemioticsEngine(dim=1024)
        status["components"]["psi_engine"] = True
        logger.info(f"[Ψ预加载] 引擎 OK ({len(engine.symbols)} 符号)")
        
        # 3. 尝试加载 V12 密集核
        try:
            from aris_v12_dense_kernel import V12DenseKernel
            v12 = V12DenseKernel()
            status["components"]["v12_kernel"] = True
            logger.info("[Ψ预加载] V12 核 OK")
        except Exception as e:
            status["components"]["v12_kernel"] = False
            logger.info(f"[Ψ预加载] V12 核不可用: {e}")
        
        # 4. 尝试加载 Cognitive Bridge 集成
        try:
            from aris_cognitive_bridge import ArisCognitiveBridge
            bridge = ArisCognitiveBridge()
            status["components"]["cognitive_bridge"] = True
            logger.info("[Ψ预加载] 认知桥 OK")
        except Exception as e:
            status["components"]["cognitive_bridge"] = False
            logger.info(f"[Ψ预加载] 认知桥不可用: {e}")
        
        # 5. 快速自检
        test_vec = enc.encode("consciousness quantum self")
        field = engine.semantic_field_map(test_vec, top_k=3)
        status["self_check"] = {
            "query": "consciousness quantum self",
            "top_symbols": [{"name": n, "strength": round(float(s), 4)} for n, s in field],
        }
        
        status["preloaded"] = True
        status["latency_ms"] = round((time.time() - start) * 1000, 1)
        logger.info(f"[Ψ预加载] 完成 ({status['latency_ms']}ms)")
        
    except Exception as e:
        status["error"] = str(e)
        logger.error(f"[Ψ预加载] 失败: {e}")
    
    return status


def verify() -> dict:
    """验证引擎是否可用（供外部调用）"""
    status = {"ready": False, "error": None}
    try:
        from structured_encoder import StructuredSemanticEncoder
        from psi_semiotics_core import PsiSemioticsEngine
        enc = StructuredSemanticEncoder(output_dim=1024)
        eng = PsiSemioticsEngine(dim=1024)
        v = enc.encode("test")
        f = eng.semantic_field_map(v)
        status["ready"] = len(f) > 0
    except Exception as e:
        status["error"] = str(e)
    return status


if __name__ == "__main__":
    print("=== Ψ-Semiotics 引擎预热 ===")
    s = preheat()
    print(f"\n状态: {'✅ 就绪' if s['preloaded'] else '❌ 失败'}")
    print(f"延迟: {s['latency_ms']}ms")
    print(f"组件: {s['components']}")
    if s.get('self_check'):
        print(f"自检: {s['self_check']['top_symbols']}")
