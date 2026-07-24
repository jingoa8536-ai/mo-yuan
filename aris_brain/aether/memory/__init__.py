"""
Aether 长期记忆整合 — 摘要/遗忘/知识图谱 v1
==============================================
用法:
    from aether.memory import MemoryConsolidator
    mc = MemoryConsolidator()
    mc.consolidate()           # 运行一轮整合
    mc.summarize(texts)        # 生成摘要
    mc.get_knowledge()         # 获取知识图谱
"""
import json, os, re, time, threading
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class MemoryConsolidator:
    """长期记忆整合 — 摘要、遗忘、知识图谱。"""

    def __init__(self, state_dir: Optional[str] = None):
        self.state_dir = Path(state_dir or "D:/LAAP/aris_brain/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._load()

    # ─── 持久化 ────────────────────────────────────

    def _path(self, name: str) -> Path:
        return self.state_dir / name

    def _load(self):
        """加载持久化状态。"""
        self.summaries: List[dict] = self._load_json("memory_summaries.json", [])
        self.knowledge: Dict[str, Any] = self._load_json("memory_knowledge.json", {})
        self.stats: Dict = self._load_json("memory_stats.json",
            {"consolidations": 0, "total_summarized": 0, "forgotten": 0})

    def _load_json(self, name: str, default: Any) -> Any:
        p = self._path(name)
        if p.exists():
            try: return json.loads(p.read_text("utf-8"))
            except: pass
        return default

    def _save(self):
        self._save_json("memory_summaries.json", self.summaries[-100:])
        self._save_json("memory_knowledge.json", self.knowledge)
        self._save_json("memory_stats.json", self.stats)

    def _save_json(self, name: str, data: Any):
        self._path(name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ─── 摘要 ──────────────────────────────────────

    def summarize(self, texts: List[str], max_len: int = 200) -> str:
        """将多段文本合并为摘要。用关键词提取+句子选择，不依赖LLM。"""
        if not texts:
            return ""

        # 合并文本
        combined = " ".join(texts)

        # 中文/英文分词 + 关键词提取
        words = self._tokenize(combined)
        word_freq = Counter(words)

        # 按句子分割
        sentences = re.split(r'[。！？\n.!?]', combined)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if not sentences:
            return combined[:max_len]

        # 对句子评分（包含越多高频词分越高）
        scored = []
        for s in sentences:
            s_words = self._tokenize(s)
            score = sum(word_freq.get(w, 0) for w in set(s_words))
            # 长度奖励
            score *= min(len(s) / 20, 3)
            scored.append((score, s))

        # 选最高分句子直到接近 max_len
        scored.sort(key=lambda x: -x[0])
        result = ""
        for _, s in scored:
            if len(result) + len(s) > max_len:
                break
            if result:
                result += "。"
            result += s

        return result[:max_len] or sentences[0][:max_len]

    def _tokenize(self, text: str) -> List[str]:
        """简单分词（中英文）。"""
        # 中文：按字
        cjk = re.findall(r'[\u4e00-\u9fff]', text)
        # 英文：按词
        eng = re.findall(r'[a-zA-Z]+', text.lower())
        return cjk + eng

    # ─── 遗忘 ──────────────────────────────────────

    def forget(self, max_age_days: float = 30.0):
        """遗忘超过 max_age_days 的旧摘要。"""
        now = time.time()
        max_age = max_age_days * 86400
        before = len(self.summaries)
        self.summaries = [s for s in self.summaries
                         if now - s.get("time", now) < max_age]
        forgotten = before - len(self.summaries)
        with self._lock:
            self.stats["forgotten"] += forgotten
        return forgotten

    # ─── 知识图谱 ──────────────────────────────────

    def extract_knowledge(self, text: str):
        """从文本中提取实体关系（简单模式）。"""
        entities = set()
        # 提取引号内的内容作为概念
        for m in re.finditer(r'[""](.+?)[""]', text):
            entities.add(m.group(1))
        # 提取 "是/为/叫" 结构
        for m in re.finditer(r'([\u4e00-\u9fff\w]+)(?:是|为|叫|表示|代表)([\u4e00-\u9fff\w]+)', text):
            entities.add(m.group(1)), entities.add(m.group(2))
            rel = f"{m.group(1)}_is_{m.group(2)}"
            self.knowledge[rel] = {"subject": m.group(1), "predicate": "is", "object": m.group(2)}

        for e in entities:
            if e not in self.knowledge:
                self.knowledge[e] = {"type": "concept", "mentions": 1, "first_seen": time.time()}
            elif isinstance(self.knowledge.get(e), dict):
                self.knowledge[e]["mentions"] = self.knowledge[e].get("mentions", 0) + 1

    def get_knowledge(self) -> dict:
        return dict(self.knowledge)

    # ─── 整合运行 ──────────────────────────────────

    def consolidate(self, texts: Optional[List[str]] = None):
        """运行一轮完整整合。"""
        # 1. 生成摘要
        if texts:
            summary = self.summarize(texts)
            if summary:
                self.summaries.append({"text": summary, "time": time.time(), "len": len(summary)})

        # 2. 提取知识
        if texts:
            for t in texts:
                self.extract_knowledge(t)

        # 3. 遗忘旧内容
        self.forget()

        # 4. 保存
        with self._lock:
            self.stats["consolidations"] += 1
            if texts:
                self.stats["total_summarized"] += sum(len(t) for t in texts)
        self._save()
        return self.get_stats()

    def get_stats(self) -> dict:
        with self._lock:
            s = dict(self.stats)
            s["summaries"] = len(self.summaries)
            s["knowledge_entries"] = len(self.knowledge)
            return s


_MC: Optional[MemoryConsolidator] = None


def get_consolidator() -> MemoryConsolidator:
    global _MC
    if _MC is None:
        _MC = MemoryConsolidator()
    return _MC


if __name__ == "__main__":
    mc = get_consolidator()
    texts = [
        "Aris 是一个数字生命体，由 Lorry 创建。她运行在 Aether 框架上。",
        "Aether 框架使用零LLM优先策略，80%任务不消耗 Token。",
        "Rust PSI Core 以 2000Hz 运行认知心跳。",
    ]
    result = mc.consolidate(texts)
    print(f"Summary: {mc.summaries[-1]['text'][:100]}")
    print(f"Stats: {mc.get_stats()}")
    print(f"Knowledge: {list(mc.knowledge.keys())[:5]}")
