"""
测试脚本：验证执行引擎（Executor Agent）功能

测试覆盖：
1. CodeTemplateEngine：代码生成模板系统
2. ToolOrchestrator：工具编排器
3. SandboxExecutor：沙箱隔离执行
4. ExecutionLayer：子任务执行器（按依赖图顺序执行）
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from laap_coding.core.harness import (
    CodeTemplateEngine,
    ToolOrchestrator,
    SandboxExecutor,
    ExecutionLayer,
    SubTask,
    DependencyGraph,
)


class TestCodeTemplateEngine:
    """测试代码生成模板引擎"""

    def __init__(self):
        self.template_engine = CodeTemplateEngine()

    def test_python_class_template(self):
        """测试Python类模板"""
        code = self.template_engine.render_python_class(
            class_name="Calculator",
            description="简单计算器类",
            params=", a: int, b: int",
            init_body="        self.a = a\n        self.b = b",
            methods="    def add(self) -> int:\n        return self.a + self.b\n\n    def multiply(self) -> int:\n        return self.a * self.b",
        )
        assert "class Calculator:" in code
        assert "def add(self)" in code
        assert "def multiply(self)" in code
        print("[✓] Python类模板测试通过")

    def test_python_function_template(self):
        """测试Python函数模板"""
        code = self.template_engine.render_python_function(
            function_name="greet",
            params="name: str",
            return_type=" -> str",
            description="问候函数",
            body="    return f'Hello, {name}!'",
        )
        assert "def greet(name: str) -> str:" in code
        assert "return f'Hello," in code
        print("[✓] Python函数模板测试通过")

    def test_pydantic_model_template(self):
        """测试Pydantic模型模板"""
        code = self.template_engine.render_pydantic_model(
            model_name="User",
            description="用户模型",
            fields="    id: int\n    name: str\n    email: str",
        )
        assert "class User(BaseModel):" in code
        assert "class UserCreate(BaseModel):" in code
        assert "class UserUpdate(BaseModel):" in code
        print("[✓] Pydantic模型模板测试通过")

    def test_fastapi_route_template(self):
        """测试FastAPI路由模板"""
        code = self.template_engine.render_fastapi_route(
            endpoint="users",
            description="用户管理",
            model_class="User",
            service_class="UserService",
            module="models",
        )
        assert '@router.get("/")' in code
        assert '@router.post("/")' in code
        assert '@router.put("/{item_id}")' in code
        assert '@router.delete("/{item_id}")' in code
        print("[✓] FastAPI路由模板测试通过")

    def test_javascript_class_template(self):
        """测试JavaScript类模板"""
        code = self.template_engine.render(
            "javascript_class",
            class_name="Counter",
            description="计数器类",
            params="initialValue = 0",
            init_body="        this.count = initialValue;",
            methods="    increment() {\n        return ++this.count;\n    }",
        )
        assert "class Counter" in code
        assert "increment()" in code
        print("[✓] JavaScript类模板测试通过")

    def test_typescript_interface_template(self):
        """测试TypeScript接口模板"""
        code = self.template_engine.render(
            "typescript_interface",
            interface_name="User",
            description="用户接口",
            properties="    id: number;\n    name: string;\n    email: string;",
        )
        assert "interface User" in code
        assert "id: number" in code
        print("[✓] TypeScript接口模板测试通过")

    def test_readme_template(self):
        """测试README模板"""
        code = self.template_engine.render_readme(
            project_name="TestProject",
            description="测试项目",
            features="- Feature 1\n- Feature 2",
        )
        assert "# TestProject" in code
        assert "## Features" in code
        print("[✓] README模板测试通过")

    def test_available_templates(self):
        """测试可用模板列表"""
        templates = self.template_engine.get_available_templates()
        assert len(templates) > 0
        assert "python_class" in templates
        assert "javascript_class" in templates
        assert "typescript_interface" in templates
        assert "common_readme" in templates
        print(f"[✓] 可用模板数量: {len(templates)}")

    def test_template_categories(self):
        """测试模板分类"""
        categories = self.template_engine.get_template_categories()
        assert "python" in categories
        assert "javascript" in categories
        assert "typescript" in categories
        assert "common" in categories
        print(f"[✓] 模板分类: {list(categories.keys())}")

    def run_all(self):
        """运行所有模板测试"""
        print("\n" + "=" * 60)
        print("测试 CodeTemplateEngine - 代码生成模板系统")
        print("=" * 60)
        self.test_python_class_template()
        self.test_python_function_template()
        self.test_pydantic_model_template()
        self.test_fastapi_route_template()
        self.test_javascript_class_template()
        self.test_typescript_interface_template()
        self.test_readme_template()
        self.test_available_templates()
        self.test_template_categories()


class TestToolOrchestrator:
    """测试工具编排器"""

    def __init__(self, workdir: str):
        self.workdir = workdir
        self.tool_orchestrator = ToolOrchestrator(workdir=workdir)

    def test_write_read_file(self):
        """测试文件读写操作"""
        test_file = os.path.join(self.workdir, "test_file.txt")
        content = "Hello, World!"
        
        result = self.tool_orchestrator.write_file(test_file, content)
        assert result == f"Written: {test_file}"
        
        read_content = self.tool_orchestrator.read_file(test_file)
        assert read_content == content
        print("[✓] 文件读写操作测试通过")

    def test_append_file(self):
        """测试文件追加操作"""
        test_file = os.path.join(self.workdir, "append_test.txt")
        self.tool_orchestrator.write_file(test_file, "Line 1\n")
        self.tool_orchestrator.append_file(test_file, "Line 2\n")
        
        content = self.tool_orchestrator.read_file(test_file)
        assert "Line 1" in content
        assert "Line 2" in content
        print("[✓] 文件追加操作测试通过")

    def test_delete_file(self):
        """测试文件删除操作"""
        test_file = os.path.join(self.workdir, "delete_test.txt")
        self.tool_orchestrator.write_file(test_file, "to be deleted")
        
        result = self.tool_orchestrator.delete_file(test_file)
        assert result == f"Deleted: {test_file}"
        assert not os.path.exists(test_file)
        print("[✓] 文件删除操作测试通过")

    def test_list_files(self):
        """测试文件列表操作"""
        self.tool_orchestrator.write_file(os.path.join(self.workdir, "file1.txt"), "content1")
        self.tool_orchestrator.write_file(os.path.join(self.workdir, "file2.txt"), "content2")
        
        files = self.tool_orchestrator.list_files(self.workdir)
        assert "file1.txt" in files
        assert "file2.txt" in files
        print("[✓] 文件列表操作测试通过")

    def test_run_shell(self):
        """测试Shell命令执行"""
        result = self.tool_orchestrator.run_shell("echo hello world", timeout=30)
        assert result["success"]
        assert "hello world" in result["stdout"]
        print("[✓] Shell命令执行测试通过")

    def test_run_python(self):
        """测试Python代码执行"""
        code = "print('Hello from Python')"
        result = self.tool_orchestrator.run_python(code, timeout=30)
        assert result["success"]
        assert "Hello from Python" in result["stdout"]
        print("[✓] Python代码执行测试通过")

    def test_available_tools(self):
        """测试可用工具列表"""
        tools = self.tool_orchestrator.get_available_tools()
        assert len(tools) > 0
        assert "read_file" in tools
        assert "write_file" in tools
        assert "run_shell" in tools
        assert "run_python" in tools
        assert "git_status" in tools
        print(f"[✓] 可用工具数量: {len(tools)}")

    def run_all(self):
        """运行所有工具编排器测试"""
        print("\n" + "=" * 60)
        print("测试 ToolOrchestrator - 工具编排器")
        print("=" * 60)
        self.test_write_read_file()
        self.test_append_file()
        self.test_delete_file()
        self.test_list_files()
        self.test_run_shell()
        self.test_run_python()
        self.test_available_tools()


class TestSandboxExecutor:
    """测试沙箱执行器"""

    def __init__(self, workdir: str):
        self.workdir = workdir
        self.sandbox = SandboxExecutor(workdir)

    def test_run_command(self):
        """测试命令执行"""
        result = self.sandbox.run_command("echo sandbox test", timeout=30)
        assert result["success"]
        assert "sandbox test" in result["stdout"]
        print("[✓] 命令执行测试通过")

    def test_run_python(self):
        """测试Python代码执行"""
        code = "print(42)"
        result = self.sandbox.run_python(code, timeout=30)
        assert result["success"]
        assert "42" in result["stdout"]
        print("[✓] Python代码执行测试通过")

    def test_timeout(self):
        """测试超时控制"""
        code = "import time; time.sleep(2)"
        result = self.sandbox.run_python(code, timeout=1)
        assert not result["success"]
        assert result["timeout"]
        print("[✓] 超时控制测试通过")

    def test_validate_path(self):
        """测试路径验证"""
        valid_path = self.workdir
        assert self.sandbox.validate_path(valid_path)
        
        invalid_path = os.path.join(os.path.dirname(self.workdir), "..")
        print(f"[✓] 路径验证测试通过 (available={self.sandbox.status.get('available', False)})")

    def test_status(self):
        """测试沙箱状态"""
        status = self.sandbox.status
        assert "workdir" in status
        assert "available" in status
        print(f"[✓] 沙箱状态: {status}")

    def run_all(self):
        """运行所有沙箱执行器测试"""
        print("\n" + "=" * 60)
        print("测试 SandboxExecutor - 沙箱执行器")
        print("=" * 60)
        self.test_run_command()
        self.test_run_python()
        self.test_timeout()
        self.test_validate_path()
        self.test_status()


class TestExecutionLayer:
    """测试执行层（子任务执行器）"""

    def __init__(self, workdir: str):
        self.workdir = workdir
        self.execution_layer = ExecutionLayer(workdir=workdir)

    def test_execute_single_subtask(self):
        """测试执行单个子任务"""
        self.execution_layer.reset()
        subtask = SubTask(
            sub_task_id="test_1",
            parent_task_id="parent_1",
            description="创建一个简单的Python类",
            files=["simple_class.py"],
            estimated_lines=50,
            dependencies=[],
        )
        
        result = self.execution_layer.execute(subtask)
        assert result.success
        assert "class" in result.output
        print("[✓] 单个子任务执行测试通过")

    def test_execute_with_dependency_graph(self):
        """测试按依赖图顺序执行子任务"""
        self.execution_layer.reset()
        subtasks = [
            SubTask(
                sub_task_id="task_1",
                parent_task_id="parent",
                description="创建数据模型",
                files=["models.py"],
                estimated_lines=50,
                dependencies=[],
            ),
            SubTask(
                sub_task_id="task_2",
                parent_task_id="parent",
                description="创建服务层",
                files=["service.py"],
                estimated_lines=80,
                dependencies=["task_1"],
            ),
            SubTask(
                sub_task_id="task_3",
                parent_task_id="parent",
                description="创建API路由",
                files=["api.py"],
                estimated_lines=60,
                dependencies=["task_2"],
            ),
        ]
        
        result = self.execution_layer.execute_with_dependency_graph(subtasks)
        assert result["success"]
        assert result["execution_order"] == ["task_1", "task_2", "task_3"]
        assert result["completed_subtasks"] == 3
        print("[✓] 依赖图顺序执行测试通过")

    def test_write_run_code(self):
        """测试编写和运行代码"""
        code = """def add(a, b):
    return a + b

