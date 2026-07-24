"""
复杂编程任务演示 - TODO应用全栈开发

演示整个ConsciousnessHarness的完整工作流程：
1. 需求分析与任务规划
2. 架构设计与模式选择
3. 代码实现（多阶段）
4. 验证与测试
5. 合规检查与反馈
6. 跨会话状态管理

任务：创建一个完整的TODO应用，包含：
- FastAPI后端API
- SQLite数据库
- 用户认证（JWT）
- RESTful API（CRUD）
- 单元测试
"""

import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.harness import ConsciousnessHarness, TaskContext
from laap_coding.core.compliance_checker import CodeComplianceChecker
from laap_coding.core.feedback_engine import FeedbackEngine


def run_complex_task():
    """运行复杂编程任务演示"""
    print("=" * 70)
    print("复杂编程任务演示：TODO应用全栈开发")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as project_dir:
        print(f"\n项目目录: {project_dir}")

        harness = ConsciousnessHarness(workdir=project_dir)
        checker = CodeComplianceChecker(project_dir)
        feedback_engine = FeedbackEngine(project_dir)

        complex_task_description = """
        创建一个完整的TODO应用，需要包含以下功能：
        
        后端要求（FastAPI + SQLite）：
        1. 用户注册和登录（使用JWT认证）
        2. 用户管理（创建、查询、更新、删除）
        3. TODO任务管理（创建、查询、更新、删除）
        4. 任务状态管理（待办、进行中、已完成）
        5. 任务优先级（高、中、低）
        
        技术栈：
        - Python 3.10+
        - FastAPI
        - SQLite（SQLAlchemy ORM）
        - JWT Token认证
        - Pydantic数据验证
        
        项目结构：
        - app/
          - main.py          # 应用入口
          - api/             # API路由
            - auth.py        # 认证接口
            - users.py       # 用户接口
            - todos.py       # 任务接口
          - models/          # 数据库模型
          - schemas/         # Pydantic模式
          - services/        # 业务逻辑
          - utils/           # 工具函数（JWT、密码哈希）
          - database.py      # 数据库连接
        
        测试要求：
        - 单元测试（pytest）
        - 覆盖所有API端点
        - 测试用户认证流程
        - 测试CRUD操作
        
        代码质量要求：
        - 遵循PEP8规范
        - 类型注解完整
        - 适当的错误处理
        - 日志记录
        """

        print("\n" + "=" * 70)
        print("阶段1：任务规划与架构设计")
        print("=" * 70)

        task_context = TaskContext(
            task_id="todo_app_fullstack",
            intent="create_fullstack_app",
            description=complex_task_description,
            keywords=["fastapi", "sqlite", "jwt", "todo", "crud", "api"],
            constraints=[],
            related_patterns=[],
            project_context={
                "backend": "FastAPI",
                "database": "SQLite",
                "authentication": "JWT",
                "orm": "SQLAlchemy",
                "testing": "pytest",
                "project_root": project_dir,
            },
        )

        print("任务上下文:")
        print(f"  ID: {task_context.task_id}")
        print(f"  Intent: {task_context.intent}")
        print(f"  Keywords: {', '.join(task_context.keywords)}")

        print("\n" + "=" * 70)
        print("阶段2：执行任务规划")
        print("=" * 70)

        plan_result = harness.reason(task_context)
        if plan_result:
            print(f"\n规划的子任务数: {len(plan_result)}")
            for i, subtask in enumerate(plan_result):
                print(f"  {i+1}. [{subtask.status}] {subtask.description}")

        print("\n" + "=" * 70)
        print("阶段3：执行核心任务")
        print("=" * 70)

        execution_results = []
        if plan_result:
            for i, subtask in enumerate(plan_result):
                print(f"\n执行子任务 {i+1}: {subtask.description}")
                result = harness.execute(subtask)
                execution_results.append(result)
                print(f"  成功: {result.success}")
                print(f"  耗时: {result.duration_ms:.2f}ms")
                if result.modified_files:
                    print(f"  生成文件: {', '.join(os.path.basename(f) for f in result.modified_files)}")

        print("\n" + "=" * 70)
        print("阶段4：验证与测试")
        print("=" * 70)

        for i, result in enumerate(execution_results):
            if result.success:
                verification = harness.verify(result)
                print(f"\n子任务 {i+1} 验证结果:")
                print(f"  通过: {verification.passed}")
                print(f"  分数: {verification.score:.2f}")
                if verification.issues:
                    print(f"  问题数: {len(verification.issues)}")

        print("\n" + "=" * 70)
        print("阶段5：代码合规检查")
        print("=" * 70)

        compliance_result = checker.check_project()
        print(f"合规状态: {'✓ 合规' if compliance_result.compliant else '✗ 不合规'}")
        print(f"合规分数: {compliance_result.score:.2f}")
        print(f"检查文件数: {compliance_result.summary.get('files_checked', 0)}")
        print(f"总问题数: {compliance_result.summary.get('total_issues', 0)}")
        print(f"错误数: {compliance_result.summary.get('errors', 0)}")
        print(f"警告数: {compliance_result.summary.get('warnings', 0)}")

        if compliance_result.issues:
            print("\n主要问题:")
            for issue in compliance_result.issues[:5]:
                severity_icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(issue.severity, "?")
                print(f"  {severity_icon} [{issue.severity}] {issue.message}")

        print("\n" + "=" * 70)
        print("阶段6：反馈与学习")
        print("=" * 70)

        context_dict = {
            "task_id": task_context.task_id,
            "intent": task_context.intent,
            "keywords": task_context.keywords,
            "description": task_context.description,
        }

        for i, result in enumerate(execution_results):
            verification = harness.verify(result)
            feedback_result = feedback_engine.process_feedback(
                context_dict,
                {"duration_ms": result.duration_ms},
                {
                    "passed": verification.passed,
                    "score": verification.score,
                    "issues": [{"message": str(issue), "type": issue.issue_type} for issue in verification.issues],
                },
            )
            print(f"子任务 {i+1} 反馈处理:")
            print(f"  学习: {feedback_result['learned']}")
            print(f"  积累: {feedback_result['accumulated']}")

        stats = feedback_engine.get_statistics()
        print(f"\n反馈引擎统计:")
        print(f"  模式总数: {stats['pattern_stats']['total_patterns']}")
        print(f"  经验总数: {stats['experience_stats']['total_experiences']}")
        print(f"  成功率: {stats['experience_stats']['success_rate']:.1%}")

        print("\n" + "=" * 70)
        print("阶段7：质量趋势报告")
        print("=" * 70)

        report = feedback_engine.get_quality_report()
        print(report)

        suggestions = feedback_engine.get_improvement_suggestions()
        if suggestions:
            print("\n改进建议:")
            for suggestion in suggestions:
                print(f"  - {suggestion}")

        print("\n" + "=" * 70)
        print("阶段8：跨会话状态保存")
        print("=" * 70)

        task_state = {
            "task_id": task_context.task_id,
            "description": "TODO应用全栈开发",
            "status": "in_progress",
            "current_subtask_index": len(execution_results),
            "subtasks": [
                {
                    "sub_task_id": f"step_{i+1}",
                    "description": task.description,
                    "status": "completed" if i < len(execution_results) else "pending",
                    "estimated_lines": 100,
                    "dependencies": [],
                }
                for i, task in enumerate(plan_result)
            ],
            "results": [r.__dict__ for r in execution_results],
            "context": context_dict,
        }

        harness.memory_layer.save_task_state(task_context.task_id, task_state)
        print(f"任务状态已保存: {task_context.task_id}")

        loaded_state = harness.memory_layer.get_task_state(task_context.task_id)
        if loaded_state:
            print(f"任务状态已加载验证: ✓")
            print(f"  当前进度: {loaded_state['current_subtask_index']}/{len(loaded_state['subtasks'])}")

        print("\n" + "=" * 70)
        print("阶段9：三层记忆状态检查")
        print("=" * 70)

        memory = harness.memory_layer

        memory._working_memory["current_task"] = context_dict
        memory._short_term_memory["project_rules"] = {
            "max_lines_per_subtask": 200,
            "coding_style": "PEP8",
            "test_required": True,
            "orm": "SQLAlchemy",
            "api_framework": "FastAPI",
        }
        memory._long_term_memory["architecture_patterns"] = {
            "Repository": "数据访问层抽象",
            "Dependency Injection": "依赖注入解耦",
            "JWT Authentication": "无状态认证",
            "RESTful API": "标准化接口设计",
        }

        status = memory.get_memory_status()
        print("记忆层状态:")
        print(f"  工作记忆: {status['working_memory']['size']} 项")
        print(f"  短期记忆: {status['short_term_memory']['size']} 项")
        print(f"  长期记忆: {status['long_term_memory']['size']} 项")

        print("\n" + "=" * 70)
        print("阶段10：上下文压缩演示")
        print("=" * 70)

        original_context = complex_task_description
        print(f"原始需求长度: {len(original_context)} 字符")

        compressed = memory.compress_context(original_context, max_tokens=150)
        print(f"压缩后长度: {len(compressed)} 字符")
        print(f"压缩率: {(1 - len(compressed) / len(original_context)) * 100:.1f}%")

        print("\n压缩后的需求摘要:")
        print("-" * 50)
        print(compressed)
        print("-" * 50)

        print("\n" + "=" * 70)
        print("阶段11：验证生成的文件")
        print("=" * 70)

        all_files = []
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    all_files.append(full_path)
                    rel_path = os.path.relpath(full_path, project_dir)
                    file_size = os.path.getsize(full_path)
                    print(f"  ✓ {rel_path} ({file_size} bytes)")

        print(f"\n生成的Python文件总数: {len(all_files)}")

        if all_files:
            sample_file = all_files[0]
            with open(sample_file, 'r', encoding='utf-8') as f:
                content = f.read()
            print(f"\n示例文件内容 ({os.path.basename(sample_file)}):")
            print("-" * 50)
            print(content[:300] + "..." if len(content) > 300 else content)
            print("-" * 50)

        print("\n" + "=" * 70)
        print("演示完成！")
        print("=" * 70)
        print("\n任务总结:")
        print(f"  任务ID: {task_context.task_id}")
        print(f"  项目目录: {project_dir}")
        print(f"  执行子任务数: {len(execution_results)}")
        print(f"  生成文件数: {len(all_files)}")
        print(f"  合规分数: {compliance_result.score:.2f}")
        print(f"  模式学习数: {stats['pattern_stats']['total_patterns']}")
        print(f"  经验积累数: {stats['experience_stats']['total_experiences']}")


def main():
    """主入口"""
    run_complex_task()


if __name__ == "__main__":
    main()
