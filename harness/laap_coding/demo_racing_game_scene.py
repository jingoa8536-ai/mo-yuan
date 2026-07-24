#!/usr/bin/env python
"""
demo_racing_game_scene.py — 赛车游戏场景生成示例

使用 GodotResourceGenerator 生成一个完整的赛车游戏场景，包含：
1. 赛车车辆节点（PhysicsVehicle）
2. 引擎声音控制器（EngineSoundController）
3. 幽灵系统（GhostRecorder/GhostPlayer）
4. UI 动画控制器
5. 赛道相机
"""

import sys
sys.path.insert(0, 'core')

from godot_resource_generator import (
    GodotResourceGenerator,
    TSCNGenerator,
    TRESGenerator,
    GDScriptGenerator
)


def create_racing_game_scene():
    """创建赛车游戏场景配置"""
    return {
        "component_uri": "racing_game_v1",
        "target_resources": [
            {
                "type": "AudioStreamPlayer3D",
                "name": "EngineSound3D",
                "path": "scenes/racing/engine_sound.tscn",
                "properties": {
                    "stream": "res://audio/samples/engine.ogg",
                    "autoplay": False,
                    "max_distance": 100.0,
                    "bus": "Engine",
                    "attenuation_model": 2,
                    "doppler_tracking": 2
                }
            },
            {
                "type": "AudioStreamPlayer3D",
                "name": "SkidSound3D",
                "path": "scenes/racing/skid_sound.tscn",
                "properties": {
                    "stream": "res://audio/samples/skid.ogg",
                    "autoplay": False,
                    "max_distance": 80.0,
                    "bus": "SFX"
                }
            },
            {
                "type": "AnimationPlayer",
                "name": "UIAnimationPlayer",
                "path": "scenes/racing/ui_animations.tscn",
                "properties": {
                    "autoplay": False,
                    "active": True
                }
            },
            {
                "type": "Node3D",
                "name": "GhostRecorder",
                "path": "scenes/racing/ghost_recorder.tscn",
                "properties": {}
            },
            {
                "type": "Node3D",
                "name": "GhostPlayer",
                "path": "scenes/racing/ghost_player.tscn",
                "properties": {}
            },
            {
                "type": "Camera3D",
                "name": "RaceCamera",
                "path": "scenes/racing/race_camera.tscn",
                "properties": {
                    "current": True,
                    "fov": 60.0,
                    "near": 0.1,
                    "far": 200.0
                }
            },
            {
                "type": "AudioBusLayout",
                "name": "RaceAudioBusLayout",
                "path": "resources/audio/race_audio_bus.tres",
                "properties": {
                    "buses": [
                        {"name": "Master", "mute": False, "volume_db": 0},
                        {"name": "Engine", "mute": False, "volume_db": -3, "parent": "Master"},
                        {"name": "SFX", "mute": False, "volume_db": -2, "parent": "Master"},
                        {"name": "Music", "mute": False, "volume_db": -5, "parent": "Master"},
                        {"name": "UI", "mute": False, "volume_db": 0, "parent": "Master"}
                    ]
                }
            },
            {
                "type": "StandardMaterial3D",
                "name": "CarMaterial",
                "path": "resources/materials/car_material.tres",
                "properties": {
                    "albedo_color": "Color(0.2, 0.4, 0.8)",
                    "metallic": 0.8,
                    "roughness": 0.2,
                    "specular": 0.5
                }
            }
        ],
        "target_scripts": [
            {
                "class_name": "EngineSoundController",
                "extends": "Node3D",
                "path": "scripts/racing/engine_sound_controller.gd",
                "exports": [
                    {"name": "rpm_min", "type": "float", "default": 1000.0},
                    {"name": "rpm_max", "type": "float", "default": 9000.0},
                    {"name": "use_synth_fallback", "type": "bool", "default": False},
                    {"name": "volume_multiplier", "type": "float", "default": 1.0}
                ],
                "methods": [
                    {"name": "update_engine", "params": ["rpm: float", "throttle: float", "speed: float"], "return": "void", "notes": "更新引擎声音状态"},
                    {"name": "play_rev_sound", "params": [], "return": "void"},
                    {"name": "play_gear_shift", "params": ["new_gear: int"], "return": "void"},
                    {"name": "_ready", "params": [], "return": "void"},
                    {"name": "_process", "params": ["delta: float"], "return": "void"}
                ]
            },
            {
                "class_name": "PhysicsVehicle",
                "extends": "VehicleBody3D",
                "path": "scripts/racing/physics_vehicle.gd",
                "exports": [
                    {"name": "max_speed", "type": "float", "default": 300.0},
                    {"name": "acceleration", "type": "float", "default": 20.0},
                    {"name": "brake_force", "type": "float", "default": 30.0},
                    {"name": "steering_angle", "type": "float", "default": 0.5}
                ],
                "methods": [
                    {"name": "apply_throttle", "params": ["amount: float"], "return": "void"},
                    {"name": "apply_brake", "params": ["amount: float"], "return": "void"},
                    {"name": "steer", "params": ["angle: float"], "return": "void"},
                    {"name": "get_current_rpm", "params": [], "return": "float"},
                    {"name": "get_current_speed", "params": [], "return": "float"},
                    {"name": "_physics_process", "params": ["delta: float"], "return": "void"}
                ]
            },
            {
                "class_name": "GhostRecorder",
                "extends": "Node3D",
                "path": "scripts/racing/ghost_recorder.gd",
                "exports": [
                    {"name": "record_interval", "type": "float", "default": 0.05},
                    {"name": "max_record_time", "type": "float", "default": 600.0},
                    {"name": "is_recording", "type": "bool", "default": False}
                ],
                "methods": [
                    {"name": "start_recording", "params": [], "return": "void"},
                    {"name": "stop_recording", "params": [], "return": "void"},
                    {"name": "save_recording", "params": ["filename: String"], "return": "void"},
                    {"name": "load_recording", "params": ["filename: String"], "return": "void"},
                    {"name": "finish_lap", "params": [], "return": "void"}
                ]
            },
            {
                "class_name": "GhostPlayerController",
                "extends": "Node3D",
                "path": "scripts/racing/ghost_player_controller.gd",
                "exports": [
                    {"name": "playback_speed", "type": "float", "default": 1.0},
                    {"name": "ghost_material", "type": "Material", "default": None}
                ],
                "methods": [
                    {"name": "play", "params": [], "return": "void"},
                    {"name": "pause", "params": [], "return": "void"},
                    {"name": "reset", "params": [], "return": "void"},
                    {"name": "set_playback_position", "params": ["time: float"], "return": "void"},
                    {"name": "_process", "params": ["delta: float"], "return": "void"}
                ]
            }
        ],
        "assembly_steps": [
            "连接 PhysicsVehicle 的 update_engine(rpm, throttle, speed) 信号到 EngineSoundController.update_engine",
            "连接 useRaceState.lapComplete 信号到 GhostRecorder.finish_lap",
            "连接 PhysicsVehicle 的 rpm 信号到 UIAnimationController.play_animation",
            "连接 useRaceState.phaseChange 信号到 GhostPlayerController.play"
        ]
    }


