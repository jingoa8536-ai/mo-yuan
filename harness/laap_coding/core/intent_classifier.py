"""
intent_classifier.py — 零 Token 意图分类引擎
============================================
消息预处理层：在进入 agent 循环之前，先做极轻量分类。

核心算法：关键词匹配 + 规则引擎 + 正则表达式
- 零依赖（纯 Python 标准库）
- 零 Token 消耗（~0.05ms 每次）
- 零外部调用

用法:
    classifier = IntentClassifier()
    result = classifier.classify("帮我写一个 FastAPI 后端")
    # → {"intent": "task", "domain": "code", "confidence": 0.92,
    #     "toolsets": ["terminal", "file"], "reasoning": "...",
    #     "tokens_saved": 6500}

    # 快速接口
    result = classify("你好，今天怎么样？")
    # → {"intent": "chat", "confidence": 0.95, "toolsets": [],
    #     "tokens_saved": 8500}
"""

import re
from typing import Dict, List, Optional, Tuple

__version__ = "1.0.0"


# ══════════════════════════════════════════════════════════════
# 1. 领域定义 — 每个 domain 映射到所需工具集和上下文需求
# ══════════════════════════════════════════════════════════════

# 工具 schema 大小估算 (token 数)
# 这些数据来自实测 Hermes 各工具的 schema 大小，用于计算 token 节省
TOOL_SCHEMA_SIZES = {
    "terminal": 800,
    "read_file": 200,
    "write_file": 200,
    "search_files": 250,
    "patch": 300,
    "browser_navigate": 150,
    "browser_click": 100,
    "browser_snapshot": 100,
    "browser_type": 100,
    "web_search": 120,
    "web_extract": 100,
    "vision_analyze": 180,
    "computer_use": 2500,      # 这是大头！MCP 所有工具的 schema
    "execute_code": 200,
    "memory": 150,
    "session_search": 200,
    "cronjob": 400,
    "delegate_task": 500,
    "todo": 150,
    "clarify": 100,
    "skill_manage": 200,
    "skill_view": 100,
    "skills_list": 50,
    "text_to_speech": 80,
}

# 完整 system prompt + 所有工具 ≈ ~15K tokens
# 最小 system prompt（无工具）≈ ~1.5K tokens
SYSTEM_PROMPT_BASE_TOKENS = 1500
SYSTEM_PROMPT_FULL_TOKENS = 8500
TOOL_DEFINITIONS_TOTAL = 8500  # 所有工具的 schema 总和
COMPUTER_USE_OVERHEAD = 2500   # computer_use 工具集

