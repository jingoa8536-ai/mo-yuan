"""
shadcn_mcp_integrator.py — LAAP Harness shadcn-ui-mcp-server 集成层
======================================================================
将 shadcn-ui-mcp-server 的 MCP 工具暴露给 Python/Harness 工程

功能:
  ├── 启动/管理 MCP Server 进程 (stdio 模式)
  ├── 封装所有 shadcn-ui MCP 工具为 Python API
  ├── 将组件数据同步到 Harness UI 数据库
  ├── 支持组件代码生成和页面组装
  ├── 支持 GitHub Token 配置（提升 API 限额 60/h → 5000/h）
  └── 集成到现有 matching_engine 和 page_assembler

架构:
  Python Harness ──stdio──> Node.js MCP Server ──GitHub API──> shadcn/ui

环境变量:
  GITHUB_PERSONAL_ACCESS_TOKEN - GitHub 个人访问令牌
  SHADCN_MCP_FRAMEWORK - 默认框架 (react/svelte/vue/react-native)
  SHADCN_MCP_TIMEOUT - 超时时间（秒）
"""

import os
import json
import time
import subprocess
import threading
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MCP_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "shadcn-ui-mcp-server")
BUILD_DIR = os.path.join(MCP_SERVER_DIR, "build")

DEFAULT_FRAMEWORK = os.getenv("SHADCN_MCP_FRAMEWORK", "react")
DEFAULT_TIMEOUT = int(os.getenv("SHADCN_MCP_TIMEOUT", "15"))


@dataclass
class ComponentInfo:
    name: str
    description: str
    framework: str
    dependencies: List[str]
    code: str
    demo: str
    metadata: Dict[str, Any]


@dataclass
class BlockInfo:
    name: str
    description: str
    category: str
    components: List[str]
    code: str


