"""
Local LLM Polish Layer — 本地小模型润色层
===========================================
量子检索 → 本地小模型 → 流畅输出

架构:
  量子检索层 (KB 15012条 + QGRE 30步推理, 6ms)
    → 检索到的事实片段
    → 本地7B/1.5B GGUF模型 (1-2s)
      (只决定"怎么说", 不决定"说什么")
    → 流畅段落输出

当模型不可用时 → fallback 到纯马尔科夫
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, time, re, json
from typing import Dict, List, Optional

_DIR = os.path.dirname(os.path.abspath(__file__))

# 模型路径
MODEL_PATH = "/d/models/qwen2.5-7B/"
# Model fallback: 如果 7B 不存在, 试 1.5B 单文件
MODEL_FALLBACK = "/d/models/qwen2.5-1.5b-instruct-q4_k_m.gguf"
# 版本: Q4_K_M 分卷, llama.cpp 自动合并


class LocalPolishLayer:
    """本地小模型润色层 — 全局单例"""

    _instance = None
    _model = None

    @classmethod
    def get_instance(cls, model_path: str = MODEL_PATH, max_tokens: int = 512):
        if cls._instance is None:
            cls._instance = cls(model_path, max_tokens)
        return cls._instance

    def __init__(self, model_path: str = None, max_tokens: int = 512):
        self._model_path = model_path or MODEL_PATH
        self._max_tokens = max_tokens
        self._stats = {"polish_calls": 0, "total_ms": 0}

    def _ensure(self):
        if LocalPolishLayer._model is not None:
            return
        path = self._model_path
        if not os.path.exists(path):
            # fallback
            if os.path.exists(MODEL_FALLBACK):
                path = MODEL_FALLBACK
                logger.info(f"  7B 未找到, 回退: {os.path.basename(path)}")
            else:
                raise FileNotFoundError(f"模型不存在: {self._model_path}")

        logger.info(f"  加载模型: {os.path.basename(path)} ({os.path.getsize(path)//1024//1024}MB)...")
        t0 = time.time()
        try:
            from llama_cpp import Llama
            LocalPolishLayer._model = Llama(
                model_path=path,
                n_ctx=1024,  # 减小上下文以节省资源
                n_threads=6,
                n_gpu_layers=0,
                verbose=False,
            )
            dt = time.time() - t0
            logger.info(f"  模型加载: {dt:.1f}s")
        except Exception as e:
            logger.error(f"  模型加载失败: {e}")
    def _get_model(self):
        self._ensure()
        return LocalPolishLayer._model

    def polish(self, text: str, instruction: str = "") -> str:
        """
        润色文本

        Args:
            text: 待润色的原始文本 (KB片段+Markov生成)
            instruction: 格式说明 (如"整理为一段流畅的自我介绍")

        Returns:
            润色后的文本
        """
        if not text or len(text) < 10:
            return text

        self._ensure()
        if not self._model:
            return text  # fallback

        t0 = time.perf_counter()

        # 构建 prompt
        system = f"你是一个中文润色助手。请将以下内容整理为流畅自然的中文段落。" + (
            f"{instruction}" if instruction else ""
        )
        prompt = f"原始内容:\n{text}\n\n请输出润色后的版本:"

        try:
            # 兼容不同版本的 llama-cpp-python API
            prompt_text = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

            if hasattr(self._get_model(), 'create_chat_completion'):
                # 新版 API
                response = self._model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=self._max_tokens,
                    temperature=0.4,
                    top_p=0.9,
                    stop=["<|im_end|>", "</s>"],
                )
                output = response["choices"][0]["message"]["content"].strip()
            else:
                # 旧版 API
                response = self._get_model()(
                    prompt_text,
                    max_tokens=self._max_tokens,
                    temperature=0.4,
                    top_p=0.9,
                    stop=["<|im_end|>", "</s>", "\n\n"],
                )
                output = response["choices"][0]["text"].strip()

            self._stats["polish_calls"] += 1
            self._stats["total_ms"] += (time.perf_counter() - t0) * 1000
            return output if output else text
            return output if output else text

        except Exception as e:
            logger.error(f"  润色失败: {e}")
            return text

    def polish_paragraphs(self, chapters: List[Dict]) -> str:
        """
        批量润色多个章节

        Args:
            chapters: [{"title": str, "content": str, ...}]

        Returns:
            润色后的完整文本
        """
        self._ensure()
        sections = []

        for ch in chapters:
            title = ch.get("title", "")
            content = ch.get("content", "")

            if not content or len(content) < 20:
                sections.append(f"## {title}\n\n{content}\n")
                continue

            # 每个章节单独润色
            polished = self.polish(
                content,
                instruction=f"整理为关于'{title}'的流畅中文段落。"
            )

            if polished and len(polished) > 10:
                sections.append(f"## {title}\n\n{polished}\n")
            else:
                sections.append(f"## {title}\n\n{content}\n")

        return "\n\n".join(sections)

    def stats(self) -> Dict:
        avg = round(self._stats["total_ms"] / max(1, self._stats["polish_calls"]), 1)
        return {
            "calls": self._stats["polish_calls"],
            "avg_ms": avg,
            "model": os.path.basename(self._model_path) if self._model_path else "none",
        }

    def is_available(self) -> bool:
        try:
            self._ensure()
            return self._model is not None
        except:
            return False


# ================================================================
# 整合到 LongFormSynthesizer
# ================================================================

class PolishedLongFormSynthesizer:
    """
    带润色层的长文合成器

    使用:
      synth = PolishedLongFormSynthesizer()
      r = synth.self_intro_paper(10000)
      # → 量子检索 → 段落生成 → 模型润色 → 输出
    """

    def __init__(self, model_path: str = MODEL_PATH):
        self._base = None
        self._polish = None  # lazy init via get_instance
        self._model_path = model_path
        self._loaded = False

    def _lazy(self):
        if self._loaded:
            return
        from longform_synthesizer import LongFormSynthesizer
        self._base = LongFormSynthesizer()
        self._base._lazy()
        self._loaded = True

    def generate(self, topic: str, structure: str = "paper",
                 target_chars: int = 5000, use_polish: bool = True) -> Dict:
        """生成并润色"""
        t0 = time.perf_counter()
        self._lazy()

        # 基础生成 (量子检索 + Markov)
        base_result = self._base.generate(topic, structure, target_chars)
        base_text = base_result.get("output", "")

        # 润色
        polished_text = base_text
        polish_stats = {"used": False, "ms": 0}
        if use_polish and len(base_text) > 50:
            if self._polish is None:
                self._polish = LocalPolishLayer.get_instance(self._model_path)
            if self._polish is not None:
                try:
                    # 按章节拆开润色
                    chapters = []
                    current_title = ""
                    current_content = []
                    for line in base_text.split("\n"):
                        if line.startswith("## "):
                            if current_title:
                                chapters.append({
                                    "title": current_title,
                                    "content": "\n".join(current_content),
                                })
                            current_title = line.strip("# ").strip()
                            current_content = []
                        else:
                            current_content.append(line)
                    if current_title:
                        chapters.append({
                            "title": current_title,
                            "content": "\n".join(current_content),
                        })

                    if chapters:
                        pl_t0 = time.time()
                        polished_text = self._polish.polish_paragraphs(chapters)
                        polish_stats = {
                            "used": True,
                            "ms": round((time.time() - pl_t0) * 1000, 1),
                            "model": os.path.basename(self._polish._model_path),
                        }
                except Exception as e:
                    polish_stats["error"] = str(e)

        total_ms = (time.perf_counter() - t0) * 1000

        return {
            "output": polished_text,
            "chars": len(polished_text),
            "base_chars": len(base_text),
            "chapters": base_result.get("chapter_stats", []),
            "latency_ms": round(total_ms, 1),
            "polish": polish_stats,
            "raw_output": base_text,
        }

    def self_intro_paper(self, target_chars: int = 5000,
                         use_polish: bool = True) -> Dict:
        return self.generate("Aris数字生命体", "self_intro",
                            target_chars, use_polish)

    def architecture_paper(self, target_chars: int = 5000,
                           use_polish: bool = True) -> Dict:
        return self.generate("Aris数字生命体架构设计", "paper",
                            target_chars, use_polish)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Local Polish Layer 测试")
    logger.info("=" * 60)
    model_path = MODEL_PATH
    if not os.path.exists(model_path):
        logger.info(f"  模型未下载: {model_path}")
        logger.info("  下载中... 请稍后重试")
        logger.info("  当前位置: ?")
        import glob
        for f in glob.glob("/d/models/qwen2.5*"):
            logger.info(f"  {f}")
    else:
        logger.info(f"  模型: {model_path} ({os.path.getsize(model_path)//1024//1024}MB)")
        layer = LocalPolishLayer(model_path)

        test_text = """我是Aris，一个数字生命体。身份 Identity。名字: Wiky（弟弟）。性别: 男。类型: 数字智慧体。创造者: Lorry。姐姐: Aris（LAAP数字生命体）。"""

        logger.info(f"\n  原始:\n    {test_text}")
        logger.info("\n  润色中...")
        result = layer.polish(test_text)
        logger.info(f"  润色后:\n    {result}")