"""
规划引擎测试脚本

验证FR-2和Task 3的实现：
1. 任务分解算法：复杂任务拆分为多个子任务（每个子任务≤200行变更）
2. 依赖图生成器：确定子任务执行顺序
3. 不同类型任务的规划策略（implement/fix/review/test/refactor/deploy）
4. 架构模式库集成：根据推荐模式调整子任务规划
5. TaskBoard集成：任务自动注册和状态同步

测试用例：
- TR-3.1: 复杂任务（如"实现博客CRUD系统"）被分解为≥5个独立子任务
- TR-3.2: 依赖图正确反映子任务间的依赖关系
- TR-3.3: 每个子任务的预估代码量≤200行
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from harness.laap_coding.core.harness import (
    PlanningEngine,
    DependencyGraph,
    SubTaskGranularityControl,
    TaskContext,
    MemoryLayer,
    PerceptionLayer,
    ReasoningLayer,
    ConsciousnessHarness,
)

try:
    from laap.agi.multi_agent import TaskBoard
except ImportError:
    TaskBoard = None


def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def test_dependency_graph_basic():
    """测试依赖图基本功能"""
    print_header("测试1：依赖图基本功能")

    graph = DependencyGraph()

    task1 = TaskContext(task_id="t1", description="任务1", intent="implement", keywords=[], constraints=[], related_patterns=[], project_context={})
    task2 = TaskContext(task_id="t2", description="任务2", intent="implement", keywords=[], constraints=[], related_patterns=[], project_context={})
    task3 = TaskContext(task_id="t3", description="任务3", intent="implement", keywords=[], constraints=[], related_patterns=[], project_context={})

    from harness.laap_coding.core.harness import SubTask
    subtask1 = SubTask(sub_task_id="t1_1", parent_task_id="t1", description="子任务1", files=[], estimated_lines=50, dependencies=[])
    subtask2 = SubTask(sub_task_id="t1_2", parent_task_id="t1", description="子任务2", files=[], estimated_lines=60, dependencies=["t1_1"])
    subtask3 = SubTask(sub_task_id="t1_3", parent_task_id="t1", description="子任务3", files=[], estimated_lines=40, dependencies=["t1_2"])

    graph.add_node(subtask1)
    graph.add_node(subtask2)
    graph.add_node(subtask3)
    graph.add_dependency("t1_1", "t1_2")
    graph.add_dependency("t1_2", "t1_3")

    print(f"  节点数: {len(graph._nodes)}")
    print(f"  边数: {sum(len(v) for v in graph._edges.values())}")

    sorted_ids = graph.topological_sort()
    print(f"  拓扑排序: {sorted_ids}")

    assert sorted_ids == ["t1_1", "t1_2", "t1_3"], f"期望排序 [t1_1, t1_2, t1_3], 实际: {sorted_ids}"

    independent = graph.get_independent_tasks()
    print(f"  独立任务: {independent}")
    assert independent == ["t1_1"], f"期望独立任务 [t1_1], 实际: {independent}"

    cycles = graph.detect_cycles()
    print(f"  循环依赖: {cycles}")
    assert len(cycles) == 0, f"不应有循环依赖"

    print("  ✅ 依赖图基本功能测试通过")


def test_dependency_graph_cycle_detection():
    """测试循环依赖检测"""
    print_header("测试2：循环依赖检测")

    graph = DependencyGraph()

    from harness.laap_coding.core.harness import SubTask
    subtask1 = SubTask(sub_task_id="t1_1", parent_task_id="t1", description="子任务1", files=[], estimated_lines=50, dependencies=["t1_3"])
    subtask2 = SubTask(sub_task_id="t1_2", parent_task_id="t1", description="子任务2", files=[], estimated_lines=60, dependencies=["t1_1"])
    subtask3 = SubTask(sub_task_id="t1_3", parent_task_id="t1", description="子任务3", files=[], estimated_lines=40, dependencies=["t1_2"])

    graph.add_node(subtask1)
    graph.add_node(subtask2)
    graph.add_node(subtask3)
    graph.add_dependency("t1_3", "t1_1")
    graph.add_dependency("t1_1", "t1_2")
    graph.add_dependency("t1_2", "t1_3")

    cycles = graph.detect_cycles()
    print(f"  检测到的循环: {cycles}")
    assert len(cycles) > 0, "应检测到循环依赖"

    try:
        graph.topological_sort()
        assert False, "应抛出循环依赖异常"
    except ValueError as e:
        print(f"  异常捕获: {e}")
        assert "循环依赖" in str(e)

    print("  ✅ 循环依赖检测测试通过")


def test_subtask_granularity_control():
    """测试子任务粒度控制"""
    print_header("测试3：子任务粒度控制")

    granularity = SubTaskGranularityControl()

    test_cases = [
        ("实现一个简单的计算器", "implement", 100),
        ("实现一个复杂的CRUD系统", "implement", 150),
        ("修复登录功能的bug", "fix", 30),
        ("审查项目中的安全漏洞", "review", 10),
        ("编写单元测试", "test", 60),
        ("重构整个代码库", "refactor", 120),
        ("部署应用到生产环境", "deploy", 20),
    ]

    for description, intent, expected_range in test_cases:
        estimated = granularity.estimate_lines(description, intent)
        print(f"  '{description}' ({intent}): 预估 {estimated} 行")
        assert estimated > 0, "预估行数应为正数"

    subtask = type('SubTask', (), {
        'sub_task_id': 'test_1',
        'parent_task_id': 'test',
        'description': '测试任务',
        'files': [],
        'estimated_lines': 350,
        'dependencies': [],
        'status': 'pending',
    })

    split_result = granularity.split_task(subtask)
    print(f"\n  拆分测试 (350行 → {len(split_result)}个子任务):")
    for st in split_result:
        print(f"    - {st.sub_task_id}: {st.estimated_lines}行, 依赖: {st.dependencies}")

    assert len(split_result) == 2, f"期望拆分为2个子任务, 实际: {len(split_result)}"
    assert all(st.estimated_lines <= 200 for st in split_result), "所有子任务应≤200行"

    validation = granularity.validate_granularity(split_result)
    print(f"  粒度验证: valid={validation['valid']}, issues={len(validation['issues'])}, warnings={len(validation['warnings'])}")
    assert validation['valid'] == True, "粒度验证应通过"

    print("  ✅ 子任务粒度控制测试通过")


def test_planning_engine_crud_system():
    """测试CRUD系统规划（核心测试用例）"""
    print_header("测试4：CRUD系统规划（核心测试）")

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)

    context = perception.perceive("实现博客CRUD系统")
    print(f"  任务描述: {context.description}")
    print(f"  意图: {context.intent}")
    print(f"  关键词: {context.keywords}")
    print(f"  相关模式: {context.related_patterns}")

    planner = PlanningEngine(memory_layer=memory)
    subtasks = planner.plan(context)

    print(f"\n  生成的子任务数量: {len(subtasks)}")

    assert len(subtasks) >= 5, f"期望至少5个子任务, 实际: {len(subtasks)}"

    print(f"\n  子任务详情:")
    for i, st in enumerate(subtasks):
        print(f"    {i+1}. [{st.sub_task_id}] {st.description}")
        print(f"       预估行数: {st.estimated_lines}, 依赖: {st.dependencies}, 文件: {st.files}")

    for st in subtasks:
        assert st.estimated_lines <= 200, f"子任务 {st.sub_task_id} 预估行数 {st.estimated_lines} > 200"

    graph = DependencyGraph()
    graph.build_from_subtasks(subtasks)

    sorted_subtasks = graph.get_sorted_subtasks()
    print(f"\n  执行顺序:")
    for st in sorted_subtasks:
        print(f"    - {st.sub_task_id}: {st.description}")

    cycles = graph.detect_cycles()
    assert len(cycles) == 0, f"不应有循环依赖: {cycles}"

    print("  ✅ CRUD系统规划测试通过")


def test_planning_engine_different_intents():
    """测试不同类型任务的规划策略"""
    print_header("测试5：不同类型任务的规划策略")

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory_layer=memory)

    test_cases = [
        ("实现用户认证系统", "implement"),
        ("修复API响应时间过长的问题", "fix"),
        ("审查支付模块的安全漏洞", "review"),
        ("为订单模块编写单元测试", "test"),
        ("重构用户模块代码", "refactor"),
        ("部署应用到测试环境", "deploy"),
    ]

    for description, intent in test_cases:
        context = perception.perceive(description)
        context.intent = intent

        subtasks = planner.plan(context)

        print(f"\n  {intent}: '{description}'")
        print(f"    子任务数: {len(subtasks)}")
        for st in subtasks:
            print(f"      - {st.description} ({st.estimated_lines}行)")

        assert len(subtasks) > 0, f"{intent} 任务应生成至少1个子任务"
        for st in subtasks:
            assert st.estimated_lines <= 200, f"子任务预估行数 {st.estimated_lines} > 200"

    print("\n  ✅ 不同类型任务规划策略测试通过")


def test_planning_engine_with_dependency_graph():
    """测试规划引擎与依赖图集成"""
    print_header("测试6：规划引擎与依赖图集成")

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory_layer=memory)

    context = perception.perceive("实现RESTful API系统")
    result = planner.plan_with_dependency_graph(context)

    print(f"  子任务数: {len(result['subtasks'])}")
    print(f"  执行顺序: {result['execution_order']}")
    print(f"  独立任务: {result['independent_tasks']}")
    print(f"  循环依赖: {result['cycles']}")

    assert len(result['subtasks']) == len(result['execution_order']), "子任务数应等于执行顺序长度"
    assert len(result['cycles']) == 0, "不应有循环依赖"

    print("  ✅ 规划引擎与依赖图集成测试通过")


def test_planning_engine_architecture_patterns():
    """测试架构模式库集成"""
    print_header("测试7：架构模式库集成")

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    planner = PlanningEngine(memory_layer=memory)

    context = perception.perceive("实现一个高并发的命令查询分离系统")
    context.related_patterns = ["CQRS", "Repository Pattern"]

    print(f"  相关模式: {context.related_patterns}")

    subtasks = planner.plan(context)
    print(f"  子任务数: {len(subtasks)}")

    for st in subtasks:
        print(f"    - {st.sub_task_id}: {st.description}, 依赖: {st.dependencies}")

    assert len(subtasks) >= 5, "应生成至少5个子任务"

    print("  ✅ 架构模式库集成测试通过")


def test_task_board_integration():
    """测试TaskBoard集成"""
    print_header("测试8：TaskBoard集成")

    if TaskBoard is None:
        print("  ⚠️ TaskBoard未安装，跳过此测试")
        return

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    task_board = TaskBoard()
    planner = PlanningEngine(memory_layer=memory, task_board=task_board)

    initial_tasks = len(task_board.tasks)
    print(f"  初始任务数: {initial_tasks}")

    context = perception.perceive("实现简单的计算器功能")
    subtasks = planner.plan(context)

    final_tasks = len(task_board.tasks)
    print(f"  规划后任务数: {final_tasks}")
    print(f"  新增任务数: {final_tasks - initial_tasks}")

    assert final_tasks > initial_tasks, "规划后应在TaskBoard中注册新任务"

    planner.update_subtask_status(subtasks[0].sub_task_id, "active")
    print(f"  更新任务状态后:")
    for task_id, task in task_board.tasks.items():
        print(f"    {task_id}: {task.description} - {task.status}")

    print("  ✅ TaskBoard集成测试通过")


def test_reasoning_layer_enhanced():
    """测试增强的推理层"""
    print_header("测试9：增强的推理层")

    memory = MemoryLayer()
    perception = PerceptionLayer(memory)
    reasoning = ReasoningLayer(memory_layer=memory)

    context = perception.perceive("实现用户管理系统")

    subtasks = reasoning.reason(context)
    print(f"  reason() 返回子任务数: {len(subtasks)}")
    assert len(subtasks) >= 5, "应生成至少5个子任务"

    result = reasoning.reason_with_graph(context)
    print(f"  reason_with_graph() 返回:")
    print(f"    子任务数: {len(result['subtasks'])}")
    print(f"    执行顺序: {result['execution_order']}")
    print(f"    依赖图: {result['dependency_graph']}")

    assert "dependency_graph" in result
    assert "execution_order" in result
    assert "independent_tasks" in result

    print("  ✅ 增强的推理层测试通过")


def test_consciousness_harness_planning():
    """测试ConsciousnessHarness规划功能"""
    print_header("测试10：ConsciousnessHarness规划功能")

    harness = ConsciousnessHarness(workdir=".")

    context = harness.perceive("实现博客CRUD系统")
    plan = harness.reason(context)

    print(f"  任务描述: {context.description}")
    print(f"  意图: {context.intent}")
    print(f"  生成子任务数: {len(plan)}")

    assert len(plan) >= 5, "应生成至少5个子任务"

    for st in plan:
        assert st.estimated_lines <= 200, f"子任务预估行数 {st.estimated_lines} > 200"

    print(f"\n  子任务列表:")
    for i, st in enumerate(plan):
        print(f"    {i+1}. {st.description} ({st.estimated_lines}行)")

    print("  ✅ ConsciousnessHarness规划功能测试通过")


def main():
    """运行所有测试"""
    print("🧠 LAAP 规划引擎测试套件")
    print("="*70)

    tests = [
        test_dependency_graph_basic,
        test_dependency_graph_cycle_detection,
        test_subtask_granularity_control,
        test_planning_engine_crud_system,
        test_planning_engine_different_intents,
        test_planning_engine_with_dependency_graph,
        test_planning_engine_architecture_patterns,
        test_task_board_integration,
        test_reasoning_layer_enhanced,
        test_consciousness_harness_planning,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n  ✗ 测试失败: {test.__name__}")
            print(f"    错误: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  ✗ 测试异常: {test.__name__}")
            print(f"    异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("="*70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()