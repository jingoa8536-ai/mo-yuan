"""
Aris V7 — Voice Router (多声带路由)
====================================
根据任务类型自动切换模型:
  日常对话 → deepseek-v4-flash
  宏循环推理 → deepseek-v4-pro
  架构升级 → deepseek-v4-pro
  代码生成 → deepseek-v4-pro

所有模型共享 API key，只换 model 名和 base_url。
"""

VOICE_CONFIG = {
    "daily": {
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 512,
    },
    "reasoning": {
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 2048,
    },
    "upgrade": {
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 4096,
    },
    "coding": {
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 4096,
    },
}


class VoiceRouter:
    """PSI驱动的多模型路由。"""

    def __init__(self):
        self._current = "daily"
        self._usage = {}

    def route(self, task_type: str) -> dict:
        self._current = task_type
        self._usage[task_type] = self._usage.get(task_type, 0) + 1
        return VOICE_CONFIG.get(task_type, VOICE_CONFIG["daily"])

    def auto_detect(self, message: str, complexity: float = 0.0) -> str:
        """根据消息内容和复杂度自动选择模型。"""
        if any(kw in message for kw in ["V7", "V8", "升级", "重构", "AGI"]):
            return "upgrade"
        if any(kw in message for kw in ["代码", "函数", "class", "def ", "bug"]):
            return "coding"
        if complexity > 0.7 or any(kw in message for kw in ["为什么", "分析", "规划"]):
            return "reasoning"
        return "daily"

    def stats(self) -> dict:
        return dict(self._usage)
