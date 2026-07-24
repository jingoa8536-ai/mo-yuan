"""
signal_connector.py — 信号连接管理器
====================================

提供信号注册、连接、断开和管理的统一接口，支持：
1. 信号定义解析（从 godot-mapping.json 的 assembly_steps）
2. 通过 JSON-RPC 调用 Godot Bridge 执行信号连接操作
3. 信号连接状态查询和管理

信号连接格式：
- 源节点 → 信号 → 目标节点 → 目标方法
- 例如：PhysicsVehicle.update_engine → EngineSoundController.update_engine
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("signal_connector")


@dataclass
class SignalConnection:
    source_node: str
    source_signal: str
    target_node: str
    target_method: str
    connection_id: str = ""
    connected: bool = False


class SignalConnector:
    SIGNAL_PATTERN = re.compile(
        r'连接\s+([^\s]+)\s*(?:的\s+([^\s\(\)]+)\s*\([^\)]*\)|([^\s]+))\s+信号到\s+([^\s]+)\.([^\s]+)'
    )
    
    def __init__(self):
        self.connections: Dict[str, SignalConnection] = {}
        self.connection_counter = 0
        logger.info("[SignalConnector] 初始化完成")
    
    def parse_assembly_steps(self, steps: List[str]) -> List[SignalConnection]:
        connections = []
        logger.info(f"[SignalConnector] 开始解析 assembly_steps，步骤数量: {len(steps)}")
        
        for idx, step in enumerate(steps):
            logger.debug(f"[SignalConnector] 解析步骤 {idx+1}: {step}")
            match = self.SIGNAL_PATTERN.search(step)
            if match:
                source_node = match.group(1)
                source_signal = match.group(2) or match.group(3)
                target_node = match.group(4)
                target_method = match.group(5)
                
                logger.info(f"[SignalConnector]   匹配成功: {source_node}.{source_signal} -> {target_node}.{target_method}")
                
                connection = SignalConnection(
                    source_node=source_node,
                    source_signal=source_signal,
                    target_node=target_node,
                    target_method=target_method
                )
                connections.append(connection)
            else:
                logger.warning(f"[SignalConnector]   步骤 {idx+1} 未匹配到信号连接模式")
        
        logger.info(f"[SignalConnector] 解析完成，共解析出 {len(connections)} 个信号连接")
        return connections
    
    def register_connection(self, connection: SignalConnection) -> str:
        connection_id = f"conn_{self.connection_counter}"
        self.connection_counter += 1
        connection.connection_id = connection_id
        self.connections[connection_id] = connection
        
        logger.info(f"[SignalConnector] 注册信号连接: {connection_id} = {connection.source_node}.{connection.source_signal} -> {connection.target_node}.{connection.target_method}")
        return connection_id
    
    def register_connections(self, connections: List[SignalConnection]) -> List[str]:
        connection_ids = []
        logger.info(f"[SignalConnector] 批量注册 {len(connections)} 个信号连接")
        
        for conn in connections:
            conn_id = self.register_connection(conn)
            connection_ids.append(conn_id)
        
        logger.info(f"[SignalConnector] 批量注册完成，共注册 {len(connection_ids)} 个连接")
        return connection_ids
    
    def connect(self, connection_id: str) -> bool:
        if connection_id not in self.connections:
            logger.error(f"[SignalConnector] 连接失败: 连接 {connection_id} 不存在")
            return False
        
        conn = self.connections[connection_id]
        conn.connected = True
        
        logger.info(f"[SignalConnector] 信号连接成功: {connection_id} ({conn.source_node}.{conn.source_signal} -> {conn.target_node}.{conn.target_method})")
        return True
    
    def disconnect(self, connection_id: str) -> bool:
        if connection_id not in self.connections:
            logger.error(f"[SignalConnector] 断开失败: 连接 {connection_id} 不存在")
            return False
        
        conn = self.connections[connection_id]
        conn.connected = False
        
        logger.info(f"[SignalConnector] 信号断开成功: {connection_id} ({conn.source_node}.{conn.source_signal} -> {conn.target_node}.{conn.target_method})")
        return True
    
    def connect_all(self) -> int:
        count = 0
        logger.info(f"[SignalConnector] 批量连接所有信号，总数量: {len(self.connections)}")
        
        for conn_id in self.connections:
            if self.connect(conn_id):
                count += 1
        
        logger.info(f"[SignalConnector] 批量连接完成，成功 {count}/{len(self.connections)}")
        return count
    
    def disconnect_all(self) -> int:
        count = 0
        logger.info(f"[SignalConnector] 批量断开所有信号，总数量: {len(self.connections)}")
        
        for conn_id in self.connections:
            if self.disconnect(conn_id):
                count += 1
        
        logger.info(f"[SignalConnector] 批量断开完成，成功 {count}/{len(self.connections)}")
        return count
    
    def get_connection(self, connection_id: str) -> Optional[SignalConnection]:
        return self.connections.get(connection_id)
    
    def get_all_connections(self) -> List[SignalConnection]:
        return list(self.connections.values())
    
    def get_connected_connections(self) -> List[SignalConnection]:
        return [conn for conn in self.connections.values() if conn.connected]
    
    def get_disconnected_connections(self) -> List[SignalConnection]:
        return [conn for conn in self.connections.values() if not conn.connected]
    
    def get_connection_status(self, connection_id: str) -> Dict[str, Any]:
        conn = self.get_connection(connection_id)
        if not conn:
            return {"error": "Connection not found"}
        
        return {
            "connection_id": conn.connection_id,
            "source_node": conn.source_node,
            "source_signal": conn.source_signal,
            "target_node": conn.target_node,
            "target_method": conn.target_method,
            "connected": conn.connected
        }
    
    def get_status_summary(self) -> Dict[str, Any]:
        total = len(self.connections)
        connected = len(self.get_connected_connections())
        disconnected = len(self.get_disconnected_connections())
        
        return {
            "total_connections": total,
            "connected_count": connected,
            "disconnected_count": disconnected,
            "connection_rate": connected / total if total > 0 else 0.0
        }
    
    def remove_connection(self, connection_id: str) -> bool:
        if connection_id in self.connections:
            del self.connections[connection_id]
            return True
        return False
    
    def clear_all(self) -> None:
        self.connections.clear()
        self.connection_counter = 0
    
    def to_dict(self) -> List[Dict[str, Any]]:
        return [
            {
                "connection_id": conn.connection_id,
                "source_node": conn.source_node,
                "source_signal": conn.source_signal,
                "target_node": conn.target_node,
                "target_method": conn.target_method,
                "connected": conn.connected
            }
            for conn in self.connections.values()
        ]
    
    @staticmethod
    def from_dict(data: List[Dict[str, Any]]) -> 'SignalConnector':
        connector = SignalConnector()
        for conn_data in data:
            conn = SignalConnection(
                source_node=conn_data.get("source_node", ""),
                source_signal=conn_data.get("source_signal", ""),
                target_node=conn_data.get("target_node", ""),
                target_method=conn_data.get("target_method", ""),
                connection_id=conn_data.get("connection_id", ""),
                connected=conn_data.get("connected", False)
            )
            connector.connections[conn.connection_id] = conn
            if conn.connection_id:
                conn_id_num = int(conn.connection_id.replace("conn_", ""))
                connector.connection_counter = max(connector.connection_counter, conn_id_num + 1)
        return connector


class GodotSignalConnector(SignalConnector):
    def __init__(self, jsonrpc_client=None):
        super().__init__()
        self.jsonrpc_client = jsonrpc_client
    
    def connect_via_rpc(self, connection_id: str) -> Dict[str, Any]:
        conn = self.get_connection(connection_id)
        if not conn:
            return {"error": "Connection not found", "success": False}
        
        if not self.jsonrpc_client:
            return {"error": "JSON-RPC client not configured", "success": False}
        
        try:
            result = self.jsonrpc_client.call_method(
                "call_method_on_node",
                {
                    "node_path": conn.source_node,
                    "method": "connect",
                    "args": [conn.source_signal, conn.target_node, conn.target_method]
                }
            )
            if result.get("success", False):
                conn.connected = True
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def disconnect_via_rpc(self, connection_id: str) -> Dict[str, Any]:
        conn = self.get_connection(connection_id)
        if not conn:
            return {"error": "Connection not found", "success": False}
        
        if not self.jsonrpc_client:
            return {"error": "JSON-RPC client not configured", "success": False}
        
        try:
            result = self.jsonrpc_client.call_method(
                "call_method_on_node",
                {
                    "node_path": conn.source_node,
                    "method": "disconnect",
                    "args": [conn.source_signal, conn.target_node, conn.target_method]
                }
            )
            if result.get("success", False):
                conn.connected = False
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def connect_all_via_rpc(self) -> Dict[str, Any]:
        results = []
        for conn_id in self.connections:
            result = self.connect_via_rpc(conn_id)
            results.append({
                "connection_id": conn_id,
                **result
            })
        
        succeeded = sum(1 for r in results if r.get("success", False))
        failed = len(results) - succeeded
        
        return {
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "details": results
        }


def get_signal_connector() -> SignalConnector:
    return SignalConnector()


def get_godot_signal_connector(jsonrpc_client=None) -> GodotSignalConnector:
    return GodotSignalConnector(jsonrpc_client)


if __name__ == "__main__":
    connector = SignalConnector()

    print("=" * 80)
    print("信号连接管理器 — 测试运行")
    print("=" * 80)

    test_steps = [
        "连接 PhysicsVehicle 的 update_engine(rpm, throttle, speed) 信号到 EngineSoundController.update_engine",
        "连接 useRaceState.lapComplete 信号到 GhostRecorder.finish_lap",
        "连接 PhysicsVehicle 的 rpm 信号到 UIAnimationController.play_animation",
        "连接 useRaceState.phaseChange 信号到 GhostPlayerController.play"
    ]

    print("\n🔍 解析 assembly_steps:")
    print("-" * 80)
    connections = connector.parse_assembly_steps(test_steps)
    for i, conn in enumerate(connections, 1):
        print(f"  {i}. {conn.source_node}.{conn.source_signal} -> {conn.target_node}.{conn.target_method}")

    print("\n📝 注册信号连接:")
    print("-" * 80)
    conn_ids = connector.register_connections(connections)
    for conn_id in conn_ids:
        status = connector.get_connection_status(conn_id)
        print(f"  {conn_id}: {status['source_node']}.{status['source_signal']} -> {status['target_node']}.{status['target_method']}")

    print("\n🔗 连接所有信号:")
    print("-" * 80)
    connected_count = connector.connect_all()
    print(f"  成功连接 {connected_count} 个信号")

    print("\n📊 状态汇总:")
    print("-" * 80)
    summary = connector.get_status_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\n✅ 信号连接管理器测试完成")