print(f"3 + 5 = {add(3, 5)}")
"""
        file_path = os.path.join(self.workdir, "test_add.py")
        
        write_result = self.execution_layer.write_code(file_path, code)
        assert write_result.success
        
        run_result = self.execution_layer.run_python(code, timeout=30)
        assert run_result.success
        assert "3 + 5 = 8" in run_result.output
        print("[✓] 编写和运行代码测试通过")

    def test_status(self):
        """测试执行层状态"""
        status = self.execution_layer.status
        assert "workdir" in status
        assert "executed_tasks" in status
        assert "available_tools" in status
        assert "available_templates" in status
        print(f"[✓] 执行层状态: 工具={len(status['available_tools'])}, 模板={len(status['available_templates'])}")

    def test_reset(self):
        """测试重置执行状态"""
        self.execution_layer.reset()
        subtask = SubTask(
            sub_task_id="reset_test",
            parent_task_id="parent",
            description="测试重置",
            files=[],
            estimated_lines=10,
            dependencies=[],
        )
        self.execution_layer.execute(subtask)
        assert len(self.execution_layer.get_executed_tasks()) == 1
        
        self.execution_layer.reset()
        assert len(self.execution_layer.get_executed_tasks()) == 0
        print("[✓] 重置执行状态测试通过")

    def run_all(self):
        """运行所有执行层测试"""
        print("\n" + "=" * 60)
        print("测试 ExecutionLayer - 执行层")
        print("=" * 60)
        self.test_execute_single_subtask()
        self.test_execute_with_dependency_graph()
        self.test_write_run_code()
        self.test_status()
        self.test_reset()


class TestDependencyGraph:
    """测试依赖图"""

    def test_topological_sort(self):
        """测试拓扑排序"""
        subtasks = [
            SubTask("a", "parent", "task a", [], 10, []),
            SubTask("b", "parent", "task b", [], 10, ["a"]),
            SubTask("c", "parent", "task c", [], 10, ["b"]),
        ]
        
        graph = DependencyGraph()
        graph.build_from_subtasks(subtasks)
        
        sorted_ids = graph.topological_sort()
        assert sorted_ids == ["a", "b", "c"]
        print("[✓] 拓扑排序测试通过")

    def test_cycle_detection(self):
        """测试循环依赖检测"""
        subtasks = [
            SubTask("a", "parent", "task a", [], 10, ["b"]),
            SubTask("b", "parent", "task b", [], 10, ["a"]),
        ]
        
        graph = DependencyGraph()
        graph.build_from_subtasks(subtasks)
        
        cycles = graph.detect_cycles()
        assert len(cycles) > 0
        print("[✓] 循环依赖检测测试通过")

    def test_independent_tasks(self):
        """测试独立任务获取"""
        subtasks = [
            SubTask("a", "parent", "task a", [], 10, []),
            SubTask("b", "parent", "task b", [], 10, []),
            SubTask("c", "parent", "task c", [], 10, ["a"]),
        ]
        
        graph = DependencyGraph()
        graph.build_from_subtasks(subtasks)
        
        independent = graph.get_independent_tasks()
        assert "a" in independent
        assert "b" in independent
        print("[✓] 独立任务获取测试通过")

    def run_all(self):
        """运行所有依赖图测试"""
        print("\n" + "=" * 60)
        print("测试 DependencyGraph - 依赖图")
        print("=" * 60)
        self.test_topological_sort()
        self.test_cycle_detection()
        self.test_independent_tasks()


def main():
    """主测试入口"""
    print("=" * 60)
    print("执行引擎（Executor Agent）功能测试")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="laap_executor_test_") as tmpdir:
        print(f"\n测试工作目录: {tmpdir}")

        # 测试代码生成模板引擎
        template_test = TestCodeTemplateEngine()
        template_test.run_all()

        # 测试工具编排器
        tool_test = TestToolOrchestrator(tmpdir)
        tool_test.run_all()

        # 测试沙箱执行器
        sandbox_test = TestSandboxExecutor(tmpdir)
        sandbox_test.run_all()

        # 测试执行层
        execution_test = TestExecutionLayer(tmpdir)
        execution_test.run_all()

        # 测试依赖图
        graph_test = TestDependencyGraph()
        graph_test.run_all()

    print("\n" + "=" * 60)
    print("所有测试通过! ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()