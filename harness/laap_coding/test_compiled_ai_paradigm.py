#!/usr/bin/env python
"""
测试编译式AI范式三大核心组件
==================================
1. CognitiveSpeciesLibrary - 认知物种库
2. EvolutionaryCompiler - 进化编译器
3. PsiNetConnector - Ψ-Net连接器
4. ConsciousnessHarness集成测试
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from laap_coding.core.cognitive_species_library import CognitiveSpeciesLibrary, SpeciesType, SpeciesOrigin
from laap_coding.core.evolutionary_compiler import EvolutionaryCompiler
from laap_coding.core.psi_net_connector import PsiNetConnector, MessageType, EventPriority
from laap_coding.core.harness import ConsciousnessHarness


def test_cognitive_species_library():
    """测试认知物种库"""
    print("\n" + "="*60)
    print("测试 1: CognitiveSpeciesLibrary")
    print("="*60)

    lib = CognitiveSpeciesLibrary()
    assert lib is not None, "物种库初始化失败"
    print("✓ 物种库初始化成功")

    species1 = lib.register_compiled_species(
        template="button",
        props={"label": "Submit", "color": "primary"},
        tags=["ui", "component"],
        domain=["frontend"],
    )
    assert species1 is not None, "注册物种失败"
    assert species1.type == SpeciesType.COMPONENT, "物种类型不正确"
    print("✓ 注册组件物种成功")

    species2 = lib.register_compiled_species(
        template="api_service",
        props={"endpoint": "/users", "method": "GET"},
        tags=["backend", "api"],
        domain=["backend"],
    )
    assert species2.type == SpeciesType.SKILL, "物种类型推断不正确"
    print("✓ 注册技能物种成功")

    species3 = lib.register_compiled_species(
        template="data_processing",
        props={"algorithm": "sort", "parallel": True},
        tags=["data"],
        domain=["ml"],
    )
    assert species3.type == SpeciesType.ABILITY, "物种类型推断不正确"
    print("✓ 注册能力物种成功")

    found = lib.get_species(species1.id)
    assert found is not None, "获取物种失败"
    assert found.name == species1.name, "获取的物种不正确"
    print("✓ 获取物种成功")

    all_species = lib.list_species()
    assert len(all_species) >= 3, "列出物种数量不正确"
    print("✓ 列出物种成功")

    by_type = lib.list_species(type_filter="component")
    assert len(by_type) >= 1, "按类型筛选失败"
    print("✓ 按类型筛选物种成功")

    searched = lib.search_species("button")
    assert len(searched) >= 1, "搜索物种失败"
    print("✓ 搜索物种成功")

    evolved = lib.evolve_species(species1.id, "button_improved", {"label": "Submit", "color": "primary", "size": "large"})
    assert evolved is not None, "进化物种失败"
    assert evolved.origin == SpeciesOrigin.EVOLVED, "进化物种来源不正确"
    print("✓ 进化物种成功")

    merged = lib.merge_species([species1.id, species2.id])
    assert merged is not None, "合并物种失败"
    assert "merged" in merged.tags, "合并标签不正确"
    print("✓ 合并物种成功")

    stats = lib.get_stats()
    assert "total_species" in stats, "获取统计信息失败"
    print(f"✓ 统计信息: {stats['total_species']} 个物种")

    pruned = lib.prune_species(min_usage=0)
    print(f"✓ 清理物种: 移除 {pruned} 个")

    print("\n" + "="*60)
    print("测试 1 完成: CognitiveSpeciesLibrary ✓")
    print("="*60)


def test_evolutionary_compiler():
    """测试进化编译器"""
    print("\n" + "="*60)
    print("测试 2: EvolutionaryCompiler")
    print("="*60)

    lib = CognitiveSpeciesLibrary()
    compiler = EvolutionaryCompiler(lib)
    assert compiler is not None, "进化编译器初始化失败"
    print("✓ 进化编译器初始化成功")

    result = compiler.compile("create_button", {"label": "Test", "color": "blue"})
    assert result is not None, "编译失败"
    assert result.status.value == "success", "编译状态不正确"
    print("✓ 编译意图成功")

    result2 = compiler.compile("create_api", {"endpoint": "/test"})
    assert result2.status.value == "success", "第二次编译失败"
    print("✓ 第二次编译成功")

    stats = compiler.get_pattern_stats()
    assert "total_patterns" in stats, "获取模式统计失败"
    assert stats["total_patterns"] >= 2, "模式数量不足"
    print(f"✓ 模式统计: {stats['total_patterns']} 个模式")

    compiler.run_evolution_cycle()
    print("✓ 进化循环运行成功")

    print("\n" + "="*60)
    print("测试 2 完成: EvolutionaryCompiler ✓")
    print("="*60)


def test_psi_net_connector():
    """测试Ψ-Net连接器"""
    print("\n" + "="*60)
    print("测试 3: PsiNetConnector")
    print("="*60)

    connector = PsiNetConnector()
    assert connector is not None, "Ψ-Net连接器初始化失败"
    assert connector.instance_id is not None, "实例ID为空"
    print(f"✓ Ψ-Net连接器初始化成功: instance_id={connector.instance_id}")

    connector.start()
    time.sleep(0.5)
    print("✓ Ψ-Net启动成功")

    stats = connector.get_stats()
    assert "instance_id" in stats, "获取统计信息失败"
    assert stats["peers"] == 0, "初始节点数量不正确"
    print("✓ 获取统计信息成功")

    connector.send_causal_rule({"name": "test_rule", "conditions": ["test"]})
    print("✓ 发送因果规则成功")

    connector.send_species_update({"name": "test_species", "type": "component"})
    print("✓ 发送物种更新成功")

    connector.send_compilation_result({"task_id": "test", "status": "success"})
    print("✓ 发送编译结果成功")

    connector.stop()
    print("✓ Ψ-Net停止成功")

    print("\n" + "="*60)
    print("测试 3 完成: PsiNetConnector ✓")
    print("="*60)


def test_psi_net_bidirectional():
    """测试Ψ-Net双实例通信"""
    print("\n" + "="*60)
    print("测试 3.1: PsiNetConnector双实例通信")
    print("="*60)

    connector1 = PsiNetConnector(port=11551)
    connector2 = PsiNetConnector(port=11552)
    assert connector1 is not None, "连接器1初始化失败"
    assert connector2 is not None, "连接器2初始化失败"
    print(f"✓ 双连接器初始化成功: {connector1.instance_id} ↔ {connector2.instance_id}")

    connector1.start()
    connector2.start()
    time.sleep(1.0)
    print("✓ 双连接器启动成功")

    messages_received = []
    def handler(msg):
        messages_received.append(msg)
        print(f"  ← 收到消息: {msg.type.value} from {msg.sender}")

    connector2.register_handler("causal_rule", handler)
    connector2.register_handler("species_update", handler)

    connected = connector1.connect_to_peer("localhost", 11552)
    assert connected, "连接到对等节点失败"
    print("✓ 点对点连接成功")

    time.sleep(1.0)
    connector1.send_causal_rule({"name": "cross_instance_test", "conditions": ["peer_connected"], "action": "sync_species"})
    print("✓ 发送跨实例因果规则")

    time.sleep(2.0)
    assert len(messages_received) >= 1, "未收到跨实例消息"
    received_rule = messages_received[0]
    assert received_rule.type.value == "causal_rule", "消息类型不正确"
    assert received_rule.payload.get("name") == "cross_instance_test", "消息内容不正确"
    assert received_rule.sender == connector1.instance_id, "消息发送者不正确"
    print("✓ 跨实例因果规则传递成功")

    connector1.send_species_update({"name": "shared_species", "type": "skill", "origin": "compiled"})
    time.sleep(1.0)
    species_messages = [m for m in messages_received if m.type.value == "species_update"]
    assert len(species_messages) >= 1, "未收到物种更新消息"
    print("✓ 跨实例物种更新传递成功")

    stats1 = connector1.get_stats()
    stats2 = connector2.get_stats()
    assert stats1["peers"] == 1, "连接器1节点数不正确"
    assert stats2["received_messages"] >= 2, "连接器2接收消息数不足"
    print("✓ 统计信息验证通过")

    connector1.stop()
    connector2.stop()
    print("✓ 双连接器停止成功")

    print("\n" + "="*60)
    print("测试 3.1 完成: PsiNetConnector双实例通信 ✓")
    print("="*60)


def test_harness_integration():
    """测试ConsciousnessHarness集成"""
    print("\n" + "="*60)
    print("测试 4: ConsciousnessHarness集成编译式AI范式")
    print("="*60)

    harness = ConsciousnessHarness()
    assert harness is not None, "Harness初始化失败"
    print("✓ ConsciousnessHarness初始化成功")

    assert harness.species_library is not None, "物种库未集成"
    print("✓ CognitiveSpeciesLibrary集成成功")

    assert harness.evolutionary_compiler is not None, "进化编译器未集成"
    print("✓ EvolutionaryCompiler集成成功")

    assert harness.psi_net is not None, "Ψ-Net连接器未集成"
    print("✓ PsiNetConnector集成成功")

    result = harness.compile("create_landing_page", {"theme": "dark", "sections": ["hero", "features"]})
    assert result is not None, "编译方法失败"
    assert "status" in result, "编译结果格式不正确"
    print("✓ compile()方法成功")

    species = harness.register_species("test_component", {"props": {"test": True}}, tags=["test"])
    assert species is not None, "注册物种方法失败"
    assert "id" in species, "物种注册结果缺少id字段"
    assert "name" in species, "物种注册结果缺少name字段"
    print("✓ register_species()方法成功")

    rule_result = harness.send_causal_rule({"name": "integration_test"})
    assert rule_result is not None, "发送因果规则方法失败"
    assert rule_result["status"] == "success", "发送因果规则失败"
    print("✓ send_causal_rule()方法成功")

    psi_start = harness.start_psi_net()
    assert psi_start is not None, "启动Ψ-Net方法失败"
    assert psi_start["status"] == "success", "启动Ψ-Net失败"
    print("✓ start_psi_net()方法成功")

    status = harness.status
    assert "compiled_ai_paradigm" in status, "状态中缺少编译式AI范式信息"
    assert "species_library" in status["compiled_ai_paradigm"], "状态中缺少物种库信息"
    assert "evolutionary_compiler" in status["compiled_ai_paradigm"], "状态中缺少进化编译器信息"
    assert "psi_net" in status["compiled_ai_paradigm"], "状态中缺少Ψ-Net信息"
    print("✓ status属性包含编译式AI范式组件状态")

    print("\n" + "="*60)
    print("测试 4 完成: ConsciousnessHarness集成 ✓")
    print("="*60)


def test_rate_buffer():
    """测试频率缓冲器"""
    print("\n" + "="*60)
    print("测试 5: RateBuffer频率缓冲")
    print("="*60)

    from laap_coding.core.psi_net_connector import RateBuffer, PsiMessage

    buffer = RateBuffer(max_events_per_second=2.0)
    assert buffer is not None, "RateBuffer初始化失败"
    print("✓ RateBuffer初始化成功")

    messages = []
    for i in range(10):
        msg = PsiMessage(
            type=MessageType.PING,
            sender="test",
            timestamp=time.time(),
            payload={"index": i},
        )
        buffer.add(msg)
        messages.append(msg)

    assert buffer.get_size() == 10, "缓冲大小不正确"
    print("✓ 添加消息到缓冲成功")

    time.sleep(1.0)
    flushed = buffer.flush()
    assert len(flushed) >= 2, "刷新缓冲失败"
    print(f"✓ 刷新缓冲: 输出 {len(flushed)} 条消息")

    print("\n" + "="*60)
    print("测试 5 完成: RateBuffer ✓")
    print("="*60)


def main():
    """运行所有测试"""
    print("="*60)
    print("编译式AI范式测试套件")
    print("="*60)

    try:
        test_cognitive_species_library()
        test_evolutionary_compiler()
        test_psi_net_connector()
        test_psi_net_bidirectional()
        test_harness_integration()
        test_rate_buffer()

        print("\n" + "="*60)
        print("所有测试通过! ✓")
        print("="*60)
        return 0
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
