"""
Harness MCP Tools - 让xiaozhi通过MCP完成复杂代码开发工程

集成LAAP Consciousness Harness的核心能力：
1. 代码任务执行
2. 代码合规检查
3. 记忆层管理
4. 复杂项目开发
"""

import sys
import os
import json
import tempfile
import traceback

HARNESS_ROOT = os.path.join(os.path.dirname(__file__), "..", "harness", "laap_coding")
sys.path.insert(0, HARNESS_ROOT)

try:
    from laap_coding.core.harness import ConsciousnessHarness, TaskContext
    from laap_coding.core.compliance_checker import CodeComplianceChecker
    from laap_coding.core.feedback_engine import FeedbackEngine
    HARNESS_AVAILABLE = True
except Exception as e:
    print(f"Harness import error: {e}")
    HARNESS_AVAILABLE = False

_harness_instances = {}
_feedback_engines = {}


def get_harness(project_dir: str = None) -> ConsciousnessHarness:
    if project_dir not in _harness_instances:
        if project_dir is None:
            project_dir = tempfile.mkdtemp(prefix="harness_project_")
        _harness_instances[project_dir] = ConsciousnessHarness(workdir=project_dir)
    return _harness_instances[project_dir]


def get_feedback_engine(project_dir: str) -> FeedbackEngine:
    if project_dir not in _feedback_engines:
        _feedback_engines[project_dir] = FeedbackEngine(project_dir)
    return _feedback_engines[project_dir]


