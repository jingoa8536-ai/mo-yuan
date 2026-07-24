"""LAAP-COOP 多智能体协作协议

定义生命体间任务分工、权责分配、协作记忆的协议契约。
支持共享事实 + 私有判断的双层记忆模型。

References:
- LAAP2.0大版本升级方案 § LAAP-COOP
- laap-2-living-workspace spec Phase 3
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FactScope(Enum):
    """事实共享范围"""
    PRIVATE = "private"  # 私有判断（仅自己可见）
    TEAM = "team"  # 团队共享
    ORG = "org"  # 组织共享
    PUBLIC = "public"  # 公开共享


class TaskStatus(Enum):
    """任务状态"""
    PROPOSED = "proposed"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NegotiationOutcome(Enum):
    """协商结果"""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COUNTERED = "countered"  # 提出反报价
    DEFERRED = "deferred"  # 延后决定


@dataclass
class TaskAssignment:
    """任务分配"""
    assignment_id: str
    task_id: str
    task_description: str
    assignee_id: str  # 被分配者 ID
    assigner_id: str  # 分配者 ID
    required_capabilities: List[str] = field(default_factory=list)
    deadline: Optional[datetime] = None
    priority: str = "medium"  # low/medium/high/critical
    status: TaskStatus = TaskStatus.ASSIGNED
    context_facts: List[str] = field(default_factory=list)  # 共享事实 ID 列表
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SharedFact:
    """共享事实（双层记忆中的"共享事实"层）"""
    fact_id: str
    content: str  # 事实内容
    scope: FactScope
    source_id: str  # 提供者 ID
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)  # 证据链


@dataclass
class NegotiationResult:
    """协商结果"""
    negotiation_id: str
    outcome: NegotiationOutcome
    agreed_terms: Dict[str, Any]  # 达成的条款
    counter_proposal: Optional[Dict[str, Any]] = None  # 反报价（若 outcome=countered）
    participants: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


class CooperationProtocol(ABC):
    """LAAP-COOP 多智能体协作协议抽象基类

    定义生命体间协作的标准接口。私有判断由各生命体自行维护，
    共享事实通过本协议传播。
    """

    @abstractmethod
    def assign_task(
        self, task: Dict[str, Any], assignee_id: str
    ) -> TaskAssignment:
        """分配任务给指定生命体

        Args:
            task: 任务描述字典（含 task_id, description, required_capabilities 等）
            assignee_id: 被分配者 ID

        Returns:
            TaskAssignment 包含完整分配信息
        """
        ...

    @abstractmethod
    def share_fact(self, fact: SharedFact) -> None:
        """共享事实到协作记忆

        根据 fact.scope 决定传播范围：
        - PRIVATE: 仅本地保存
        - TEAM: 广播到团队
        - ORG: 广播到组织
        - PUBLIC: 全网广播

        Args:
            fact: 要共享的事实
        """
        ...

    @abstractmethod
    def negotiate(
        self,
        proposal: Dict[str, Any],
        counterparty_ids: List[str],
    ) -> NegotiationResult:
        """与其他生命体协商

        支持任务分配协商、资源交换协商、责任划分协商等。

        Args:
            proposal: 提议内容
            counterparty_ids: 协商对方 ID 列表

        Returns:
            NegotiationResult 包含协商结果
        """
        ...

    @abstractmethod
    def query_shared_facts(
        self,
        tags: Optional[List[str]] = None,
        source_id: Optional[str] = None,
    ) -> List[SharedFact]:
        """查询共享事实库

        Args:
            tags: 可选的标签过滤
            source_id: 可选的来源过滤

        Returns:
            匹配的共享事实列表
        """
        ...

    @abstractmethod
    def get_assignments(
        self, assignee_id: Optional[str] = None
    ) -> List[TaskAssignment]:
        """查询任务分配

        Args:
            assignee_id: 可选的被分配者过滤；None 表示所有

        Returns:
            任务分配列表
        """
        ...
