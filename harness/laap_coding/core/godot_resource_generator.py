"""
godot_resource_generator.py — Godot资源自动生成器
=================================================

基于预设模板和配置参数，批量生成 Godot 资源文件：
1. .tscn 场景文件生成器
2. .tres 资源文件生成器  
3. .gd GDScript 文件生成器

支持的资源类型：
- AudioStreamPlayer3D, AudioStreamPlayer, Node3D, MeshInstance3D, AnimationPlayer
- AudioBusLayout, AudioStreamGenerator, StandardMaterial3D, AnimationLibrary
- GDScript (class_name, extends, exports, methods)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("godot_resource_generator")


class TSCNGenerator:
    @staticmethod
    def generate(mapping: Dict[str, Any]) -> str:
        nodes = mapping.get("nodes", [])
        logger.info(f"[TSCN] 开始生成 .tscn 场景，节点数量: {len(nodes)}")
        scene_content = TSCNGenerator._build_scene(nodes)
        logger.info(f"[TSCN] 场景生成完成，内容长度: {len(scene_content)} 字符")
        return scene_content

    @staticmethod
    def _build_scene(nodes: List[Dict[str, Any]]) -> str:
        lines = []
        lines.append("[gd_scene load_steps=1 format=3 uid=\"uid://abc123\"]")
        lines.append("")
        
        for idx, node in enumerate(nodes):
            node_type = node.get("type", "Node3D")
            name = node.get("name", "Node")
            parent = node.get("parent", ".")
            properties = node.get("properties", {})
            
            logger.debug(f"[TSCN] 处理节点 {idx+1}/{len(nodes)}: {name} (类型: {node_type}, 父节点: {parent})")
            logger.debug(f"[TSCN]   属性数量: {len(properties)}")
            
            lines.append(f"[node name=\"{name}\" type=\"{node_type}\" parent=\"{parent}\"]")
            for prop_name, prop_value in properties.items():
                formatted_value = TSCNGenerator._format_property(prop_value)
                logger.debug(f"[TSCN]     {prop_name} = {formatted_value}")
                lines.append(f"{prop_name} = {formatted_value}")
            lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def _format_property(value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            formatted_items = [TSCNGenerator._format_property(v) for v in value]
            return f"[{', '.join(formatted_items)}]"
        elif isinstance(value, dict):
            return str(value)
        else:
            return str(value)


class TRESGenerator:
    @staticmethod
    def generate(mapping: Dict[str, Any]) -> str:
        resource_type = mapping.get("type", "Resource")
        properties = mapping.get("properties", {})
        logger.info(f"[TRES] 开始生成 .tres 资源，类型: {resource_type}，属性数量: {len(properties)}")
        resource_content = TRESGenerator._build_resource(resource_type, properties)
        logger.info(f"[TRES] 资源生成完成，内容长度: {len(resource_content)} 字符")
        return resource_content

    @staticmethod
    def _build_resource(resource_type: str, properties: Dict[str, Any]) -> str:
        lines = []
        lines.append(f"[gd_resource type=\"{resource_type}\" load_steps=1 format=3]")
        lines.append("")
        lines.append("[resource]")
        
        for prop_name, prop_value in properties.items():
            formatted_value = TRESGenerator._format_property(prop_value)
            logger.debug(f"[TRES]   {prop_name} = {formatted_value}")
            lines.append(f"{prop_name} = {formatted_value}")
        
        return "\n".join(lines)

    @staticmethod
    def _format_property(value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            formatted_items = [TRESGenerator._format_property(v) for v in value]
            return f"[ {', '.join(formatted_items)} ]"
        elif isinstance(value, dict):
            return TRESGenerator._format_dict(value)
        else:
            return str(value)

    @staticmethod
    def _format_dict(d: Dict[str, Any]) -> str:
        if not d:
            return "{}"
        lines = ["{"]
        for key, value in d.items():
            lines.append(f'    "{key}": {TRESGenerator._format_property(value)},')
        lines.append("}")
        return "\n".join(lines)


class GDScriptGenerator:
    @staticmethod
    def generate(mapping: Dict[str, Any]) -> str:
        class_name = mapping.get("class_name", "")
        extends = mapping.get("extends", "Node")
        exports = mapping.get("exports", [])
        methods = mapping.get("methods", [])
        
        logger.info(f"[GDScript] 开始生成 .gd 脚本，类名: {class_name}，继承: {extends}，导出变量: {len(exports)}，方法: {len(methods)}")
        
        lines = []
        
        if class_name:
            lines.append(f"class_name {class_name}")
        
        lines.append(f"extends {extends}")
        lines.append("")
        
        for export_def in exports:
            export_name = export_def.get("name", "")
            export_type = export_def.get("type", "float")
            default = export_def.get("default")
            logger.debug(f"[GDScript]   @export var {export_name}: {export_type} = {default}")
            export_line = f"@export var {export_name}: {export_type}"
            if default is not None:
                export_line += f" = {GDScriptGenerator._format_default(default, export_type)}"
            lines.append(export_line)
        
        if exports:
            lines.append("")
        
        for method in methods:
            method_name = method.get("name", "")
            params = method.get("params", [])
            return_type = method.get("return", "void")
            logger.debug(f"[GDScript]   func {method_name}({', '.join(params)}) -> {return_type}")
            
            params_str = ", ".join(params)
            lines.append(f"func {method_name}({params_str}) -> {return_type}:")
            
            notes = method.get("notes", "")
            if notes:
                lines.append(f"\t# {notes}")
            
            if return_type != "void":
                lines.append("\treturn null")
            else:
                lines.append("\tpass")
            
            lines.append("")
        
        script_content = "\n".join(lines).strip()
        logger.info(f"[GDScript] 脚本生成完成，内容长度: {len(script_content)} 字符")
        return script_content

    @staticmethod
    def _format_default(value: Any, type_name: str) -> str:
        if type_name == "bool":
            return "true" if value else "false"
        elif type_name == "Color":
            return f'Color("{value}")'
        elif isinstance(value, str):
            return f'"{value}"'
        else:
            return str(value)


class GodotResourceGenerator:
    def __init__(self, output_dir: str = "generated"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"[Generator] 初始化完成，输出目录: {output_dir}")

    def generate_from_mapping(self, mapping: Dict[str, Any]) -> List[str]:
        component_uri = mapping.get("component_uri", "unknown")
        generated_files = []
        
        logger.info(f"[Generator] 开始处理组件: {component_uri}")
        
        target_resources = mapping.get("target_resources", [])
        target_scripts = mapping.get("target_scripts", [])
        
        logger.info(f"[Generator] 待生成资源数量: {len(target_resources)}，待生成脚本数量: {len(target_scripts)}")
        
        for idx, resource in enumerate(target_resources):
            resource_type = resource.get("type", "")
            path = resource.get("path", "")
            
            if not path:
                logger.warning(f"[Generator] 资源 {idx+1} 路径为空，跳过")
                continue
            
            logger.info(f"[Generator] 处理资源 {idx+1}/{len(target_resources)}: {path} (类型: {resource_type})")
            
            try:
                if resource_type.endswith(".tscn") or resource_type in [
                    "Node3D", "AudioStreamPlayer3D", "AudioStreamPlayer", 
                    "MeshInstance3D", "AnimationPlayer", "Camera3D", "VehicleBody3D"
                ]:
                    logger.info(f"[Generator]   生成 .tscn 场景文件")
                    content = self._generate_tscn(resource)
                    file_path = self._write_file(path, content)
                    generated_files.append(file_path)
                    logger.info(f"[Generator]   成功生成: {file_path}")
                elif resource_type.endswith(".tres") or resource_type in [
                    "AudioBusLayout", "AudioStreamGenerator", 
                    "StandardMaterial3D", "AnimationLibrary"
                ]:
                    logger.info(f"[Generator]   生成 .tres 资源文件")
                    content = self._generate_tres(resource)
                    file_path = self._write_file(path, content)
                    generated_files.append(file_path)
                    logger.info(f"[Generator]   成功生成: {file_path}")
                else:
                    logger.warning(f"[Generator]   未知资源类型: {resource_type}，跳过")
            except Exception as e:
                logger.error(f"[Generator]   生成失败: {str(e)}")
        
        for idx, script in enumerate(target_scripts):
            path = script.get("path", "")
            if not path:
                logger.warning(f"[Generator] 脚本 {idx+1} 路径为空，跳过")
                continue
            
            logger.info(f"[Generator] 处理脚本 {idx+1}/{len(target_scripts)}: {path}")
            
            try:
                content = GDScriptGenerator.generate(script)
                file_path = self._write_file(path, content)
                generated_files.append(file_path)
                logger.info(f"[Generator]   成功生成: {file_path}")
            except Exception as e:
                logger.error(f"[Generator]   生成失败: {str(e)}")
        
        logger.info(f"[Generator] 组件 {component_uri} 处理完成，共生成 {len(generated_files)} 个文件")
        return generated_files

    def _generate_tscn(self, resource: Dict[str, Any]) -> str:
        node_type = resource.get("type", "Node3D")
        name = resource.get("name", node_type.replace("3D", ""))
        properties = resource.get("properties", {})
        
        nodes = [{
            "type": node_type,
            "name": name,
            "parent": ".",
            "properties": properties
        }]
        
        return TSCNGenerator.generate({"nodes": nodes})

    def _generate_tres(self, resource: Dict[str, Any]) -> str:
        resource_type = resource.get("type", "Resource")
        properties = resource.get("properties", {})
        
        return TRESGenerator.generate({
            "type": resource_type,
            "properties": properties
        })

    def _write_file(self, path: str, content: str) -> str:
        full_path = os.path.join(self.output_dir, path.lstrip("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return full_path

    def batch_generate(self, mappings: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        results = {}
        
        for mapping in mappings:
            component_uri = mapping.get("component_uri", "unknown")
            generated = self.generate_from_mapping(mapping)
            results[component_uri] = generated
        
        return results


def get_godot_resource_generator(output_dir: str = "generated") -> GodotResourceGenerator:
    return GodotResourceGenerator(output_dir)


if __name__ == "__main__":
    generator = GodotResourceGenerator(output_dir="test_output")

    print("=" * 80)
    print("Godot资源自动生成器 — 测试运行")
    print("=" * 80)

    print("\n📄 测试 .tscn 生成:")
    print("-" * 80)
    tscn_mapping = {
        "nodes": [
            {
                "type": "AudioStreamPlayer3D",
                "name": "EngineSound3D",
                "parent": ".",
                "properties": {
                    "stream": "res://audio/samples/engine.ogg",
                    "autoplay": False,
                    "max_distance": 100.0,
                    "bus": "Engine"
                }
            }
        ]
    }
    tscn_content = TSCNGenerator.generate(tscn_mapping)
    print(tscn_content)

    print("\n📄 测试 .tres 生成:")
    print("-" * 80)
    tres_mapping = {
        "type": "AudioBusLayout",
        "properties": {
            "buses": [
                {"name": "Master", "mute": False, "volume_db": 0},
                {"name": "Engine", "mute": False, "volume_db": -3, "parent": "Master"}
            ]
        }
    }
    tres_content = TRESGenerator.generate(tres_mapping)
    print(tres_content)

    print("\n📄 测试 .gd 生成:")
    print("-" * 80)
    gd_mapping = {
        "class_name": "EngineSoundController",
        "extends": "Node3D",
        "exports": [
            {"name": "rpm_min", "type": "float", "default": 1000.0},
            {"name": "rpm_max", "type": "float", "default": 9000.0},
            {"name": "use_synth_fallback", "type": "bool", "default": False}
        ],
        "methods": [
            {"name": "update_engine", "params": ["rpm: float", "throttle: float"], "return": "void"},
            {"name": "_ready", "params": [], "return": "void"},
            {"name": "_process", "params": ["delta: float"], "return": "void", "notes": "每帧更新引擎声音"}
        ]
    }
    gd_content = GDScriptGenerator.generate(gd_mapping)
    print(gd_content)

    print("\n✅ Godot资源自动生成器测试完成")
