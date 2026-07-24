"""
LAAP Consciousness Harness 使用示例

展示如何使用完整的harness系统：
1. 初始化ConsciousnessHarness
2. 执行代码任务
3. 使用合规检查器
4. 使用反馈引擎
5. 跨会话状态恢复
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.harness import ConsciousnessHarness
from laap_coding.core.compliance_checker import CodeComplianceChecker
from laap_coding.core.feedback_engine import FeedbackEngine


def example_basic_usage():
    """基础用法示例"""
    print("=" * 60)
    print("示例1：基础任务执行")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    description = "创建一个Python函数，计算两个数的最大公约数(GCD)"
    intent = "create_function"

    result = harness.run(description=description, intent=intent)

    print(f"任务状态: {result.get('status')}")
    print(f"子任务数: {len(result.get('subtasks', []))}")

    if result.get('results'):
        for i, r in enumerate(result['results']):
            print(f"  子任务 {i+1}: {r.get('subtask')} - {r.get('status')}")


def example_compliance_checker():
    """合规检查器示例"""
    print("\n" + "=" * 60)
    print("示例2：代码合规检查")
    print("=" * 60)

    checker = CodeComplianceChecker(os.path.join(os.path.dirname(__file__), "core"))
    result = checker.check_project()

    print(f"合规状态: {'✓ 合规' if result.compliant else '✗ 不合规'}")
    print(f"合规分数: {result.score:.2f}")
    print(f"检查文件数: {result.summary.get('files_checked', 0)}")
    print(f"总问题数: {result.summary.get('total_issues', 0)}")
    print(f"错误数: {result.summary.get('errors', 0)}")
    print(f"警告数: {result.summary.get('warnings', 0)}")

    report = checker.generate_report(result)
    print("\n合规报告摘要:")
    lines = report.split('\n')[:20]
    print('\n'.join(lines))


def example_feedback_engine():
    """反馈引擎示例"""
    print("\n" + "=" * 60)
    print("示例3：反馈引擎使用")
    print("=" * 60)

    engine = FeedbackEngine(r"D:\LAAP")

    context = {
        "task_id": "example_feedback_task",
        "intent": "create_api",
        "keywords": ["api", "rest", "flask"],
        "description": "创建一个Flask REST API服务",
    }

    execution_result = {"duration_ms": 5000.0}
    verification_result = {
        "passed": True,
        "score": 0.88,
        "issues": [],
    }

    feedback_result = engine.process_feedback(context, execution_result, verification_result)
    print(f"反馈处理结果:")
    print(f"  修正: {feedback_result['corrected']}")
    print(f"  学习: {feedback_result['learned']}")
    print(f"  积累: {feedback_result['accumulated']}")

    stats = engine.get_statistics()
    print(f"\n统计信息:")
    print(f"  模式总数: {stats['pattern_stats']['total_patterns']}")
    print(f"  经验总数: {stats['experience_stats']['total_experiences']}")
    print(f"  成功率: {stats['experience_stats']['success_rate']:.1%}")

    report = engine.get_quality_report()
    print("\n质量趋势报告:")
    print(report)


def example_cross_session():
    """跨会话状态恢复示例"""
    print("\n" + "=" * 60)
    print("示例4：跨会话状态恢复")
    print("=" * 60)

    harness1 = ConsciousnessHarness(workdir=r"D:\LAAP")
    harness2 = ConsciousnessHarness(workdir=r"D:\LAAP")

    task_id = "example_cross_session"

    task_state = {
        "task_id": task_id,
        "description": "跨会话状态恢复演示",
        "status": "in_progress",
        "current_subtask_index": 2,
        "subtasks": [
            {
                "sub_task_id": "step_1",
                "description": "需求分析",
                "status": "completed",
                "estimated_lines": 20,
                "dependencies": [],
            },
            {
                "sub_task_id": "step_2",
                "description": "架构设计",
                "status": "completed",
                "estimated_lines": 40,
                "dependencies": ["step_1"],
            },
            {
                "sub_task_id": "step_3",
                "description": "代码实现",
                "status": "pending",
                "estimated_lines": 100,
                "dependencies": ["step_2"],
            },
        ],
        "results": [
            {
                "subtask": "需求分析",
                "sub_task_id": "step_1",
                "status": "completed",
                "duration_ms": 150.0,
                "feedback": {"corrected": False, "corrections": []},
            },
            {
                "subtask": "架构设计",
                "sub_task_id": "step_2",
                "status": "completed",
                "duration_ms": 200.0,
                "feedback": {"corrected": False, "corrections": []},
            },
        ],
    }

    print("保存任务状态...")
    harness1.memory_layer.save_task_state(task_id, task_state)

    print("恢复任务状态...")
    restore_result = harness2.restore_task(task_id)
    print(f"恢复状态: {restore_result['status']}")
    print(f"从索引恢复: {restore_result['restored_from_index']}")

    harness1.memory_layer._state_persistence.delete_task_state(task_id)
    print("任务状态已清理")


def example_memory_layers():
    """三层记忆架构示例"""
    print("\n" + "=" * 60)
    print("示例5：三层记忆架构")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")
    memory = harness.memory_layer

    memory._working_memory["current_task"] = {
        "task_id": "example_task",
        "status": "in_progress",
        "step": 3,
    }

    memory._short_term_memory["project_rules"] = {
        "max_lines_per_subtask": 200,
        "coding_style": "PEP8",
        "test_required": True,
    }

    memory._long_term_memory["architecture_patterns"] = {
        "CQRS": "适用于复杂业务场景，分离读/写操作",
        "Repository": "数据访问层抽象，解耦业务逻辑与数据源",
    }

    working_val = memory.get_working_memory("current_task")
    short_val = memory.get_short_term_memory("project_rules")
    long_val = memory.get_long_term_memory("architecture_patterns")

    print("工作记忆（当前任务上下文）:")
    print(f"  {working_val}")

    print("\n短期记忆（项目约定和规则）:")
    print(f"  {short_val}")

    print("\n长期记忆（架构模式和最佳实践）:")
    print(f"  {long_val}")

    status = memory.get_memory_status()
    print("\n记忆层状态:")
    print(f"  工作记忆大小: {status['working_memory']['size']}")
    print(f"  短期记忆大小: {status['short_term_memory']['size']}")
    print(f"  长期记忆大小: {status['long_term_memory']['size']}")


def example_context_compression():
    """上下文压缩示例"""
    print("\n" + "=" * 60)
    print("示例6：上下文压缩")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    long_context = """
    用户需求：创建一个完整的电商订单管理系统，包含以下功能：
    1. 用户注册和登录
    2. 商品浏览和搜索
    3. 购物车管理
    4. 订单创建和支付
    5. 订单状态跟踪
    6. 管理员后台管理

    技术要求：
    - 使用Python FastAPI框架
    - 使用SQLAlchemy ORM
    - 使用JWT认证
    - 支持RESTful API
    - 需要完整的单元测试

    项目结构：
    - app/
      - api/          # API路由
      - models/       # 数据库模型
      - schemas/      # Pydantic模式
      - services/     # 业务逻辑
      - utils/        # 工具函数
    """

    print(f"原始上下文长度: {len(long_context)} 字符")

    compressed = harness.memory_layer.compress_context(long_context, max_tokens=200)
    print(f"压缩后长度: {len(compressed)} 字符")
    print(f"压缩率: {(1 - len(compressed) / len(long_context)) * 100:.1f}%")

    print("\n压缩后的摘要:")
    print(compressed[:300] + "..." if len(compressed) > 300 else compressed)


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("LAAP Consciousness Harness 使用示例")
    print("=" * 60)

    example_basic_usage()
    example_compliance_checker()
    example_feedback_engine()
    example_cross_session()
    example_memory_layers()
    example_context_compression()

    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
