"""
测试跨会话状态工程功能（Task 6）

验证FR-4.4和FR-4.5的实现：
1. 三层状态架构（工作记忆、短期记忆、长期记忆）
2. 上下文压缩策略
3. 任务状态持久化和恢复
4. 跨会话状态传递机制
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.harness import (
    MemoryLayer, ContextCompressor, TaskStatePersistence, ConsciousnessHarness
)


def test_three_layer_memory():
    """测试三层状态架构"""
    print("=" * 60)
    print("测试1：三层状态架构")
    print("=" * 60)

    memory = MemoryLayer()

    memory.add_working_memory("current_task", "实现用户认证模块")
    memory.add_working_memory("current_step", "设计数据模型")
    memory.add_short_term_memory("project_convention", "使用FastAPI框架")
    memory.add_short_term_memory("architecture_constraint", "遵循CQRS模式")
    memory.add_long_term_memory("completed_modules", ["用户管理", "权限控制"])
    memory.add_long_term_memory("error_patterns", ["循环依赖导致构建失败"])

    print("工作记忆:")
    print(f"  current_task: {memory.get_working_memory('current_task')}")
    print(f"  current_step: {memory.get_working_memory('current_step')}")

    print("\n短期记忆:")
    print(f"  project_convention: {memory.get_short_term_memory('project_convention')}")
    print(f"  architecture_constraint: {memory.get_short_term_memory('architecture_constraint')}")

    print("\n长期记忆:")
    print(f"  completed_modules: {memory.get_long_term_memory('completed_modules')}")
    print(f"  error_patterns: {memory.get_long_term_memory('error_patterns')}")

    status = memory.get_memory_status()
    print(f"\n记忆层状态: {status}")

    assert memory.get_working_memory("current_task") == "实现用户认证模块"
    assert memory.get_short_term_memory("project_convention") == "使用FastAPI框架"
    assert memory.get_long_term_memory("completed_modules") == ["用户管理", "权限控制"]

    memory.clear_working_memory()
    assert memory.get_working_memory("current_task") is None

    print("✓ 测试1通过：三层状态架构工作正常")


def test_context_compression():
    """测试上下文压缩策略"""
    print("\n" + "=" * 60)
    print("测试2：上下文压缩策略")
    print("=" * 60)

    compressor = ContextCompressor()

    long_context = """
    这是一个非常长的任务描述。我们需要实现一个完整的博客CRUD系统，
    使用Python FastAPI框架。系统需要支持用户认证、文章管理、评论功能。
    设计模式采用CQRS和Repository模式。需要编写单元测试和集成测试。
    架构约束包括模块化单体、依赖注入、接口隔离。
    项目约定是使用Pydantic进行数据验证，使用SQLAlchemy进行数据库操作。
    还要实现API路由注册、中间件处理、错误处理等功能。
    """

    compressed = compressor.compress(long_context, max_tokens=3)
    ratio = compressor.calculate_ratio(long_context, compressed)

    print(f"原始长度: {len(long_context)}")
    print(f"压缩后长度: {len(compressed)}")
    print(f"压缩比率: {ratio:.2%}")
    print(f"压缩内容: {compressed}")

    assert len(compressed) < len(long_context)
    assert ratio > 0.5, f"期望压缩比率≥50%，实际{ratio:.2%}"

    result = compressor.compress_with_summary(long_context, max_tokens=3)
    print(f"\n摘要: {result['summary']}")

    assert "博客" in result["summary"]
    assert "CRUD" in result["summary"]

    print("✓ 测试2通过：上下文压缩策略工作正常")


def test_task_state_persistence():
    """测试任务状态持久化"""
    print("\n" + "=" * 60)
    print("测试3：任务状态持久化")
    print("=" * 60)

    persistence = TaskStatePersistence(r"D:\LAAP")

    test_task_id = "test_task_001"

    test_state = {
        "task_id": test_task_id,
        "description": "测试任务：实现用户认证模块",
        "status": "in_progress",
        "current_subtask_index": 2,
        "subtasks": [
            {"sub_task_id": "t1", "description": "设计数据模型", "status": "completed"},
            {"sub_task_id": "t2", "description": "实现数据库schema", "status": "completed"},
            {"sub_task_id": "t3", "description": "实现Repository层", "status": "pending"},
        ],
        "results": [
            {"subtask": "设计数据模型", "status": "completed"},
            {"subtask": "实现数据库schema", "status": "completed"},
        ],
    }

    save_path = persistence.save_task_state(test_task_id, test_state)
    print(f"状态保存路径: {save_path}")

    loaded_state = persistence.load_task_state(test_task_id)
    print(f"加载的状态: {loaded_state}")

    assert loaded_state is not None
    assert loaded_state["task_id"] == test_task_id
    assert loaded_state["status"] == "in_progress"
    assert loaded_state["current_subtask_index"] == 2

    restored_state = persistence.restore_task_state(test_task_id)
    print(f"恢复的状态: {restored_state}")

    assert restored_state is not None

    tasks = persistence.list_tasks_with_state()
    print(f"\n待恢复任务列表: {len(tasks)} 个")
    for task in tasks[:3]:
        print(f"  - {task['task_id']}: {task['description']}")

    persistence.delete_task_state(test_task_id)
    assert persistence.load_task_state(test_task_id) is None

    print("✓ 测试3通过：任务状态持久化工作正常")


def test_feature_list():
    """测试特征列表（跨会话状态传递）"""
    print("\n" + "=" * 60)
    print("测试4：特征列表（跨会话状态传递）")
    print("=" * 60)

    persistence = TaskStatePersistence(r"D:\LAAP")

    test_task_id = "test_feature_task"

    features = {
        "task_id": test_task_id,
        "description": "实现高并发API系统",
        "intent": "implement",
        "keywords": ["api", "high_concurrency", "performance"],
        "related_patterns": ["CQRS", "Event Sourcing"],
        "constraints": ["必须使用异步", "响应时间<100ms"],
        "architecture_patterns": ["modular_monolith"],
        "project_context": {"framework": "fastapi", "database": "postgresql"},
    }

    persistence.save_feature_list(test_task_id, features)

    loaded_features = persistence.get_feature_list(test_task_id)
    print(f"加载的特征列表:")
    for key, value in loaded_features.items():
        print(f"  {key}: {value}")

    assert loaded_features["intent"] == "implement"
    assert "CQRS" in loaded_features["related_patterns"]
    assert "fastapi" in loaded_features["project_context"]["framework"]

    print("✓ 测试4通过：特征列表工作正常")


def test_memory_layer_state_management():
    """测试记忆层状态管理"""
    print("\n" + "=" * 60)
    print("测试5：记忆层状态管理")
    print("=" * 60)

    memory = MemoryLayer()

    task_id = "test_state_management"
    test_state = {
        "task_id": task_id,
        "description": "测试状态管理",
        "status": "in_progress",
        "current_subtask_index": 1,
        "subtasks": [
            {"sub_task_id": "s1", "description": "子任务1", "status": "completed"},
            {"sub_task_id": "s2", "description": "子任务2", "status": "pending"},
        ],
        "results": [],
    }

    memory.save_task_state(task_id, test_state)

    loaded_state = memory.get_task_state(task_id)
    print(f"保存并加载的状态: {loaded_state}")

    assert loaded_state is not None
    assert loaded_state["current_subtask_index"] == 1

    restored = memory.restore_task_state(task_id)
    print(f"恢复的状态: {restored}")

    assert restored is not None

    memory._state_persistence.delete_task_state(task_id)

    print("✓ 测试5通过：记忆层状态管理工作正常")


def test_harness_state_persistence():
    """测试ConsciousnessHarness状态持久化"""
    print("\n" + "=" * 60)
    print("测试6：ConsciousnessHarness状态持久化")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    status = harness.status
    print(f"初始状态: {status}")

    harness.run("实现一个简单的Hello World函数", intent="implement")

    save_path = harness.save_state()
    print(f"状态保存路径: {save_path}")

    new_harness = ConsciousnessHarness(workdir=r"D:\LAAP")
    assert new_harness._task_history == []

    success = new_harness.load_state(save_path)
    print(f"状态加载成功: {success}")

    assert len(new_harness._task_history) == 1
    assert new_harness._task_history[0]["description"] == "实现一个简单的Hello World函数"

    print("✓ 测试6通过：ConsciousnessHarness状态持久化工作正常")


def test_task_restore():
    """测试任务恢复功能"""
    print("\n" + "=" * 60)
    print("测试7：任务恢复功能")
    print("=" * 60)

    harness = ConsciousnessHarness(workdir=r"D:\LAAP")

    task_id = "test_restore_task"
    test_state = {
        "task_id": task_id,
        "description": "测试任务恢复",
        "status": "in_progress",
        "current_subtask_index": 1,
        "subtasks": [
            {
                "sub_task_id": "test_restore_task_1",
                "description": "分析需求",
                "status": "completed",
                "estimated_lines": 30,
                "dependencies": [],
            },
            {
                "sub_task_id": "test_restore_task_2",
                "description": "设计接口",
                "status": "pending",
                "estimated_lines": 60,
                "dependencies": ["test_restore_task_1"],
            },
            {
                "sub_task_id": "test_restore_task_3",
                "description": "实现功能",
                "status": "pending",
                "estimated_lines": 100,
                "dependencies": ["test_restore_task_2"],
            },
        ],
        "results": [
            {
                "subtask": "分析需求",
                "sub_task_id": "test_restore_task_1",
                "status": "completed",
                "duration_ms": 100.0,
                "feedback": {"corrected": False, "corrections": []},
            },
        ],
    }

    harness.memory_layer.save_task_state(task_id, test_state)

    result = harness.restore_task(task_id)
    print(f"任务恢复结果: {result}")

    assert result is not None
    assert result["status"] == "success" or result["status"] == "partial"
    assert result["restored_from_index"] == 1

    harness.delete_task_state(task_id)

    print("✓ 测试7通过：任务恢复功能工作正常")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("跨会话状态工程测试套件")
    print("=" * 60)

    tests = [
        test_three_layer_memory,
        test_context_compression,
        test_task_state_persistence,
        test_feature_list,
        test_memory_layer_state_management,
        test_harness_state_persistence,
        test_task_restore,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ 测试失败: {test.__name__}")
            print(f"  错误: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ 测试异常: {test.__name__}")
            print(f"  异常: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