def generate_racing_game_scene():
    """生成赛车游戏场景"""
    print("=" * 80)
    print("赛车游戏场景生成器")
    print("=" * 80)
    
    generator = GodotResourceGenerator(output_dir="racing_game_output")
    scene_config = create_racing_game_scene()
    
    print(f"\n📁 组件: {scene_config['component_uri']}")
    print(f"📄 资源数量: {len(scene_config['target_resources'])}")
    print(f"📜 脚本数量: {len(scene_config['target_scripts'])}")
    print(f"🔗 信号连接数量: {len(scene_config['assembly_steps'])}")
    
    generated_files = generator.generate_from_mapping(scene_config)
    
    print("\n✅ 生成完成！以下是生成的文件：")
    print("-" * 80)
    for filepath in generated_files:
        print(f"  📄 {filepath}")
    
    print("\n📋 场景预览 (EngineSound3D.tscn):")
    print("-" * 80)
    engine_sound_resource = next((r for r in scene_config["target_resources"] if r["name"] == "EngineSound3D"), None)
    if engine_sound_resource:
        tscn_content = TSCNGenerator.generate({
            "nodes": [{
                "type": engine_sound_resource["type"],
                "name": engine_sound_resource["name"],
                "parent": ".",
                "properties": engine_sound_resource["properties"]
            }]
        })
        print(tscn_content)
    
    return generated_files


if __name__ == "__main__":
    generate_racing_game_scene()
