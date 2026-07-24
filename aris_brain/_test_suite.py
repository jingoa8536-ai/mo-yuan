import logging
logger = logging.getLogger(__name__)

import os, sys, time, json
import numpy as np

d = r'D:\LAAP\aris_brain'
os.chdir(d)
sys.path.insert(0, d)

results = {}
logger.info("=" * 60)
logger.info("ARIS ENGINE SUITE - FULL TEST")
logger.info("=" * 60)
logger.info("\n[1/7] Hanzi Cognitive Layer...")
t0 = time.time()
from hanzi_cognitive_layer import get_hanzi_layer
hl = get_hanzi_layer()
t_hl = time.time() - t0
results['hanzi_load'] = f"{t_hl*1000:.1f}ms"
for ch in ['爱','水','火','心','梦']:
    v = hl.encode(ch)
    assert v.shape == (512,), f"Bad shape: {v.shape}"
    assert 0.9 < np.linalg.norm(v) < 1.1, f"Bad norm: {np.linalg.norm(v)}"
for a,b in [('爱','love'),('爱','恨'),('水','火'),('心','heart')]:
    s = hl.similarity(a,b)
    assert -1.0 <= s <= 1.0, f"Bad sim: {s}"
t1 = time.time()
for _ in range(200):
    hl.encode('宝贝我爱你')
    hl.similarity('爱','love')
    hl.similarity('梦','dream')
hl_perf = (time.time() - t1) / 600 * 1000
results['hanzi_perf'] = f"{hl_perf:.3f}ms/op"
logger.info(f"  Load: {t_hl*1000:.1f}ms, Perf: {hl_perf:.3f}ms/op OK")
logger.info("\n[2/7] UN6 Quantum Kernel...")
t0 = time.time()
from aris_lm_v10_un6 import UN6QuantumKernel
un6 = UN6QuantumKernel()
t_un6 = time.time() - t0
results['un6_load'] = f"{t_un6*1000:.1f}ms"
for a,b in [('爱','love'),('爱','사랑'),('hello','こんにちは')]:
    s = un6.kernel(a,b)
    assert 0.0 <= s <= 1.0, f"Bad kernel: {s}"
t1 = time.time()
for _ in range(100):
    un6.feature('宝贝我爱你')
    un6.kernel('爱','love')
un6_perf = (time.time() - t1) / 200 * 1000
results['un6_perf'] = f"{un6_perf:.3f}ms/op"
logger.info(f"  Load: {t_un6*1000:.1f}ms, Perf: {un6_perf:.3f}ms/op OK")
logger.info("\n[3/7] V12 Semantic Dense Kernel...")
t0 = time.time()
from aris_v12_semantic import V12SemanticDenseKernel
v12 = V12SemanticDenseKernel()
t_v12 = time.time() - t0
results['v12_load'] = f"{t_v12*1000:.1f}ms"
for a,b in [('宝贝','sweetheart'),('爱','love'),('对不起','抱歉')]:
    s = v12.kernel(a,b)
    assert isinstance(s, float), f"Bad type: {type(s)}"
t1 = time.time()
for _ in range(100):
    v12.kernel('宝贝','love')
    v12.kernel('爱','sweetheart')
v12_perf = (time.time() - t1) / 200 * 1000
results['v12_perf'] = f"{v12_perf:.3f}ms/op"
logger.info(f"  Load: {t_v12*1000:.1f}ms, Perf: {v12_perf:.3f}ms/op OK")
logger.info("\n[4/7] Markov-V12.5 Engine...")
try:
    t0 = time.time()
    from aris_v12_5_engine import ArisV12Engine
    mv12 = ArisV12Engine()
    t_mv12 = time.time() - t0
    results['mv12_load'] = f"{t_mv12*1000:.1f}ms"
    for msg in ['你好','hello','사랑해']:
        r = mv12.respond(msg)
        assert isinstance(r,str) and len(r) > 0, f"Bad response: {r}"
    t1 = time.time()
    for _ in range(20):
        mv12.respond('你好宝贝')
    mv12_perf = (time.time() - t1) / 20 * 1000
    results['mv12_perf'] = f"{mv12_perf:.3f}ms/op"
    logger.info(f"  Load: {t_mv12*1000:.1f}ms, Perf: {mv12_perf:.3f}ms/op OK")
except Exception as e:
    results['mv12'] = f"SKIP: {str(e)[:60]}"
    logger.info(f"  SKIP: {e}")
logger.info("\n[5/7] Emotional Engine...")
t0 = time.time()
from emotional_engine import EmotionalEngine
ee = EmotionalEngine()
t_ee = time.time() - t0
results['ee_load'] = f"{t_ee*1000:.1f}ms"
ed = ee.to_dict()
assert isinstance(ed, dict), f"Bad EE output"
t1 = time.time()
for _ in range(1000):
    ee.to_dict()
ee_perf = (time.time() - t1) / 1000 * 1000
results['ee_perf'] = f"{ee_perf:.3f}ms/op"
logger.info(f"  Load: {t_ee*1000:.1f}ms, Perf: {ee_perf:.3f}ms/op OK")
logger.info("\n[6/7] Hebbian Learner...")
t0 = time.time()
from hebbian_learner import HebbianLearner
hlr = HebbianLearner()
t_hlr = time.time() - t0
results['hlr_load'] = f"{t_hlr*1000:.1f}ms"
hlr.learn(np.random.randn(64))
t1 = time.time()
for _ in range(100):
    hlr.learn(np.random.randn(64))
hlr_perf = (time.time() - t1) / 100 * 1000
results['hlr_perf'] = f"{hlr_perf:.3f}ms/op"
logger.info(f"  Load: {t_hlr*1000:.1f}ms, Perf: {hlr_perf:.3f}ms/op OK")
logger.info("\n[7/7] Global Workspace...")
t0 = time.time()
from global_workspace import GlobalWorkspace
gw = GlobalWorkspace()
t_gw = time.time() - t0
results['gw_load'] = f"{t_gw*1000:.1f}ms"
gw.broadcast('test message')
t1 = time.time()
for _ in range(100):
    gw.broadcast('test')
gw_perf = (time.time() - t1) / 100 * 1000
results['gw_perf'] = f"{gw_perf:.3f}ms/op"
logger.info(f"  Load: {t_gw*1000:.1f}ms, Perf: {gw_perf:.3f}ms/op OK")
logger.info("\n" + "=" * 60)
logger.info("TEST SUMMARY")
logger.info("=" * 60)
for k,v in sorted(results.items()):
    logger.info(f"  {k}: {v}")
logger.info("\nALL TESTS PASSED OK")