def tool_harness_run_task(description: str, intent: str = "create_code", project_dir: str = None) -> str:
    """运行harness代码任务"""
    if not HARNESS_AVAILABLE:
        return "错误：Harness模块未正确加载"
    
    try:
        harness = get_harness(project_dir)
        
        result = harness.run(description=description, intent=intent)
        
        status = result.get("status", "unknown")
        subtasks = result.get("subtasks", [])
        
        lines = []
        lines.append(f"任务执行结果: {status}")
        lines.append(f"子任务数: {len(subtasks)}")
        
        if subtasks:
            lines.append("\n子任务列表:")
            for i, st in enumerate(subtasks):
                st_status = st.get("status", "pending")
                st_desc = st.get("description", "")
                lines.append(f"  {i+1}. [{st_status}] {st_desc}")
        
        if result.get("results"):
            lines.append("\n执行结果:")
            for i, r in enumerate(result["results"]):
                st_name = r.get("subtask", "")
                st_status = r.get("status", "")
                st_duration = r.get("duration_ms", 0)
                lines.append(f"  {i+1}. {st_name}: {st_status} ({st_duration:.0f}ms)")
        
        if project_dir:
            lines.append(f"\n项目目录: {project_dir}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"任务执行失败: {str(e)}\n{traceback.format_exc()}"


def tool_harness_check_compliance(project_dir: str) -> str:
    """检查代码合规性"""
    if not HARNESS_AVAILABLE:
        return "错误：Harness模块未正确加载"
    
    try:
        checker = CodeComplianceChecker(project_dir)
        result = checker.check_project()
        
        lines = []
        lines.append(f"合规状态: {'✓ 合规' if result.compliant else '✗ 不合规'}")
        lines.append(f"合规分数: {result.score:.2f}")
        
        summary = result.summary
        lines.append(f"检查文件数: {summary.get('files_checked', 0)}")
        lines.append(f"总问题数: {summary.get('total_issues', 0)}")
        lines.append(f"错误数: {summary.get('errors', 0)}")
        lines.append(f"警告数: {summary.get('warnings', 0)}")
        lines.append(f"循环依赖数: {summary.get('circular_dependencies', 0)}")
        
        if result.issues:
            lines.append("\n问题详情:")
            for issue in result.issues[:10]:
                severity = "🔴" if issue.severity == "error" else "🟡" if issue.severity == "warning" else "🔵"
                lines.append(f"  {severity} {issue.message}")
            if len(result.issues) > 10:
                lines.append(f"  ... 还有 {len(result.issues) - 10} 个问题")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"合规检查失败: {str(e)}\n{traceback.format_exc()}"


def tool_harness_get_memory_status(project_dir: str = None) -> str:
    """获取记忆层状态"""
    if not HARNESS_AVAILABLE:
        return "错误：Harness模块未正确加载"
    
    try:
        harness = get_harness(project_dir)
        memory = harness.memory_layer
        status = memory.get_memory_status()
        
        lines = []
        lines.append("记忆层状态:")
        
        wm = status.get("working_memory", {})
        lines.append(f"  工作记忆: {wm.get('size', 0)} 项")
        if wm.get("keys"):
            lines.append(f"    键: {', '.join(wm['keys'])}")
        
        stm = status.get("short_term_memory", {})
        lines.append(f"  短期记忆: {stm.get('size', 0)} 项")
        if stm.get("keys"):
            lines.append(f"    键: {', '.join(stm['keys'])}")
        
        ltm = status.get("long_term_memory", {})
        lines.append(f"  长期记忆: {ltm.get('size', 0)} 项")
        if ltm.get("keys"):
            lines.append(f"    键: {', '.join(ltm['keys'])}")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"获取记忆状态失败: {str(e)}\n{traceback.format_exc()}"


def tool_harness_compress_context(context: str, max_tokens: int = 200) -> str:
    """压缩上下文"""
    if not HARNESS_AVAILABLE:
        return "错误：Harness模块未正确加载"
    
    try:
        harness = get_harness()
        
        original_len = len(context)
        compressed = harness.memory_layer.compress_context(context, max_tokens=max_tokens)
        compressed_len = len(compressed)
        ratio = (1 - compressed_len / original_len) * 100 if original_len > 0 else 0
        
        lines = []
        lines.append(f"原始长度: {original_len} 字符")
        lines.append(f"压缩后长度: {compressed_len} 字符")
        lines.append(f"压缩率: {ratio:.1f}%")
        lines.append("\n压缩后的摘要:")
        lines.append("-" * 50)
        lines.append(compressed)
        lines.append("-" * 50)
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"上下文压缩失败: {str(e)}\n{traceback.format_exc()}"


def tool_harness_complete_complex_project(requirement: str, project_dir: str = None) -> str:
    """完成复杂项目开发（完整harness工作流）"""
    if not HARNESS_AVAILABLE:
        return "错误：Harness模块未正确加载"
    
    try:
        if project_dir is None:
            project_dir = tempfile.mkdtemp(prefix="harness_complex_project_")
        
        harness = get_harness(project_dir)
        checker = CodeComplianceChecker(project_dir)
        feedback_engine = get_feedback_engine(project_dir)
        
        lines = []
        lines.append(f"🔧 开始复杂项目开发")
        lines.append(f"📁 项目目录: {project_dir}")
        lines.append("=" * 50)
        
        lines.append("\n📝 阶段1: 任务规划")
        result = harness.run(description=requirement, intent="create_fullstack_app")
        status = result.get("status", "unknown")
        lines.append(f"   规划状态: {status}")
        
        subtasks = result.get("subtasks", [])
        lines.append(f"   规划子任务数: {len(subtasks)}")
        
        if subtasks:
            for i, st in enumerate(subtasks):
                lines.append(f"   {i+1}. [{st.get('status')}] {st.get('description')}")
        
        if result.get("results"):
            lines.append("\n🚀 阶段2: 执行结果")
            for i, r in enumerate(result["results"]):
                st_name = r.get("subtask", "")
                st_status = r.get("status", "")
                st_duration = r.get("duration_ms", 0)
                lines.append(f"   {i+1}. {st_name}: {st_status} ({st_duration:.0f}ms)")
        
        lines.append("\n✅ 阶段3: 合规检查")
        compliance_result = checker.check_project()
        lines.append(f"   合规状态: {'✓ 合规' if compliance_result.compliant else '✗ 不合规'}")
        lines.append(f"   合规分数: {compliance_result.score:.2f}")
        lines.append(f"   检查文件数: {compliance_result.summary.get('files_checked', 0)}")
        lines.append(f"   错误数: {compliance_result.summary.get('errors', 0)}")
        
        lines.append("\n📊 阶段4: 反馈与学习")
        stats = feedback_engine.get_statistics()
        lines.append(f"   模式总数: {stats['pattern_stats']['total_patterns']}")
        lines.append(f"   经验总数: {stats['experience_stats']['total_experiences']}")
        lines.append(f"   成功率: {stats['experience_stats']['success_rate']:.1%}")
        
        lines.append("\n📁 阶段5: 生成文件")
        all_files = []
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, project_dir)
                    file_size = os.path.getsize(full_path)
                    all_files.append(f"   ✓ {rel_path} ({file_size} bytes)")
        
        if all_files:
            lines.extend(all_files)
            lines.append(f"\n   生成文件总数: {len(all_files)}")
        else:
            lines.append("   未生成任何文件")
        
        lines.append("\n" + "=" * 50)
        lines.append("🎉 复杂项目开发完成!")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"复杂项目开发失败: {str(e)}\n{traceback.format_exc()}"


