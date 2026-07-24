"""
Quantum Trajectory Database Builder — 推理轨迹数据库构建器
============================================================
把 LAAP文档 + arXiv论文 → 量子推理轨迹 → 存入知识矩阵

每条轨迹:
  start_state: 问题编码(1024D)
  path_states: [s1, s2, ..., sK]  (K步推理状态)
  end_state: 答案编码(1024D)
  metadata: {概念, 来源, 推理类型}

检索:
  新问题 → 编码 → 余弦相似度找最近start_state → 复用该trajectory → 微调 → 输出

速度: ~0.5ms (一次矩阵乘)
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, json, time, re
import numpy as np
from typing import Dict, List, Optional, Tuple
from write_utils import atomic_write_json

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
_STATE_DIR = os.path.join(_DIR, "state")
_TRAJ_PATH = os.path.join(_STATE_DIR, "quantum_trajectories.npz")
_TRAJ_INDEX = os.path.join(_STATE_DIR, "trajectory_index.json")


class QuantumTrajectoryDB:
    """量子推理轨迹数据库"""

    def __init__(self):
        self._encoder = None
        self._trajectories = []      # List[Dict]
        self._start_states = None    # (N, 1024) 起点矩阵
        self._end_states = None      # (N, 1024) 终点矩阵
        self._loaded = False

    def _lazy_encoder(self):
        if self._encoder is None:
            import sys; sys.path.insert(0, _DIR)
            from v7_encoder import get_encoder
            self._encoder = get_encoder(1024)

    def build_from_qa(self, qa_pairs: List[Dict], reasoning_steps: int = 5):
        """
        从QA对构建推理轨迹

        Args:
            qa_pairs: [{"question": str, "answer": str, "concept": str, ...}]
            reasoning_steps: 每条轨迹的中间步数

        算法:
          每个QA对生成一个量子推理轨迹:
            start = encode(question)
            end = encode(answer)
            path = [start, interpolate(start→end, k/reasoning_steps), ..., end]
        """
        self._lazy_encoder()
        t0 = time.time()

        trajectories = []
        start_states = []
        end_states = []

        for i, qa in enumerate(qa_pairs):
            q = qa.get("question", "")
            a = qa.get("answer", "")[:500]
            if not q or not a:
                continue

            # 编码起点和终点
            q_vec = self._encoder.encode(q)
            q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

            a_vec = self._encoder.encode(a)
            a_vec = a_vec / (np.linalg.norm(a_vec) + 1e-10)

            # 生成中间推理步骤 (线性插值 + 噪声)
            path_states = []
            for step in range(reasoning_steps + 1):
                alpha = step / reasoning_steps
                # 球面线性插值
                # 先做线性插值
                interp = (1 - alpha) * q_vec + alpha * a_vec
                # 加递减噪声模拟推理震荡
                noise = np.random.randn(1024).astype(np.float32) * 0.03 * (1 - alpha)
                interp = interp + noise
                # 归一化
                interp = interp / (np.linalg.norm(interp) + 1e-10)
                path_states.append(interp)

            trajectory = {
                "id": i,
                "question": q,
                "answer": a[:200],
                "concept": qa.get("concept", ""),
                "source": qa.get("source", ""),
                "start_state": q_vec,
                "path_states": path_states,
                "end_state": a_vec,
                "steps": reasoning_steps,
            }

            trajectories.append(trajectory)
            start_states.append(q_vec)
            end_states.append(a_vec)

        # 构建矩阵
        self._trajectories = trajectories
        if start_states:
            self._start_states = np.vstack(start_states).astype(np.float32)
            self._end_states = np.vstack(end_states).astype(np.float32)
        else:
            self._start_states = np.zeros((0, 1024), dtype=np.float32)
            self._end_states = np.zeros((0, 1024), dtype=np.float32)

        # 保存
        os.makedirs(_STATE_DIR, exist_ok=True)
        np.savez_compressed(
            _TRAJ_PATH,
            start_states=self._start_states,
            end_states=self._end_states,
        )
        # 保存轨迹元数据
        index_data = []
        for t in trajectories:
            index_data.append({
                "id": t["id"],
                "question": t["question"],
                "answer": t["answer"][:100],
                "concept": t["concept"],
                "source": t["source"],
                "steps": t["steps"],
            })
        atomic_write_json(index_data, _TRAJ_INDEX, indent=2)

        self._loaded = True
        dt = (time.time() - t0) * 1000
        logger.info(f"  轨迹数据库: {len(trajectories)}条轨迹, 构建耗时{dt:.0f}ms")
        logger.info(f"  保存: {_TRAJ_PATH} ({os.path.getsize(_TRAJ_PATH)//1024}KB)")
    def search(self, question: str, top_k: int = 3) -> List[Dict]:
        """
        搜索最匹配的推理轨迹

        算法: 编码问题 → 与所有起点做余弦相似 → 返回topK轨迹
        """
        if not self._loaded or self._start_states is None or len(self._start_states) == 0:
            return []

        self._lazy_encoder()
        q_vec = self._encoder.encode(question)
        q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

        # 矩阵乘: (N,1024) @ (1024,) → (N,) 余弦相似度
        scores = self._start_states @ q_vec
        top_indices = np.argsort(-scores)[:top_k]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < 0.2:
                continue
            if idx < len(self._trajectories):
                traj = self._trajectories[idx]
                results.append({
                    "trajectory": traj,
                    "match_score": score,
                    "question": traj["question"],
                    "concept": traj["concept"],
                    "source": traj["source"],
                })

        return results

    def reason_with_trajectory(self, question: str,
                                top_trajectory: Dict) -> Tuple[np.ndarray, List[str]]:
        self._lazy_encoder()
        traj = top_trajectory.get("trajectory", {})
        
        q_vec = self._encoder.encode(question)
        q_vec = q_vec / (np.linalg.norm(q_vec) + 1e-10)

        # 如果没有预存路径，直接从起点到终点插值生成
        if "path_states" not in traj or not traj.get("path_states"):
            # 用 start_state 和 end_state 动态生成路径
            start = traj.get("start_state")
            end = traj.get("end_state")
            if start is not None and end is not None:
                # 球面插值生成 5 步
                steps = 5
                path = []
                for s in range(steps + 1):
                    alpha = s / steps
                    interp = (1 - alpha) * np.array(start) + alpha * np.array(end)
                    noise = np.random.randn(1024).astype(np.float32) * 0.02 * (1 - alpha)
                    interp = interp + noise
                    interp = interp / (np.linalg.norm(interp) + 1e-10)
                    path.append(interp)
            else:
                return q_vec, []
        else:
            path = traj["path_states"]

        if not path or len(path) < 2:
            return q_vec, []

        current = q_vec.copy()
        reasoning_chain = []

        for step_idx, waypoint in enumerate(path):
            waypoint = np.array(waypoint, dtype=np.float32)
            alpha = 0.8
            next_state = alpha * waypoint + (1 - alpha) * current
            n = float(np.linalg.norm(next_state))
            if n > 0:
                next_state = next_state / n

            if step_idx > 0:
                delta = float(np.linalg.norm(next_state - current))
                if delta > 0.01:
                    reasoning_chain.append(
                        f"步骤{step_idx}: 状态变化{delta:.3f}，概念={traj.get('concept','')}"
                    )

            current = next_state

        return current, reasoning_chain

    def expand_to_text(self, final_state: np.ndarray,
                        reasoning_chain: List[str],
                        kb_context: List[str],
                        max_chars: int = 2000) -> str:
        """把推理轨迹展开为结构化文本"""
        self._lazy_encoder()

        sections = []
        sections.append("## 量子推理结果\n")

        # 推理链
        if reasoning_chain:
            sections.append("### 推理过程\n")
            for rc in reasoning_chain:
                sections.append(f"- {rc}")
            sections.append("")

        # 知识上下文
        if kb_context:
            sections.append("### 相关知识\n")
            for i, kc in enumerate(kb_context[:3]):
                clean = re.sub(r'[#=\n]{2,}', ' ', kc)[:200]
                sections.append(f"{i+1}. {clean}\n")

        # 最终状态匹配 — 找最相似的知识条目作为答案
        if hasattr(self, '_end_states') and self._end_states is not None and len(self._end_states) > 0:
            scores = self._end_states @ final_state
            best_idx = int(np.argmax(scores))
            if best_idx < len(self._trajectories):
                answer = self._trajectories[best_idx]["answer"]
                sections.append(f"### 答案\n{answer[:800]}")
                sections.append(f"\n*(匹配:{float(scores[best_idx]):.3f})*")

        return "\n".join(sections)[:max_chars]

    def stats(self) -> Dict:
        return {
            "total_trajectories": len(self._trajectories),
            "loaded": self._loaded,
            "start_states_shape": self._start_states.shape if self._start_states is not None else None,
        }


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Quantum Trajectory DB 自测")
    logger.info("=" * 60)
    qa_path = os.path.join(_STATE_DIR, "reasoning_trajectories.json")
    if os.path.exists(qa_path):
        with open(qa_path, 'r', encoding='utf-8') as f:
            qa_pairs = json.load(f)
        logger.info(f"  加载QA对: {len(qa_pairs)}条")
    else:
        qa_pairs = []
        logger.info("  无QA对，用示例")
        qa_pairs = [
            {"question": "量子核是什么？", "answer": "量子核是一种纯NumPy实现的语义特征映射方法，在16384维空间中编码中英日韩跨语言语义关系。", "concept": "量子核"},
        ]

    # 构建轨迹数据库
    db = QuantumTrajectoryDB()
    db.build_from_qa(qa_pairs, reasoning_steps=5)
    logger.info(f"\n  数据库: {db.stats()}")
    logger.info("\n=== 测试检索 ===")
    test_qs = [
        "量子核是怎么工作的？",
        "LAAP架构如何实现零LLM",
        "PSI认知循环包含什么",
    ]

    for q in test_qs:
        results = db.search(q, top_k=2)
        logger.info(f"\n  问题: {q}")
        if results:
            for i, r in enumerate(results):
                logger.info(f"    匹配{i+1}: [{r['concept']}] {r['question'][:60]} (得分:{r['match_score']:.3f})")
                final, chain = db.reason_with_trajectory(q, r)
                if len(chain) > 0:
                    logger.info(f"      推理: {len(chain)}步, 最终链: {' → '.join(chain[-2:])}")
        else:
            logger.info(f"    (无匹配)")