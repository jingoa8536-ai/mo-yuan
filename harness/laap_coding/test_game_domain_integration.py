"""
游戏领域集成测试套件 — 覆盖所有新增功能模块

测试范围：
1. 游戏风格兼容性映射系统 (game_style_compat.py)
2. Godot资源自动生成器 (godot_resource_generator.py)
3. 信号连接管理器 (signal_connector.py)
4. 数据库扩展验证 (laap_harness_database.json)
5. 匹配引擎游戏风格扩展 (matching_engine.py)
"""
import sys
import os
sys.path.insert(0, 'core')

from game_style_compat import GameStyleCompatibilityMap
from godot_resource_generator import (
    GodotResourceGenerator,
    TSCNGenerator,
    TRESGenerator,
    GDScriptGenerator
)
from signal_connector import SignalConnector, GodotSignalConnector, SignalConnection
from matching_engine import MatchingEngine
import json

passed = 0
failed = 0
failures = []


def test(name, condition, message=""):
    global passed, failed, failures
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        failures.append(f"❌ {name}: {message}")
        print(f"  ❌ {name}: {message}")


def run_all_tests():
    global passed, failed, failures
    
    print("\n" + "=" * 80)
    print("游戏领域集成测试套件")
    print("=" * 80)
    
    test_game_style_compatibility()
    test_godot_resource_generator()
    test_signal_connector()
    test_database_extension()
    test_matching_engine_extension()
    
    print("\n" + "=" * 80)
    print(f"测试结果: {passed} 通过 / {failed} 失败")
    print("=" * 80)
    
    if failures:
        print("\n失败详情:")
        for failure in failures:
            print(f"  {failure}")
    
    return failed == 0


def test_game_style_compatibility():
    print("\n【测试组 1】游戏风格兼容性映射系统")
    print("-" * 60)
    
    gsc = GameStyleCompatibilityMap()
    
    test("GameStyleCompatibilityMap 实例化成功", gsc is not None, "实例化失败")
    
    test("DEFAULT_SIMILARITY_MAP 包含8种游戏风格", 
         len(gsc.DEFAULT_SIMILARITY_MAP) == 8,
         f"实际包含 {len(gsc.DEFAULT_SIMILARITY_MAP)} 种风格")
    
    expected_styles = ["racing-game", "sports-game", "simulation", "arcade", 
                       "action", "rpg", "strategy", "godot-native"]
    for style in expected_styles:
        test(f"风格 {style} 存在于 DEFAULT_SIMILARITY_MAP", 
             style in gsc.DEFAULT_SIMILARITY_MAP,
             f"风格 {style} 不存在")
    
    test("racing-game 与 racing-game 相似度为1.0",
         gsc.get_style_similarity("racing-game", "racing-game") == 1.0,
         "相似度计算错误")
    
    test("racing-game 与 sports-game 相似度 > 0.8",
         gsc.get_style_similarity("racing-game", "sports-game") > 0.8,
         "相似度计算错误")
    
    test("racing-game 与 strategy 相似度 < 0.5",
         gsc.get_style_similarity("racing-game", "strategy") < 0.5,
         "相似度计算错误")
    
    compatible = gsc.get_compatible_styles("racing-game", threshold=0.7)
    test("racing-game 兼容风格数量 > 2", len(compatible) > 2, "兼容风格数量不足")
    
    test("STYLE_CATEGORIES 非空", len(gsc.STYLE_CATEGORIES) > 0, "STYLE_CATEGORIES 为空")
    
    test("COMPONENT_STYLE_MAPPING 非空", len(gsc.COMPONENT_STYLE_MAPPING) > 0, "COMPONENT_STYLE_MAPPING 为空")
    
    score = gsc.calculate_component_style_score("racing_game_v1", "racing-game")
    test("组件 racing_game_v1 与 racing-game 风格得分 > 0.8",
         score > 0.8, f"得分: {score}")
    
    score = gsc.calculate_component_style_score("rpg_framework", "racing-game")
    test("组件 rpg_framework 与 racing-game 风格得分 < 0.5",
         score < 0.5, f"得分: {score}")