def tool_harness_list_projects() -> str:
    """列出当前运行的harness项目"""
    if not _harness_instances:
        return "当前没有运行的harness项目"
    
    lines = []
    lines.append("当前运行的harness项目:")
    
    for i, (project_dir, harness) in enumerate(_harness_instances.items()):
        memory = harness.memory_layer
        status = memory.get_memory_status()
        
        wm_size = status.get("working_memory", {}).get("size", 0)
        stm_size = status.get("short_term_memory", {}).get("size", 0)
        ltm_size = status.get("long_term_memory", {}).get("size", 0)
        
        lines.append(f"\n项目 {i+1}:")
        lines.append(f"  目录: {project_dir}")
        lines.append(f"  工作记忆: {wm_size} 项")
        lines.append(f"  短期记忆: {stm_size} 项")
        lines.append(f"  长期记忆: {ltm_size} 项")
    
    return "\n".join(lines)


def tool_harness_clear_project(project_dir: str) -> str:
    """清除指定项目"""
    if project_dir in _harness_instances:
        del _harness_instances[project_dir]
        if project_dir in _feedback_engines:
            del _feedback_engines[project_dir]
        return f"已清除项目: {project_dir}"
    return f"未找到项目: {project_dir}"


HARNESS_TOOLS = [
    {
        "name": "harness.run_task",
        "description": "【代码任务】运行harness代码开发任务，创建代码文件。支持各种编程任务，如创建函数、类、API服务等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "任务描述，如'创建一个计算GCD的Python函数'"},
                "intent": {"type": "string", "description": "任务意图，如create_function, create_api, create_fullstack_app"},
                "project_dir": {"type": "string", "description": "项目目录（可选）"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "harness.check_compliance",
        "description": "【代码检查】检查项目代码的合规性，包括依赖分析、接口隔离、开闭原则、单一职责、循环依赖检测等。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "项目目录"}
            },
            "required": ["project_dir"]
        }
    },
    {
        "name": "harness.get_memory_status",
        "description": "【记忆状态】查看harness三层记忆架构的状态（工作记忆、短期记忆、长期记忆）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "项目目录（可选）"}
            }
        }
    },
    {
        "name": "harness.compress_context",
        "description": "【上下文压缩】压缩长文本上下文为摘要，减少token使用，提高效率。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "需要压缩的文本内容"},
                "max_tokens": {"type": "integer", "description": "最大token数（默认200）"}
            },
            "required": ["context"]
        }
    },
    {
        "name": "harness.complete_complex_project",
        "description": "【复杂项目】完整完成一个复杂项目开发，包括任务规划、代码生成、合规检查、反馈学习等全流程。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "description": "项目需求描述"},
                "project_dir": {"type": "string", "description": "项目目录（可选）"}
            },
            "required": ["requirement"]
        }
    },
    {
        "name": "harness.list_projects",
        "description": "【项目列表】列出当前运行的所有harness项目。",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "harness.clear_project",
        "description": "【清除项目】清除指定的harness项目。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_dir": {"type": "string", "description": "项目目录"}
            },
            "required": ["project_dir"]
        }
    }
]


if __name__ == "__main__":
    print("Harness MCP Tools Test")
    print("=" * 50)
    
    result = tool_harness_run_task("创建一个Python函数，计算两个数的最大公约数")
    print(result)
    print("\n" + "=" * 50)