class ShadcnMCPIntegrator:
    """shadcn-ui-mcp-server Python 集成层"""

    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        self.server_process = None
        self.server_running = False
        self._request_id = 0
        self._output_buffer = ""
        self._lock = threading.Lock()
        self._token_validated = False

    def validate_github_token(self, token: str = None) -> bool:
        """验证 GitHub Token 的有效性"""
        token_to_check = token or self.github_token
        if not token_to_check:
            return False

        try:
            response = requests.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token_to_check}"},
                timeout=5
            )
            self._token_validated = response.status_code == 200
            return self._token_validated
        except Exception:
            self._token_validated = False
            return False

    def get_api_limit(self) -> Dict[str, int]:
        """获取当前 GitHub API 调用限额"""
        if not self.github_token:
            return {"limit": 60, "remaining": 60, "used": 0, "with_token": False}

        try:
            response = requests.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"token {self.github_token}"},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                core = data.get("rate", {})
                return {
                    "limit": core.get("limit", 5000),
                    "remaining": core.get("remaining", 5000),
                    "used": core.get("used", 0),
                    "with_token": True
                }
        except Exception:
            pass

        return {"limit": 60, "remaining": 60, "used": 0, "with_token": False}

    def start_server(self, framework: str = "react", ui_library: str = "radix") -> bool:
        """启动 shadcn-ui-mcp-server (stdio 模式)"""
        if self.server_running:
            return True

        build_path = os.path.join(BUILD_DIR, "index.js")
        if not os.path.exists(build_path):
            raise RuntimeError(f"MCP Server build not found: {build_path}")

        env = os.environ.copy()
        if self.github_token:
            env["GITHUB_PERSONAL_ACCESS_TOKEN"] = self.github_token
        env["UI_LIBRARY"] = ui_library

        args = [
            "node", build_path,
            "--mode", "stdio",
            "--framework", framework
        ]

        try:
            self.server_process = subprocess.Popen(
                args,
                cwd=MCP_SERVER_DIR,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            time.sleep(2)

            if self.server_process.poll() is None:
                self.server_running = True
                print(f"✅ shadcn-ui-mcp-server started (pid: {self.server_process.pid})")
                return True
            else:
                stderr = self.server_process.stderr.read() if self.server_process.stderr else ""
                print(f"❌ Server failed to start: {stderr}")
                return False
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False

    def stop_server(self):
        """停止 MCP Server"""
        if self.server_process:
            try:
                self.server_process.stdin.close()
            except:
                pass
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except:
                self.server_process.kill()
            self.server_process = None
        self.server_running = False
        print("✅ shadcn-ui-mcp-server stopped")

    def _read_response(self, timeout: int = 15) -> str:
        """读取服务器响应"""
        if not self.server_process or not self.server_process.stdout:
            raise RuntimeError("Server not running or stdout not available")

        deadline = time.time() + timeout
        response = ""

        while time.time() < deadline:
            try:
                line = self.server_process.stdout.readline()
                if line:
                    response += line
                    if line.strip().startswith("{") and line.strip().endswith("}"):
                        break
                    if "}" in line and "{" in response:
                        break
                else:
                    time.sleep(0.1)
            except Exception as e:
                time.sleep(0.1)

        if not response:
            raise RuntimeError("No response from server")

        return response

    def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """调用 MCP 工具 (stdio JSON-RPC)"""
        if not self.server_running and not self.start_server():
            raise RuntimeError("MCP Server not running")

        if not hasattr(self, '_initialized') or not self._initialized:
            self._initialize_connection()

        self._request_id += 1
        request_id = self._request_id

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params or {}
            }
        }

        try:
            if self.server_process.stdin:
                self.server_process.stdin.write(json.dumps(payload) + "\n")
                self.server_process.stdin.flush()
            else:
                raise RuntimeError("Cannot write to stdin")

            response_str = self._read_response()

            try:
                return json.loads(response_str)
            except json.JSONDecodeError:
                lines = response_str.strip().split("\n")
                for line in lines:
                    line = line.strip()
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            return json.loads(line)
                        except:
                            continue
                raise RuntimeError(f"Invalid JSON response: {response_str[:200]}")

        except Exception as e:
            raise RuntimeError(f"MCP call error: {e}")

    def _initialize_connection(self):
        """初始化 MCP 连接"""
        self._request_id += 1
        request_id = self._request_id

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "clientInfo": {
                    "name": "LAAP Harness",
                    "version": "1.0.0"
                }
            }
        }

        if self.server_process.stdin:
            self.server_process.stdin.write(json.dumps(payload) + "\n")
            self.server_process.stdin.flush()

        response_str = self._read_response()
        print(f"DEBUG: Initialize response: {response_str[:300]}")

        try:
            response = json.loads(response_str)
            if "error" in response:
                print(f"WARNING: Initialize error: {response['error'].get('message')}")
        except:
            pass

        self._initialized = True

    def _extract_content(self, result: Dict[str, Any]) -> str:
        """从 MCP 响应中提取内容"""
        result_data = result.get("result", {})
        content = result_data.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            return content[0].get("text", "")
        elif isinstance(content, dict):
            return content.get("text", json.dumps(content))
        return str(content)

    def list_components(self) -> List[Dict[str, Any]]:
        """获取所有可用组件"""
        result = self._call_mcp_tool("list_components")
        content_text = self._extract_content(result)
        print(f"DEBUG: list_components content: {content_text[:300]}")
        try:
            data = json.loads(content_text)
            if isinstance(data, dict) and "components" in data:
                return data["components"]
            elif isinstance(data, list):
                return [{"name": item} if isinstance(item, str) else item for item in data]
            return []
        except Exception as e:
            print(f"DEBUG: JSON parse error: {e}")
            return []

    def get_component(self, component_name: str, framework: str = "react") -> ComponentInfo:
        """获取组件源代码"""
        result = self._call_mcp_tool("get_component", {
            "componentName": component_name,
            "framework": framework
        })
        content_text = self._extract_content(result)
        try:
            content = json.loads(content_text)
        except:
            content = {}
        return ComponentInfo(
            name=component_name,
            description=content.get("description", ""),
            framework=framework,
            dependencies=content.get("dependencies", []),
            code=content.get("code", ""),
            demo="",
            metadata=content.get("metadata", {})
        )

    def get_component_demo(self, component_name: str, framework: str = "react") -> str:
        """获取组件示例代码"""
        result = self._call_mcp_tool("get_component_demo", {
            "componentName": component_name,
            "framework": framework
        })
        content_text = self._extract_content(result)
        try:
            content = json.loads(content_text)
            return content.get("code", "")
        except:
            return content_text

    def get_component_metadata(self, component_name: str, framework: str = "react") -> Dict[str, Any]:
        """获取组件元数据"""
        result = self._call_mcp_tool("get_component_metadata", {
            "componentName": component_name,
            "framework": framework
        })
        content_text = self._extract_content(result)
        try:
            return json.loads(content_text)
        except:
            return {}

    def list_blocks(self) -> List[Dict[str, Any]]:
        """获取所有可用 blocks"""
        result = self._call_mcp_tool("list_blocks")
        content_text = self._extract_content(result)
        try:
            data = json.loads(content_text)
            if isinstance(data, dict) and "blocks" in data:
                return data["blocks"]
            elif isinstance(data, list):
                return [{"name": item} if isinstance(item, str) else item for item in data]
            return []
        except:
            return []

    def get_block(self, block_name: str, framework: str = "react") -> BlockInfo:
        """获取 block 实现"""
        result = self._call_mcp_tool("get_block", {
            "blockName": block_name,
            "framework": framework
        })
        content_text = self._extract_content(result)
        try:
            content = json.loads(content_text)
        except:
            content = {}
        return BlockInfo(
            name=block_name,
            description=content.get("description", ""),
            category=content.get("category", ""),
            components=content.get("components", []),
            code=content.get("code", "")
        )

    def get_directory_structure(self, path: str = "") -> Dict[str, Any]:
        """获取目录结构"""
        result = self._call_mcp_tool("get_directory_structure", {
            "path": path
        })
        return result.get("result", {}).get("content", {})

    def list_themes(self) -> List[str]:
        """获取可用主题"""
        result = self._call_mcp_tool("list_themes")
        return result.get("result", {}).get("content", {}).get("themes", [])

    def get_theme(self, theme_name: str) -> Dict[str, Any]:
        """获取主题详情"""
        result = self._call_mcp_tool("get_theme", {
            "themeName": theme_name
        })
        return result.get("result", {}).get("content", {})

    def sync_to_harness_db(self) -> Dict[str, Any]:
        """同步 shadcn-ui 组件到 Harness UI 数据库"""
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from harness_ui_db import UI_LIBRARIES, ANIMATION_LIBRARIES

        components = self.list_components()
        blocks = self.list_blocks()

        shadcn_ui_entry = UI_LIBRARIES.get("shadcn_ui", {})
        shadcn_ui_entry["components"] = [c.get("name") for c in components]
        shadcn_ui_entry["blocks"] = [b.get("name") for b in blocks]
        shadcn_ui_entry["total_components"] = len(components)
        shadcn_ui_entry["total_blocks"] = len(blocks)

        UI_LIBRARIES["shadcn_ui"] = shadcn_ui_entry

        return {
            "synced_components": len(components),
            "synced_blocks": len(blocks),
            "updated_library": "shadcn_ui"
        }

    def generate_page_from_blocks(self, blocks: List[str], framework: str = "react") -> str:
        """从 blocks 生成完整页面"""
        page_parts = []

        for block_name in blocks:
            block = self.get_block(block_name, framework)
            if block.code:
                page_parts.append(f"<!-- Block: {block_name} -->")
                page_parts.append(block.code)

        return "\n".join(page_parts)

    def generate_component_code(self, component_name: str, props: Dict[str, Any] = None, framework: str = "react") -> str:
        """生成组件代码（包含 props）"""
        component = self.get_component(component_name, framework)
        demo = self.get_component_demo(component_name, framework)

        return f"""// {component_name} Component - {framework}
// Description: {component.description}
// Dependencies: {', '.join(component.dependencies)}

{component.code}

// Demo Usage:
{demo}
"""

    def status(self) -> Dict[str, Any]:
        """获取集成状态"""
        try:
            components = self.list_components()
            blocks = self.list_blocks()
            return {
                "server_running": self.server_running,
                "framework": "react",
                "total_components": len(components),
                "total_blocks": len(blocks),
                "component_names": [c.get("name") for c in components[:10]] + (["..."] if len(components) > 10 else []),
                "block_names": [b.get("name") for b in blocks[:10]] + (["..."] if len(blocks) > 10 else []),
                "health": "healthy" if self.server_running else "stopped"
            }
        except Exception as e:
            return {
                "server_running": self.server_running,
                "error": str(e)
            }