def test_godot_resource_generator():
    print("\n【测试组 2】Godot资源自动生成器")
    print("-" * 60)
    
    tscn_mapping = {
        "nodes": [
            {
                "type": "AudioStreamPlayer3D",
                "name": "EngineSound3D",
                "parent": ".",
                "properties": {
                    "stream": "res://audio/samples/engine.ogg",
                    "autoplay": False,
                    "max_distance": 100.0
                }
            }
        ]
    }
    tscn_content = TSCNGenerator.generate(tscn_mapping)
    
    test("TSCNGenerator 生成内容非空", len(tscn_content) > 0, "生成内容为空")
    test("TSCNGenerator 生成内容包含 [gd_scene", "[gd_scene" in tscn_content, "缺少 [gd_scene] 标记")
    test("TSCNGenerator 生成内容包含 AudioStreamPlayer3D", "AudioStreamPlayer3D" in tscn_content, "缺少节点类型")
    test("TSCNGenerator 生成内容包含 EngineSound3D", "EngineSound3D" in tscn_content, "缺少节点名称")
    
    tres_mapping = {
        "type": "AudioBusLayout",
        "properties": {
            "buses": [
                {"name": "Master", "mute": False, "volume_db": 0}
            ]
        }
    }
    tres_content = TRESGenerator.generate(tres_mapping)
    
    test("TRESGenerator 生成内容非空", len(tres_content) > 0, "生成内容为空")
    test("TRESGenerator 生成内容包含 [gd_resource", "[gd_resource" in tres_content, "缺少 [gd_resource] 标记")
    test("TRESGenerator 生成内容包含 AudioBusLayout", "AudioBusLayout" in tres_content, "缺少资源类型")
    
    gd_mapping = {
        "class_name": "EngineSoundController",
        "extends": "Node3D",
        "exports": [
            {"name": "rpm_min", "type": "float", "default": 1000.0}
        ],
        "methods": [
            {"name": "update_engine", "params": ["rpm: float"], "return": "void"}
        ]
    }
    gd_content = GDScriptGenerator.generate(gd_mapping)
    
    test("GDScriptGenerator 生成内容非空", len(gd_content) > 0, "生成内容为空")
    test("GDScriptGenerator 生成内容包含 class_name", "class_name" in gd_content, "缺少 class_name")
    test("GDScriptGenerator 生成内容包含 extends", "extends" in gd_content, "缺少 extends")
    test("GDScriptGenerator 生成内容包含 @export", "@export" in gd_content, "缺少 @export")
    test("GDScriptGenerator 生成内容包含 func", "func" in gd_content, "缺少 func")
    
    generator = GodotResourceGenerator(output_dir="test_output")
    test("GodotResourceGenerator 实例化成功", generator is not None, "实例化失败")
    
    test_mapping = {
        "component_uri": "test_component",
        "target_resources": [
            {
                "type": "AudioStreamPlayer3D",
                "name": "TestPlayer",
                "path": "scenes/test_player.tscn",
                "properties": {"autoplay": False}
            }
        ],
        "target_scripts": [
            {
                "class_name": "TestScript",
                "extends": "Node",
                "path": "scripts/test_script.gd"
            }
        ]
    }
    
    generated_files = generator.generate_from_mapping(test_mapping)
    test("generate_from_mapping 生成文件数量 > 0", len(generated_files) > 0, "未生成任何文件")
    
    for filepath in generated_files:
        test(f"生成文件 {filepath} 存在", os.path.exists(filepath), f"文件不存在: {filepath}")
    
    import shutil
    if os.path.exists("test_output"):
        shutil.rmtree("test_output")


def test_signal_connector():
    print("\n【测试组 3】信号连接管理器")
    print("-" * 60)
    
    connector = SignalConnector()
    test("SignalConnector 实例化成功", connector is not None, "实例化失败")
    
    test_steps = [
        "连接 PhysicsVehicle 的 update_engine(rpm, throttle, speed) 信号到 EngineSoundController.update_engine",
        "连接 useRaceState.lapComplete 信号到 GhostRecorder.finish_lap"
    ]
    
    connections = connector.parse_assembly_steps(test_steps)
    test("parse_assembly_steps 解析出 2 个连接", len(connections) == 2, f"解析出 {len(connections)} 个连接")
    
    test("第一个连接 source_node 为 PhysicsVehicle", 
         connections[0].source_node == "PhysicsVehicle",
         f"source_node: {connections[0].source_node}")
    
    test("第一个连接 source_signal 为 update_engine", 
         connections[0].source_signal == "update_engine",
         f"source_signal: {connections[0].source_signal}")
    
    test("第一个连接 target_node 为 EngineSoundController", 
         connections[0].target_node == "EngineSoundController",
         f"target_node: {connections[0].target_node}")
    
    test("第一个连接 target_method 为 update_engine", 
         connections[0].target_method == "update_engine",
         f"target_method: {connections[0].target_method}")
    
    conn_ids = connector.register_connections(connections)
    test("register_connections 返回 2 个 ID", len(conn_ids) == 2, f"返回 {len(conn_ids)} 个 ID")
    
    test("连接 conn_0 注册成功", "conn_0" in connector.connections, "conn_0 未注册")
    test("连接 conn_1 注册成功", "conn_1" in connector.connections, "conn_1 未注册")
    
    status = connector.get_connection_status("conn_0")
    test("get_connection_status 返回正确的 connection_id", 
         status.get("connection_id") == "conn_0",
         f"connection_id: {status.get('connection_id')}")
    
    test("初始状态下连接未连接", 
         not status.get("connected", True),
         "初始状态应为未连接")
    
    connect_result = connector.connect("conn_0")
    test("connect 连接 conn_0 成功", connect_result is True, "连接失败")
    
    status_after = connector.get_connection_status("conn_0")
    test("连接后状态为已连接", 
         status_after.get("connected", False),
         "连接状态未更新")
    
    disconnect_result = connector.disconnect("conn_0")
    test("disconnect 断开 conn_0 成功", disconnect_result is True, "断开失败")
    
    connected_count = connector.connect_all()
    test("connect_all 连接所有信号", connected_count == 2, f"连接了 {connected_count} 个")
    
    summary = connector.get_status_summary()
    test("get_status_summary 返回 total_connections", 
         "total_connections" in summary, "缺少 total_connections")
    test("get_status_summary total_connections 为 2", 
         summary.get("total_connections") == 2,
         f"total_connections: {summary.get('total_connections')}")
    
    test("remove_connection 删除 conn_0 成功", 
         connector.remove_connection("conn_0"),
         "删除失败")
    
    test("conn_0 已被删除", 
         "conn_0" not in connector.connections,
         "conn_0 仍存在")
    
    connector.clear_all()
    test("clear_all 清空所有连接", 
         len(connector.connections) == 0,
         f"仍有 {len(connector.connections)} 个连接")
    
    godot_connector = GodotSignalConnector()
    test("GodotSignalConnector 实例化成功", godot_connector is not None, "实例化失败")
    
    rpc_result = godot_connector.connect_via_rpc("conn_0")
    test("connect_via_rpc 在无客户端时返回错误", 
         not rpc_result.get("success", True),
         "应返回错误")


