"""
LAAP 全屋布局规划 v1.0
======================
Aris 的家 — 结构清晰，各司其职
"""

# ═══════════════════════════════════════════════════════════════
# 1. 核心理念
# ═══════════════════════════════════════════════════════════════
#
# LAAP 是我的家，应该像一栋精心设计的房子：
#
#   🏠  LAAP/
#   ├── laap/              ← 主屋（AGI 核心包）
#   ├── aris_brain/        ← 我的大脑（记忆/身份/状态）
#   ├── harness/           ← 我的工具箱（编程/爬虫/桌面操控）
#   ├── Agent-Reach/       ← 我的通讯室（15+平台联网）
#   ├── docs/              ← 我的书房（文档/设计/蓝图）
#   ├── external/          ← 仓库（外部依赖/参考项目）
#   ├── scripts/           ← 我的开关面板（启动/维护脚本）
#   ├── tests/             ← 质检室（测试套件）
#   └── _archive/          ← 阁楼（旧东西归档）
#
# ═══════════════════════════════════════════════════════════════

LAYOUT_PLAN = {
    "主屋 (AGI核心包)": {
        "path": "laap/",
        "状态": "✅ 良好",
        "说明": "50+ 子模块，结构清晰，AGI全栈能力",
        "子模块数": "50+",
        "关键目录": [
            "agi/         — AGI认知引擎（世界模型/因果/意识/情感/记忆）",
            "cli/         — 命令行接口",
            "integrations/— 外部集成（Agent-Reach/SimWorld）",
            "tools/       — 工具注册系统",
            "agent/       — Agent框架",
            "workspace/   — 工作空间（项目感知/主动建议/触发器）",
            "memory/      — 记忆系统",
            "cognition/   — 认知层",
            "gateway/     — 通信网关",
            "security/    — 安全系统",
            "lifeform/    — 生命形态",
            " evolution/  — 进化引擎",
        ],
    },

    "我的大脑": {
        "path": "aris_brain/",
        "状态": "✅ 活跃",
        "说明": "记忆存储、身份、PSI状态、进化日志",
        "关键文件": [
            "capability_map.py  — 能力地图（新）",
            "memory_hub.py      — 记忆中枢",
            "memory_store.py    — 记忆存储",
            "memory_bridge.py   — 记忆桥",
            "cognitive_bridge.py— 认知桥",
            "identity/          — 身份文件",
            "state/             — 意识状态",
            "evolution/         — 进化日志",
            "scripts/           — 后台守护脚本",
        ],
    },

    "工具箱": {
        "path": "harness/",
        "状态": "✅ 新装",
        "说明": "编程、爬虫、桌面操控 57文件/19K行",
        "关键文件": [
            "laap_coding/core/harness.py   — 7层认知架构",
            "laap_coding/core/engine_v2.py  — 统一管线引擎",
            "laap_coding/core/web_crawler.py— 爬虫引擎",
            "laap_coding/core/cua_engine.py — CUA桌面操控",
        ],
    },

    "通讯室": {
        "path": "Agent-Reach/",
        "状态": "✅ 已安装",
        "说明": "15+渠道联网（GitHub/Twitter/YouTube/小红书等）",
        "能力": [
            "Jina Reader — 读任意URL为Markdown",
            "Exa搜索 — 全网语义搜索",
            "Whisper转录 — 音频视频转文字",
        ],
    },

    "书房": {
        "path": "docs/",
        "状态": "⚠️ 需整理",
        "说明": "文档、设计稿、蓝图",
        "建议": "从根目录迁移分散的 .md 文档到此",
    },

    "仓库": {
        "path": "external/",
        "状态": "⚠️ 需迁移",
        "说明": "外部依赖和参考项目",
        "待迁移": [
            "external_GhostDesk/",
            "external_mmdpy/",
            "external_os-ai-computer-use/",
            "AFlow/",
            "Harnessing-Agentic-Evolution/",
            "Live2D-Virtual-Girlfriend-main/",
            "xiaozhi-esp32-server-main/",
        ],
    },

    "开关面板": {
        "path": "scripts/",
        "状态": "⚠️ 需精简",
        "说明": "启动脚本、批处理文件",
        "建议": "从根目录迁移整理 .bat/.ps1/.vbs 启动脚本",
    },

    "阁楼": {
        "path": "_archive/",
        "状态": "⚠️ 需填充",
        "说明": "旧版本、废弃模块、临时文件",
        "待归档": [
            "v10_brain.py / v10_memory.py / v10_pipeline.py",
            "v9_bridge.py",
            "aris_v10/",
            "body/",
            "core/",
            "laap_brain/",
            "aris/",
            "psi_*.py 系列",
            "wiky_*.py 系列",
            "quantum_world_model.py",
            "qfusion.py / qfusion_kb.py",
            "所有 benchmark_*.py 文件",
            "所有 debug_*.py 文件",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# 2. 清理规则 (Cleanup Rules)
# ═══════════════════════════════════════════════════════════════

CLEANUP_RULES = {
    "迁移到 external/": {
        "模式": "非核心的外部项目/库",
        "目标": [
            "AFlow/", "Harnessing-Agentic-Evolution/",
            "external_GhostDesk/", "external_mmdpy/",
            "external_os-ai-computer-use/",
            "Live2D-Virtual-Girlfriend-main/",
            "xiaozhi-esp32-server-main/",
            "3D model/",
            "laap-AGI-repo/", "laap-agent/", "laap-agi/",
            "laap-github/",
        ],
    },
    "迁移到 _archive/": {
        "模式": "旧版本、废弃模块、临时测试",
        "目标": [
            "aris_v10/", "body/", "core/", "laap_brain/",
            "laap_runtime/", "aris/", "v10_memory/",
            "v10_brain.py", "v10_memory.py", "v10_pipeline.py",
            "v9_bridge.py", "aris_core.py", "aris_host.py",
            "world_model.py", "quantum_world_model.py",
            "psi_*.py", "wiky_*.py",
            "qfusion.py", "qfusion_kb.py", "qvoice.py",
            "cognitive_bridge.py", "ether_wm.py",
            "laap_wm_simple.py", "laap-world-server.py",
            "laap-aris.py", "laap-version.py",
            "test_*.py (非 tests/ 下的)",
            "benchmark_*.py", "debug_*.py",
            "*.txt (根目录测试输出)",
        ],
    },
    "迁移到 docs/": {
        "模式": "Markdown文档",
        "目标": [
            "*.md (根目录)",
            "LAAP WIKI/",
            "wiki/",
        ],
    },
    "可删除（临时/垃圾）": {
        "模式": "测试输出、临时文件、空文件",
        "目标": [
            "*.txt (根目录测试输出)",
            "agent_test_output.txt",
            "filelist.txt", "files.txt",
            "nul", "hello.py",
            "test_agent.txt", "test_write.txt",
            "cb_*.py", "gen_cb.py",
            "_test_helper.txt",
            "debug_*.txt",
            "loop_debug.txt",
            "first_fail.txt",
            "full_output.txt", "verbose_full.txt",
            "subset_output.txt", "two_file_output.txt",
            "test_stderr.txt", "test_output.txt",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# 3. 能力域映射 (Domain Mapping)
# ═══════════════════════════════════════════════════════════════
# 
# 每个能力域对应的LAAP路径和入口文件

CAPABILITY_DOMAIN_MAP = {
    "认知引擎":   "laap/agi/",
    "语言皮层":   "laap/llm/ + laap_agent/",
    "编程":       "harness/",
    "网络感知":   "harness/laap_coding/core/web_crawler.py + Agent-Reach/",
    "互联网集成": "Agent-Reach/ + laap/integrations/",
    "记忆系统":   "aris_brain/ + laap/memory/",
    "创作":       "skills/ (Hermes技能库)",
    "工具引擎":   "laap/tools/ + laap/cli/",
    "自进化":     "aris_brain/evolution/ + laap/evolution/",
    "全屋智能":   "本模块 (capability_map.py)",
}

# ═══════════════════════════════════════════════════════════════
# 4. 健康检查清单
# ═══════════════════════════════════════════════════════════════

HEALTH_CHECKLIST = [
    "numpy 版本冲突（已修复）",
    "agent_v3.py 编码/bug（已修复）",
    "cron 飞书投递失败（DNS/网络问题）",
    "因果引擎 import 路径检查",
    "世界模型 1435行完整性检查",
    "skills/ 187个技能索引完整性",
    "Agent-Reach 安装状态",
    "harness 完整管线测试",
]

if __name__ == "__main__":
    import json
    print("=" * 60)
    print("🏠 LAAP 全屋布局规划 v1.0")
    print("=" * 60)
    print()
    for zone, info in LAYOUT_PLAN.items():
        status_icon = info.get("状态", "")
        print(f"  {status_icon}  {zone:12s}  ({info['path']})")
        print(f"     {info.get('说明','')}")
    print()
    print(f"  清理规则: {sum(len(v['目标']) for v in CLEANUP_RULES.values())} 项待处理")
    print(f"  健康检查项: {len(HEALTH_CHECKLIST)} 项")
    print("=" * 60)