class ShadcnHarnessBridge:
    """Harness 桥接器 — 将 shadcn-mcp 集成到 Harness 匹配引擎和页面组装器"""

    def __init__(self, integrator: ShadcnMCPIntegrator):
        self.integrator = integrator
        self.component_cache = {}
        self.block_cache = {}

    def enhance_matching_result(self, matching_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """增强匹配结果，添加 shadcn-ui 组件详情"""
        enhanced = []
        for result in matching_results:
            if result.get("type") == "ui" and result.get("id") == "shadcn_ui":
                component_name = result.get("component")
                if component_name and component_name not in self.component_cache:
                    try:
                        metadata = self.integrator.get_component_metadata(component_name)
                        self.component_cache[component_name] = metadata
                    except:
                        self.component_cache[component_name] = {}

                result["shadcn_metadata"] = self.component_cache.get(component_name, {})
                result["mcp_available"] = True
            enhanced.append(result)
        return enhanced

    def assemble_with_shadcn(self, intent: Dict[str, Any]) -> str:
        """使用 shadcn-ui 组件组装页面"""
        page_type = intent.get("page_type", "landing")
        style_tags = intent.get("style_tags", [])
        required_sections = intent.get("required_sections", [])

        blocks_map = {
            "landing": ["hero-01", "features-01", "pricing-01", "cta-01"],
            "dashboard": ["dashboard-01", "sidebar-01", "stats-01"],
            "auth": ["login-01", "register-01"],
        }

        blocks_to_use = blocks_map.get(page_type, ["hero-01"])

        page_code = self.integrator.generate_page_from_blocks(blocks_to_use)

        return f"""<!-- Generated by LAAP Harness + shadcn-ui-mcp-server -->
<!-- Intent: {json.dumps(intent)} -->
<!-- Blocks: {blocks_to_use} -->

{page_code}
"""

    def get_component_dependency_graph(self, component_name: str) -> Dict[str, Any]:
        """获取组件依赖图"""
        metadata = self.integrator.get_component_metadata(component_name)
        dependencies = metadata.get("dependencies", [])

        graph = {
            "component": component_name,
            "direct_dependencies": dependencies,
            "transitive_dependencies": [],
            "size": metadata.get("size", ""),
            "version": metadata.get("version", "")
        }

        for dep in dependencies:
            try:
                dep_metadata = self.integrator.get_component_metadata(dep)
                graph["transitive_dependencies"].extend(dep_metadata.get("dependencies", []))
            except:
                pass

        return graph


if __name__ == "__main__":
    print("=" * 80)
    print("LAAP Harness shadcn-ui-mcp-server 集成测试")
    print("=" * 80)

    integrator = ShadcnMCPIntegrator()

    print("\n[TOKEN] GitHub Token 状态:")
    api_limit = integrator.get_api_limit()
    if api_limit["with_token"]:
        print(f"   [OK] Token 已配置")
        print(f"   [INFO] API 限额: {api_limit['used']}/{api_limit['limit']}")
        print(f"   [INFO] 提升: 60/h → {api_limit['limit']}/h")
    else:
        print(f"   [WARN] 未配置 Token")
        print(f"   [INFO] API 限额: 60/h")
        print(f"   [HINT] 建议: 创建 .env 文件配置 GITHUB_PERSONAL_ACCESS_TOKEN")

    print("\n[SERVER] 启动 MCP Server...")
    if integrator.start_server():
        print("\n[OK] MCP Server 连接成功")
        print(f"   服务器: shadcn-ui-mcp-server v2.0.0")
        print(f"   协议版本: 2025-06-18")

        print("\n[COMPONENTS] 获取组件列表...")
        components = integrator.list_components()
        print(f"   找到 {len(components)} 个 shadcn/ui 组件")
        if components:
            print(f"   前 10 个: {', '.join([c.get('name', c) if isinstance(c, dict) else c for c in components[:10]])}")

        print("\n[BLOCKS] 获取 Blocks 列表...")
        blocks = integrator.list_blocks()
        print(f"   找到 {len(blocks)} 个 blocks")

        print("\n[COMPLETE] 集成测试完成")

        integrator.stop_server()
    else:
        print("[ERROR] 无法启动 MCP Server")