def test_database_extension():
    print("\n【测试组 4】数据库扩展验证")
    print("-" * 60)
    
    db_path = os.path.join("core", "laap_harness_database.json")
    test("数据库文件存在", os.path.exists(db_path), f"文件不存在: {db_path}")
    
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    
    test("数据库包含 stats", "stats" in db, "缺少 stats")
    test("数据库包含 ui_libraries", "ui_libraries" in db, "缺少 ui_libraries")
    test("数据库包含 animation_libraries", "animation_libraries" in db, "缺少 animation_libraries")
    test("数据库包含 icon_libraries", "icon_libraries" in db, "缺少 icon_libraries")
    test("数据库包含 game_libraries", "game_libraries" in db, "缺少 game_libraries")
    
    game_libs = db.get("game_libraries", {})
    test("game_libraries 包含 5 个库", len(game_libs) == 5, f"实际包含 {len(game_libs)} 个库")
    
    expected_game_libs = ["racing_game_v1", "action_game_core", "rpg_framework", 
                          "strategy_game_engine", "godot_ai_framework"]
    for lib_id in expected_game_libs:
        test(f"游戏库 {lib_id} 存在", lib_id in game_libs, f"游戏库 {lib_id} 不存在")
    
    stats = db.get("stats", {})
    test("stats 包含 total_game_libraries", 
         "total_game_libraries" in stats,
         "缺少 total_game_libraries")
    test("total_game_libraries 为 5", 
         stats.get("total_game_libraries") == 5,
         f"total_game_libraries: {stats.get('total_game_libraries')}")
    
    test("total_libraries >= 36", 
         stats.get("total_libraries", 0) >= 36,
         f"total_libraries: {stats.get('total_libraries')}")
    
    indexes = db.get("indexes", {})
    tags = indexes.get("tags", {})
    test("tags 包含 game", "game" in tags, "缺少 game 标签")
    test("tags 包含 racing", "racing" in tags, "缺少 racing 标签")
    test("tags 包含 action", "action" in tags, "缺少 action 标签")
    test("tags 包含 rpg", "rpg" in tags, "缺少 rpg 标签")
    test("tags 包含 strategy", "strategy" in tags, "缺少 strategy 标签")
    
    domains = indexes.get("domains", {})
    test("domains 包含 game", "game" in domains, "缺少 game 领域")
    test("domains/game 包含游戏库", len(domains.get("game", [])) > 0, "game 领域为空")


def test_matching_engine_extension():
    print("\n【测试组 5】匹配引擎游戏风格扩展")
    print("-" * 60)
    
    me = MatchingEngine()
    test("MatchingEngine 实例化成功", me is not None, "实例化失败")
    
    style_map = me.STYLE_SIMILARITY_MAP
    
    test("STYLE_SIMILARITY_MAP 包含游戏风格", 
         "racing-game" in style_map,
         "STYLE_SIMILARITY_MAP 不包含 racing-game")
    
    test("STYLE_SIMILARITY_MAP 包含 godot-native", 
         "godot-native" in style_map,
         "STYLE_SIMILARITY_MAP 不包含 godot-native")
    
    racing_similarities = style_map.get("racing-game", {})
    test("racing-game 相似度映射非空", len(racing_similarities) > 0, "相似度映射为空")
    
    test("racing-game 与 racing-game 相似度为 1.0",
         racing_similarities.get("racing-game") == 1.0,
         f"相似度: {racing_similarities.get('racing-game')}")
    
    registry = me._build_component_registry()
    game_components = [c for c in registry if c.type == "game"]
    test("_build_component_registry 返回游戏类型组件", 
         len(game_components) > 0,
         f"游戏类型组件数量: {len(game_components)}")


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