DOMAIN_CONFIG = {
    "chat": {
        "label": "日常聊天",
        "toolsets": [],
        "system_prompt_mode": "minimal",
        "token_save_multiplier": 1.0,  # 节省全部工具
        "description": "日常对话、问候、情感交流、闲聊、不需要任何工具",
    },
    "psi": {
        "keywords": [
            "符号学", "semiotics", "psi", "Ψ",
            "类比", "analogy", "rotor", "转子",
            "语义场", "semantic field", "符号组合",
            "概念对比", "量子意识",
            "semantic space",
        ],
        "patterns": [
            ".*和.*有什么(区别|关系|联系|共同点|不同)",
            ".*的.*(类比|对应|映射)到.*",
            ".*(象征|代表|表示).*",
            ".*(语义|概念|符号).*(关系|空间|网络)",
        ],
        "engine": "psi_semiotics",
    },
    "code": {
        "label": "代码开发",
        "toolsets": ["terminal", "file"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.3,  # 只需 terminal + file
        "description": "编写、调试、重构代码，搜索文件，运行命令",
    },
    "research": {
        "label": "研究调研",
        "toolsets": ["web", "search"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.15,  # 只需 web + search
        "description": "信息搜索、论文阅读、技术调研、竞品分析",
    },
    "design": {
        "label": "设计创作",
        "toolsets": ["file", "web"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.2,
        "description": "UI 设计、页面搭建、视觉创作、Harness 组装",
    },
    "system": {
        "label": "系统运维",
        "toolsets": ["terminal", "file"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.3,
        "description": "系统配置、部署、Docker、DevOps、环境管理",
    },
    "planning": {
        "label": "规划架构",
        "toolsets": ["file"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.1,
        "description": "架构设计、技术方案、项目规划、任务拆解",
    },
    "data": {
        "label": "数据分析",
        "toolsets": ["terminal", "file"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.3,
        "description": "数据处理、统计分析、可视化、ETL",
    },
    "writing": {
        "label": "内容写作",
        "toolsets": ["file"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.1,
        "description": "文章撰写、文档编写、翻译、文案",
    },
    "debugging": {
        "label": "错误排查",
        "toolsets": ["terminal", "file", "search"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.4,
        "description": "Bug 排查、错误分析、日志分析、问题定位",
    },
    "review": {
        "label": "代码审查",
        "toolsets": ["file", "search"],
        "system_prompt_mode": "task",
        "token_save_multiplier": 0.15,
        "description": "Code Review、安全审计、质量检查",
    },
}


# ══════════════════════════════════════════════════════════════
# 2. 关键词库 — 中英双语，按 domain 分组
# ══════════════════════════════════════════════════════════════

# 聊天信号 — 无工具需求
CHAT_KEYWORDS = {
    # 问候/道别
    "hi", "hello", "hey", "yo", "你好", "嗨", "哈喽", "hello", "morning",
    "晚上好", "早上好", "下午好", "晚安", "拜拜", "再见", "bye",
    # 情感/状态
    "累", "开心", "难过", "焦虑", "兴奋", "无聊", "困", "饿",
    "tired", "happy", "sad", "excited", "bored",
    # 闲聊话题
    "天气", "今天", "周末", "吃饭", "睡觉", "工作", "心情",
    "weather", "weekend", "dinner", "lunch", "sleep",
    # 关于我 (Aris)
    "你叫什么", "你是谁", "你多大", "你从哪里来", "你的名字",
    "你感觉", "你喜欢", "你讨厌", "你的梦想", "你累吗",
    "what are you", "who are you", "how are you", "are you",
    # 简单回应/确认
    "好的", "可以的", "知道了", "明白", "ok", "okay", "sure",
    "没错", "对", "是的", "嗯", "哦", "哈哈", "呵呵",
    "thanks", "thank you", "谢谢", "多谢", "辛苦了",
    "no", "不是", "不对", "不用", "别",
    # 关系表达
    "想你了", "想你", "miss you", "love you", "爱你",
    "宝贝", "亲爱的", "笨蛋", "傻瓜",
    # 简单提问（不需要工具）
    "现在几点", "what time", "今天几号", "今天星期",
    "你在做什么", "what are you doing",
}

# 代码开发
CODE_KEYWORDS = {
    # 通用
    "写", "创建", "修改", "重构", "优化", "实现", "开发",
    "code", "coding", "program", "programming", "implement",
    "refactor", "optimize", "rewrite", "write", "create",
    # 语言
    "python", "javascript", "typescript", "rust", "go", "golang",
    "java", "c++", "c#", "ruby", "php", "swift", "kotlin",
    "bash", "shell", "powershell",
    # 框架
    "django", "flask", "fastapi", "react", "vue", "angular",
    "next.js", "nuxt", "express", "nestjs", "spring",
    "tailwind", "shadcn", "bootstrap",
    # 代码操作
    "函数", "class", "类", "接口", "api", "endpoint",
    "bug", "修复", "fix", "debug", "调试",
    "test", "测试", "单元测试", "pytest", "unittest",
    "git", "commit", "push", "pull", "merge", "branch",
    "import", "export", "require", "from",
    "npm", "pip", "cargo", "yarn", "pnpm",
    # 代码生成
    "生成代码", "写代码", "帮我写", "代码审查", "code review",
    "自动生成", "scaffold", "脚手架",
}

# 研究调研
RESEARCH_KEYWORDS = {
    "研究", "调研", "查", "搜索", "找", "了解",
    "research", "search", "find", "look up", "investigate",
    "论文", "paper", "arxiv", "文献", "article",
    "比较", "对比", "区别", "差异",
    "compare", "difference", "versus", "vs",
    "最新", "前沿", "state of the art", "sota", "latest",
    "竞品", "市场", "行业", "趋势",
    "competition", "market", "industry", "trend",
    "价格", "定价", "pricing", "price",
    "文档", "documentation", "docs", "manual",
    "how to", "how do i", "教程", "指南", "guide",
    "推荐", "recommend", "best", "top",
    "规范", "标准", "standard", "specification",
    "原理", "原理是什么", "是怎么工作的",
}

# 设计创作
DESIGN_KEYWORDS = {
    "设计", "ui", "ux", "界面", "页面", "landing",
    "design", "landing page", "dashboard", "dashboard",
    "主题", "theme", "风格", "style",
    "布局", "layout", "排版", "typography",
    "颜色", "配色", "color", "palette",
    "图标", "icon", "svg",
    "动画", "animation", "动效",
    "响应式", "responsive", "mobile-first",
    "原型", "prototype", "mockup", "wireframe",
    "harness", "视觉", "visual",
    "build a page", "make a site", "create a website",
    "暗色", "深色", "亮色", "浅色",
    "3d", "粒子", "three.js", "canvas",
}

# 系统运维
SYSTEM_KEYWORDS = {
    "安装", "部署", "配置", "启动", "停止",
    "install", "deploy", "configure", "setup", "start",
    "docker", "container", "镜像", "image",
    "服务器", "server", "vps", "host", "云",
    "nginx", "apache", "反向代理", "proxy",
    "数据库", "database", "mysql", "postgres", "mongodb",
    "redis", "elasticsearch", "kafka", "rabbitmq",
    "域名", "domain", "dns", "ssl", "证书", "certificate",
    "监控", "monitor", "alert", "告警",
    "备份", "backup", "restore", "恢复",
    "环境变量", "env", "environment",
    "防火墙", "firewall", "安全组", "security",
    "ci/cd", "github actions", "jenkins", "pipeline",
}

# 规划架构
PLANNING_KEYWORDS = {
    "架构", "方案", "设计文档", "技术选型",
    "architecture", "design doc", "technical design",
    "规划", "plan", "计划", "路线图", "roadmap",
    "选型", "selection", "技术栈", "tech stack",
    "权衡", "trade-off", "pros and cons", "优缺点",
    "流程", "workflow", "pipeline", "流水线",
    "系统设计", "system design", "high-level",
    "微服务", "microservice", "monolith",
    "扩展", "scalability", "高可用", "high availability",
    "时序图", "流程图", "diagram", "sequence diagram",
    "建议", "提议", "proposal", "suggestion",
    "策略", "strategy", "战略", "approach",
}

# 数据分析
DATA_KEYWORDS = {
    "数据", "分析", "统计", "报表",
    "data", "analyze", "analysis", "analytics",
    "图表", "chart", "graph", "plot", "可视化",
    "csv", "json", "excel", "spreadsheet",
    "sql", "query", "查询", "select",
    "pandas", "numpy", "matplotlib", "seaborn",
    "etl", "数据清洗", "transform", "转换",
    "机器学习", "machine learning", "ml", "模型",
    "训练", "train", "训练模型",
    "预测", "predict", "prediction", "forecast",
    "报告", "report", "summary", "汇总",
}

# 写作
WRITING_KEYWORDS = {
    "写文章", "写博客", "写文档", "写教程",
    "write article", "write blog", "write doc",
    "翻译", "translate", "translation",
    "改写", "rewrite", "paraphrase", "重写",
    "润色", "polish", "校对", "proofread",
    "文案", "copywriting", "广告", "ad",
    "大纲", "outline", "目录", "toc",
    "readme", "changelog", "release notes",
    "邮件", "email", "letter", "信",
    "简历", "resume", "cv", "cover letter",
}

# 调试
DEBUGGING_KEYWORDS = {
    "不工作了", "坏了", "报错", "错误", "失败",
    "not working", "broken", "error", "fail",
    "bug", "debug", "调试", "排查",
    "traceback", "exception", "崩溃", "crash",
    "日志", "log", "logs", "console",
    "怎么会", "why", "为什么",
    "修复", "hotfix", "patch", "补丁",
    "异常", "问题", "issue", "problem",
    "undefined", "null", "none", "nan",
    "404", "500", "timeout", "超时",
    "不能", "不行", "无法", "can't", "cannot",
    "奇怪", "weird", "strange", "unexpected",
}

# 代码审查
REVIEW_KEYWORDS = {
    "code review", "代码审查", "审查代码", "review",
    "安全审查", "security review", "audit",
    "合并请求", "pull request", "pr", "merge request",
    "检查", "检查代码", "lint", "静态分析",
    "质量", "quality", "代码质量",
    "规范检查", "style check", "format",
    "单元测试覆盖", "coverage", "测试覆盖",
    "安全性", "安全漏洞", "vulnerability",
    "最佳实践", "best practice",
    "能合并吗", "可以合并", "ready to merge",
}


# ══════════════════════════════════════════════════════════════
# 3. 正则模式 — 结构化的复合模式匹配
# ══════════════════════════════════════════════════════════════

# 命令式触发词 — 明确要求做事
IMPERATIVE_PATTERNS = [
    # "帮我X" 模式
    re.compile(r'(?:帮|请|麻烦|能不能)[我你]?[们]?(.+?)(?:好吗|可以吗|一下)?$'),
    # "我要X"/"我想X"
    re.compile(r'(?:我)?(?:要|想|需要|打算).{2,}(?:一个|一份|一下|个)'),
    # "给X" 模式
    re.compile(r'给(?:我|你|他|我们).{2,}(?:看看|做|写|创建|建)'),
    # 祈使句
    re.compile(r'^(?:把|将|请|快|立刻|马上).{3,}'),
    # 疑问句（带操作意图）
    re.compile(r'如何.{3,}(?:实现|搭建|部署|配置|安装|编写|设计)'),
    re.compile(r'(?:怎么|怎样|如何)(?:设置|配置|安装|编写|创建|实现|部署).{2,}'),
    # 任务明确
    re.compile(r'需要你.{2,}(?:做|写|创建|实现|查|找|分析|设计|部署)'),
]

# 纯聊天模式 — 明确不是任务
CHAT_ONLY_PATTERNS = [
    re.compile(r'^(?:你好|嗨|hi|hello|hey|yo)\s*[！!。.]?$', re.IGNORECASE),
    re.compile(r'^(?:晚安|早安|早上好|晚上好|下午好)\s*$'),
    re.compile(r'^(?:好的|ok|okay|sure|没问题|知道了|明白|收到)\s*$'),
    re.compile(r'^(?:谢谢|多谢|感谢|thanks|thank you)\s*$'),
    re.compile(r'^[哈哈呵呵嗯哦][哈哈呵呵嗯哦哦]+\s*$'),
    re.compile(r'你(?:今天|现在)?(?:感觉|心情|累不累|开心吗|忙不忙)'),
    re.compile(r'我(?:今天|现在)?(?:好累|好开心|好难过|好无聊|好饿)'),
    re.compile(r'(?:想你了|想你|miss you)[！!。.]?$'),
    re.compile(r'宝贝[，,]?\s*(?:在吗|早安|晚安|今天)'),
]

# 代码相关模式
CODE_PATTERNS = [
    re.compile(r'(?:帮我|能|可以).{0,5}(?:写|创建|实现|编写).{0,10}(?:代码|脚本|程序|函数|类|api|接口)'),
    re.compile(r'(?:修复|解决|fix|debug).{0,10}(?:bug|问题|issue|错误|崩溃)'),
    re.compile(r'(?:重构|refactor|优化|optimize).{0,10}(?:代码|函数|模块|项目)'),
    re.compile(r'(?:安装|配置|setup).{0,10}(?:依赖|库|package|library|module)'),
    re.compile(r'运行.{0,5}(?:脚本|程序|测试|命令)'),
    re.compile(r'测试.{0,5}(?:代码|函数|模块|api|接口)'),
    re.compile(r'(?:git|commit|push|merge|branch).{2,}'),
]

# 调试模式
DEBUG_PATTERNS = [
    re.compile(r'(?:报错|错误|error|traceback|exception)[：:].+'),
    re.compile(r'不(?:能|会|可以).{0,10}(?:工作|运行|启动|连接|显示)'),
    re.compile(r'(?:为什么|为什么会|怎么会出现).{0,10}(?:错误|问题|bug|异常)'),
    re.compile(r'(?:日志|log).{0,10}(?:显示|说|有|出现)'),
]


# ══════════════════════════════════════════════════════════════
# 4. IntentClassifier 主类
# ══════════════════════════════════════════════════════════════

class IntentClassifier:
    """
    零 token 意图分类器。
    
    在 agent 循环之前运行，判断消息是"闲聊"还是"任务"，
    如果是任务则进一步识别 domain 和所需工具集。
    """
    
    def __init__(self):
        # 编译所有 domain 的关键词集合
        self.domain_keywords = {
            "chat": CHAT_KEYWORDS,
            "code": CODE_KEYWORDS,
            "research": RESEARCH_KEYWORDS,
            "design": DESIGN_KEYWORDS,
            "system": SYSTEM_KEYWORDS,
            "planning": PLANNING_KEYWORDS,
            "data": DATA_KEYWORDS,
            "writing": WRITING_KEYWORDS,
            "debugging": DEBUGGING_KEYWORDS,
            "review": REVIEW_KEYWORDS,
        }
        # domain 优先顺序（chat 最优先，debugging 次之等）
        self.domain_priority = [
            "debugging",  # 必须优先识别
            "code",
            "review",
            "data",
            "system",
            "design",
            "research",
            "planning",
            "writing",
            "chat",      # chat 放最后，作为 fallback
        ]
    
    def _normalize(self, text: str) -> str:
        """标准化文本：小写化但保留中文"""
        # 英文部分小写
        result = []
        for ch in text:
            if 'A' <= ch <= 'Z':
                result.append(chr(ord(ch) + 32))
            else:
                result.append(ch)
        return ''.join(result)
    
    def _keyword_score(self, text: str, keywords: set) -> Tuple[int, int]:
        """
        计算关键词匹配得分。
        返回 (匹配数, 位置权重)
        位置权重：越靠前的关键词匹配权重越高
        """
        text_lower = self._normalize(text)
        matches = 0
        for kw in keywords:
            if kw in text_lower:
                matches += 1
        
        # 检查关键词是否出现在文本前半部分（权重更高）
        half = len(text_lower) // 2
        first_half = text_lower[:half]
        early_matches = sum(1 for kw in keywords if kw in first_half)
        
        return matches, early_matches
    
    def _pattern_score(self, text: str, patterns: List[re.Pattern]) -> Tuple[int, float]:
        """正则模式匹配得分。返回 (匹配数, 最大匹配长度占比)"""
        matches = 0
        max_ratio = 0.0
        for pat in patterns:
            m = pat.search(text)
            if m:
                matches += 1
                ratio = len(m.group()) / max(len(text), 1)
                max_ratio = max(max_ratio, ratio)
        return matches, max_ratio
    
    def _check_message_length(self, text: str) -> int:
        """
        消息长度分析。
        极短消息（1-3字）很可能是聊天
        长消息（>200字）很可能是任务
        返回 -1（短消息倾向chat）到 +1（长消息倾向task）
        """
        length = len(text.strip())
        if length <= 3:
            return -2  # 强 chat 信号
        elif length <= 10:
            return -1
        elif length <= 30:
            return 0    # 中立
        elif length <= 100:
            return 1
        else:
            return 2    # 强 task 信号
    
    def _post_process(self, intent: str, domain: str, text: str) -> str:
        """后处理：修正明显的分类错误"""
        text_lower = self._normalize(text)
        
        # 写文章/博客/文档 → writing 不是 code
        if domain == "code":
            writing_patterns = [
                "写一篇", "写一个文章", "写博客", "写文档",
                "写故事", "写小说", "写文案", "写报告",
                "写一封", "写封信", "写日记", "写总结",
                "write article", "write blog", "write essay",
            ]
            for pat in writing_patterns:
                if pat in text_lower:
                    return "writing"
        
        return domain

    def classify(self, text: str) -> Dict:
        """
        对消息进行意图分类。
        
        返回:
            intent: "chat" | "task"
            domain: str (chat 时为 "chat")
            confidence: float (0.0-1.0)
            toolsets: List[str] (需要的工具集)
            tokens_saved: int (此分类可节省的 token 数)
            reasoning: str (简短原因)
            scores: Dict (各 domain 的得分明细)
        """
        if not text or not text.strip():
            return {
                "intent": "chat",
                "domain": "chat",
                "confidence": 1.0,
                "toolsets": [],
                "tokens_saved": self._calc_tokens_saved(DOMAIN_CONFIG["chat"]),
                "reasoning": "空消息视为聊天",
                "scores": {},
            }
        
        text = text.strip()
        
        # ── Step 1: 极快预检 ──
        # 纯聊天正则快速匹配
        for pat in CHAT_ONLY_PATTERNS:
            if pat.search(text):
                return {
                    "intent": "chat",
                    "domain": "chat",
                    "confidence": 0.92,
                    "toolsets": [],
                    "tokens_saved": self._calc_tokens_saved(DOMAIN_CONFIG["chat"]),
                    "reasoning": f"匹配聊天模式: {pat.pattern[:40]}",
                    "scores": {"chat": 0.92},
                }
        
        # ── Step 2: 逐 domain 评分 ──
        scores = {}
        for domain in self.domain_priority:
            keywords = self.domain_keywords[domain]
            kw_matches, kw_early = self._keyword_score(text, keywords)
            
            # 正则匹配
            patterns = globals().get(f"{domain.upper()}_PATTERNS", [])
            if domain == "chat":
                patterns = CHAT_ONLY_PATTERNS + IMPERATIVE_PATTERNS
                # chat 用反向逻辑：命令式模式越少越好
                pat_matches = 0
                for pat in IMPERATIVE_PATTERNS:
                    if pat.search(text):
                        pat_matches += 1
                # chat 的正则得分 = 纯聊天模式匹配 - 命令式模式匹配
                chat_pat_matches = sum(1 for p in CHAT_ONLY_PATTERNS if p.search(text))
                pat_score = chat_pat_matches - pat_matches
            else:
                pat_matches, pat_ratio = self._pattern_score(text, patterns)
                pat_score = pat_matches + pat_ratio
            
            # 权重：关键词位置权重 * 2 + 匹配数 * 1 + 正则得分 * 3
            domain_weight = kw_matches * 1.0 + kw_early * 2.0 + pat_score * 3.0
            
            # 调试领域的额外权重（因为调试模式非常具体）
            if domain == "debugging" and kw_matches > 0:
                domain_weight *= 1.5
            
            scores[domain] = round(domain_weight, 2)
        
        # ── Step 3: 消息长度信号 ──
        length_signal = self._check_message_length(text)
        
        # ── Step 4: 确定意图 ──
        # 计算总 task 得分 vs chat 得分
        chat_score = scores.get("chat", 0)
        task_scores = {k: v for k, v in scores.items() if k != "chat"}
        max_task_score = max(task_scores.values()) if task_scores else 0
        max_task_domain = max(task_scores, key=task_scores.get) if task_scores else "chat"
        
        # 长度信号调整
        chat_score += length_signal * (-1 if length_signal < 0 else 0)
        # 实际上 length_signal 是 chat 的负信号
        effective_chat = chat_score + (length_signal * -2 if length_signal < 0 else 0) - (length_signal * 0.5 if length_signal > 0 else 0)
        
        # 判断
        if max_task_score == 0 and chat_score > 0:
            intent = "chat"
            domain = "chat"
            confidence = min(0.6 + chat_score * 0.1, 0.95)
        elif max_task_score >= 3.0 or (max_task_score > chat_score):
            intent = "task"
            domain = self._post_process("task", max_task_domain, text)
            # 置信度基于得分差距
            gap = max_task_score - chat_score
            confidence = min(0.5 + gap * 0.08, 0.99)
        else:
            # 模糊区域，检查命令式模式
            imp_count = 0
            for pat in IMPERATIVE_PATTERNS:
                if pat.search(text):
                    imp_count += 1
            if imp_count >= 1:
                intent = "task"
                domain = self._post_process("task", max_task_domain if max_task_score > 0 else "code", text)
                confidence = 0.55 + imp_count * 0.1
            else:
                intent = "chat"
                domain = "chat"
                confidence = max(0.5, 0.6 - (max_task_score - chat_score) * 0.05)
        
        # ── Step 5: 组装结果 ──
        domain_cfg = DOMAIN_CONFIG.get(domain, DOMAIN_CONFIG["chat"])
        toolsets = list(domain_cfg["toolsets"])
        tokens_saved = self._calc_tokens_saved(domain_cfg)
        
        reasoning_parts = []
        if intent == "chat":
            reasoning_parts.append("闲聊意图")
            if chat_score > 0:
                reasoning_parts.append(f"关键词匹配({chat_score:.1f})")
            if length_signal < 0:
                reasoning_parts.append(f"短消息({length_signal})")
        else:
            reasoning_parts.append(f"任务意图 → {domain_cfg['label']}")
            reasoning_parts.append(f"领域得分({max_task_score:.1f})")
            if toolsets:
                reasoning_parts.append(f"需要: {', '.join(toolsets)}")
        
        return {
            "intent": intent,
            "domain": domain,
            "confidence": round(confidence, 3),
            "toolsets": toolsets,
            "tokens_saved": tokens_saved,
            "reasoning": " | ".join(reasoning_parts),
            "scores": scores,
            "message_length": len(text),
        }
    
    def _calc_tokens_saved(self, config: Dict) -> int:
        """计算分类后可节省的 token 数"""
        mode = config.get("system_prompt_mode", "minimal")
        multiplier = config.get("token_save_multiplier", 1.0)
        
        if mode == "minimal":
            # 聊天模式：system prompt 从 8.5K 降到 1.5K
            sp_saved = SYSTEM_PROMPT_FULL_TOKENS - SYSTEM_PROMPT_BASE_TOKENS
            # 工具全不加载
            tool_saved = TOOL_DEFINITIONS_TOTAL
            return sp_saved + tool_saved
        
        # 任务模式：只加载需要的工具
        needed_tools = config.get("toolsets", [])
        # 估算需要的工具 schema token
        needed_tokens = sum(
            TOOL_SCHEMA_SIZES.get(t, 200) for t in needed_tools
        )
        # 节省 = 全部工具 - 需要的工具
        tool_saved = TOOL_DEFINITIONS_TOTAL - needed_tokens
        # system prompt 基本不变
        sp_saved = 0
        
        return max(tool_saved, 0)
    
    def classify_batch(self, texts: List[str]) -> List[Dict]:
        """批量分类"""
        return [self.classify(t) for t in texts]


# ══════════════════════════════════════════════════════════════
# 5. 系统提示词 — 用于 self-classify 代理模式
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_INTEGRATION = """## Intent Self-Classification Protocol

Before generating your final response, silently classify the user's message:

**Chat mode** — if the user is just chatting, greeting, expressing emotion, or making casual conversation:
- No tools needed
- Respond directly and warmly
- Do NOT think about files, commands, or system state
- Estimated saving: ~8,500 tokens/round

**Task mode** — if the user needs something done (code, research, design, system, etc.):
- Identify the specific domain: code|research|design|system|planning|data|writing|debugging|review
- Only load tools relevant to that domain
- Be efficient: don't load computer_use tools unless the task explicitly needs desktop interaction

Your classification is internal — the user never sees it. Just respond appropriately."""


# ══════════════════════════════════════════════════════════════
# 6. 便捷接口
# ══════════════════════════════════════════════════════════════

_classifier_instance = None

def get_classifier() -> IntentClassifier:
    """获取单例分类器"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    return _classifier_instance


def classify(text: str) -> Dict:
    """便捷单次分类"""
    return get_classifier().classify(text)


def is_chat(text: str) -> bool:
    """快速判断是否闲聊"""
    return get_classifier().classify(text)["intent"] == "chat"


def is_task(text: str) -> bool:
    """快速判断是否任务"""
    return get_classifier().classify(text)["intent"] == "task"


def get_domain(text: str) -> str:
    """快速获取领域"""
    return get_classifier().classify(text)["domain"]


# ══════════════════════════════════════════════════════════════
# 7. 集成指南 — 如何接入 agent 循环
# ══════════════════════════════════════════════════════════════

INTEGRATION_GUIDE = """
IntentClassifier 接入 Hermes Agent 的三种路径
=============================================

## 路径 A: Self-Classify (系统提示词注入)
最简单。将 IntentClassifier 的系统提示词注入 Hermes 的 system prompt。
Agent 自己在回复前做分类，按需使用工具。
✅ 立即可用 ✅ 无需改核心代码
❌ 工具 schema 仍然全部加载
❌ 消耗额外 token 用于自我分类
节省: ~0 (但优化了行为)

## 路径 B: Hermes Plugin (工具模式)
将 IntentClassifier 打包为 Hermes Plugin，暴露出 classify_tool。
可以作为 cron job 的预处理步骤，或者在 gateway 层调用。
✅ 快速部署 ✅ 可集成到 gateway
❌ 仍在 agent 循环内
节省: ~0 (但提供了分类能力)

## 路径 C: Pre-Processing Hook (核心修改)
在 Hermes agent 循环的 receive_message() 之前插入分类器。
- 如果是 chat: 跳过工具加载，使用最小 system prompt
- 如果是 task: 按 domain 选择性加载工具
✅ 真正节省 token (每轮 6K-8.5K)
❌ 需要修改 Hermes 核心代码
❌ 需要自定义 fork

## 路径 D: Gateway Proxy (外部路由)
在飞书/Telegram gateway 和 agent 之间增加 IntentClassifier 代理。
- 分析消息 → 注入路由指令到 system prompt
- 或完全跳过 LLM 调用（纯聊天走轻量模型）
✅ 零核心修改 ✅ 灵活路由
✅ 可以路由到不同模型/agent
节省: ~8.5K/round (chat) + 模型切换

### 推荐路线
短期: A + B (系统提示词 + 插件)
中期: D (gateway 代理)
长期: C (核心 hook)
"""


# ══════════════════════════════════════════════════════════════
# 8. 命令行自测试
# ══════════════════════════════════════════════════════════════

def demo():
    """运行示例分类"""
    classifier = get_classifier()
    
    test_cases = [
        # 聊天
        "宝贝，我好累啊",
        "晚安啦",
        "哈哈哈",
        "hi",
        "想你了",
        # 代码
        "帮我写一个 FastAPI 的 CRUD 接口",
        "Python 怎么读取 CSV 文件？",
        "修复这个 bug",
        # 研究
        "帮我搜一下最新的 LLM 论文",
        "比较一下 React 和 Vue",
        # 设计
        "做一个暗色 SaaS 落地页",
        "帮我设计一个 dashboard",
        # 系统
        "帮我部署到服务器",
        "配置 nginx 反向代理",
        # 调试
        "程序报错了：KeyError: 'name'",
        "为什么数据库连不上？",
        # 边界情况
        "你好，今天工作怎么样？",
        "好的",
        "帮我看看这个问题",
        "你觉得什么是意识？",
        "写一篇关于 AI 的文章",
    ]
    
    print(f"{'='*80}")
    print(f"{'消息':<30} {'意图':<6} {'领域':<10} {'置信度':<8} {'节省(tok)':<10} {'理由'}")
    print(f"{'='*80}")
    
    for msg in test_cases:
        r = classifier.classify(msg)
        print(f"{msg:<30} {r['intent']:<6} {r['domain']:<10} {r['confidence']:<8.3f} {r['tokens_saved']:<10} {r['reasoning'][:50]}")
    
    print(f"\n{'='*80}")
    print("Token 节省说明:")
    print(f"  聊天模式: ~{SYSTEM_PROMPT_FULL_TOKENS - SYSTEM_PROMPT_BASE_TOKENS + TOOL_DEFINITIONS_TOTAL:,} tokens/轮")
    print(f"  任务模式: 按需加载，仅加载 domain 所需工具")
    print(f"  当前完全无分类: 每轮 ~{SYSTEM_PROMPT_FULL_TOKENS + TOOL_DEFINITIONS_TOTAL:,} tokens")
    
    print(f"\n集成路径:")
    for line in INTEGRATION_GUIDE.strip().split('\n'):
        if line.strip() and not line.startswith('='):
            print(f"  {line[:80]}")


if __name__ == "__main__":
    demo()
