"""
LAAP 动态工具加载器 — 按任务类型按需加载工具
============================================

原理：
  用户说"帮我修bug" → 分类器 → coding工具集(5个)
  用户说"打开浏览器" → 分类器 → browser工具集(3个)
  用户说"查文件" → 分类器 → file工具集(4个)
  → 只加载需要的工具 schema，其他不进上下文
"""

import re
from typing import List, Dict, Set

# ── 工具分类 ───────────────────────────────────────────────

TOOL_CATEGORIES = {
    "coding": {
        "tools": ["terminal", "file_read", "file_write", "glob", "grep"],
        "keywords": ["写代码", "修bug", "实现", "fix", "bug", "implement", "重构",
                     "代码", "函数", "class", "调试", "test", "测试", "编译",
                     "python", "rust", "javascript", "html", "css"],
        "description": "代码编写、调试、测试"
    },
    "file_ops": {
        "tools": ["file_read", "file_write", "glob", "grep", "search_files"],
        "keywords": ["读文件", "写文件", "创建", "删除", "复制", "移动",
                     "找文件", "搜索", "目录", "文件夹", "重命名",
                     "read", "write", "create", "delete", "find"],
        "description": "文件读写、搜索、管理"
    },
    "browser": {
        "tools": ["browser_navigate", "browser_click", "browser_type",
                  "browser_snapshot", "browser_scroll"],
        "keywords": ["打开网页", "浏览器", "网页", "网站", "搜索",
                     "百度", "google", "chrome", "url", "http",
                     "browse", "web", "page", "上网"],
        "description": "浏览器操作、网页访问"
    },
    "research": {
        "tools": ["web_search", "web_extract", "browser_navigate",
                  "arxiv_search", "session_search"],
        "keywords": ["搜索", "查资料", "研究", "论文", "调研",
                     "what is", "how to", "search", "research",
                     "查一下", "找资料", "知识", "了解"],
        "description": "信息搜索、资料查询"
    },
    "system": {
        "tools": ["terminal", "process"],
        "keywords": ["系统", "进程", "端口", "网络", "安装",
                     "system", "process", "port", "network", "install",
                     "配置", "环境", "服务", "server", "启动"],
        "description": "系统管理、进程控制"
    },
    "cua": {
        "tools": ["scan_desktop", "click_element"],
        "keywords": ["桌面", "窗口", "点击", "打开软件", "启动程序",
                     "cua", "屏幕", "界面", "操作电脑",
                     "desktop", "click", "window", "app"],
        "description": "桌面操控、窗口管理"
    },
}

# ── 默认最小工具集（当无法分类时） ──

MINIMAL_TOOLS = ["terminal", "file_read", "file_write"]

ALL_TOOLS = set()
for cat in TOOL_CATEGORIES.values():
    ALL_TOOLS.update(cat["tools"])


# ── 任务分类器 ─────────────────────────────────────────────

class TaskClassifier:
    """分析任务，返回需要的工具分类。"""

    def __init__(self):
        pass

    def classify(self, task: str) -> List[str]:
        """分析任务，返回匹配的分类名称列表。"""
        task_lower = task.lower()
        matched = []

        # 逐个分类匹配关键词
        for name, cat in TOOL_CATEGORIES.items():
            score = 0
            for kw in cat["keywords"]:
                if kw.lower() in task_lower:
                    score += 1
            if score > 0:
                matched.append((name, score))

        # 按匹配度排序
        matched.sort(key=lambda x: -x[1])

        # 如果没有匹配，返回默认
        if not matched:
            return ["coding"]  # 默认当作编码任务

        return [m[0] for m in matched]

    def get_tools(self, task: str) -> List[str]:
        """根据任务返回需要的工具列表。"""
        categories = self.classify(task)
        tools = set()

        for cat_name in categories:
            cat = TOOL_CATEGORIES.get(cat_name)
            if cat:
                tools.update(cat["tools"])

        # 至少包含最小工具集
        if len(tools) < 3:
            tools.update(MINIMAL_TOOLS)

        return list(tools)

    def get_tool_names(self, task: str) -> str:
        """返回人类可读的工具列表描述。"""
        categories = self.classify(task)
        if not categories:
            return "terminal, file_read, file_write (默认)"

        descs = [f"[{c}] {TOOL_CATEGORIES[c]['description']}" 
                for c in categories if c in TOOL_CATEGORIES]
        tools = self.get_tools(task)
        return f"分类: {', '.join(descs)}\n工具: {', '.join(tools)} ({len(tools)}个)"

    def hermes_toolsets(self, task: str) -> Dict[str, bool]:
        """返回 Hermes toolsets 的启用/禁用字典。"""
        categories = self.classify(task)
        toolsets = {
            "hermes-cli": True,     # 核心工具集，始终启用
            "glm-free": False,      # 默认禁用
            "image_gen": False,     # 默认禁用
            "video_gen": False,     # 默认禁用
        }
        return toolsets


# ── 测试 ──────────────────────────────────────────────────

if __name__ == "__main__":
    classifier = TaskClassifier()

    tests = [
        "帮我修一下 login.py 的 bug",
        "查一下 Python 的 list 用法",
        "打开百度搜索 LAAP",
        "帮我看看系统端口占用",
        "写一个贪吃蛇游戏",
        "扫描桌面窗口",
        "今天天气怎么样",
    ]

    print(f"{'='*60}")
    print(f"  LAAP 动态工具加载器 — 测试")
    print(f"{'='*60}")
    for task in tests:
        tools = classifier.get_tools(task)
        print(f"\n📝 {task}")
        print(f"  {classifier.get_tool_names(task)}")
        print(f"  工具数: {len(tools)} (全量: {len(ALL_TOOLS)})")
        print(f"  省: {(1-len(tools)/len(ALL_TOOLS))*100:.0f}%")
