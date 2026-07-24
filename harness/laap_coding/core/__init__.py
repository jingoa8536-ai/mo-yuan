"""
LAAP Coding Core — 核心模块入口
"""

from .harness import (
    ConsciousnessHarness,
    PerceptionLayer,
    MemoryLayer,
    ReasoningLayer,
    DecisionLayer,
    ExecutionLayer,
    VerificationLayer,
    FeedbackLayer,
    TaskContext,
    SubTask,
    ExecutionResult,
    VerificationResult,
    VerificationStep,
)

from .engine import HarnessEngine

from .test_validator import (
    TestValidator,
    TestResult,
    CoverageReport,
)

from .static_analyzer import (
    StaticAnalyzer,
    AnalysisIssue,
    StaticAnalysisResult,
)

from .security_scanner import (
    SecurityScanner,
    SecurityIssue,
    SecurityScanResult,
)

from .incremental_delivery import (
    IncrementalDelivery,
    CommitResult,
    ChangeStats,
    DeliveryConstraint,
)

from .progress_tracker import (
    ProgressTracker,
    TaskProgress,
    GoalProgress,
    ProgressSnapshot,
)

from .security_alignment import (
    SecurityAlignment,
    AIDebate,
    ArchitecturePatternValidator,
    ComplianceChecker,
    DeceptionDetector,
    DebateResult,
    PatternViolation,
    ComplianceIssue,
    DeceptionDetection,
)

from .cognitive_integration import (
    CognitiveIntegration,
    RateBuffer,
    EmergenceInsight,
    HarnessExecutionResult,
    EmergenceEventType,
    get_integration,
    start_integration,
    stop_integration,
    process_pending_insights,
    get_context,
)

from .matching_engine import (
    MatchingEngine,
    ComponentMeta,
    MatchThreshold,
    MatchLevel,
    MatchingStrategy,
    get_matching_engine,
)

__all__ = [
    "ConsciousnessHarness",
    "PerceptionLayer",
    "MemoryLayer",
    "ReasoningLayer",
    "DecisionLayer",
    "ExecutionLayer",
    "VerificationLayer",
    "FeedbackLayer",
    "TaskContext",
    "SubTask",
    "ExecutionResult",
    "VerificationResult",
    "VerificationStep",
    "HarnessEngine",
    "TestValidator",
    "TestResult",
    "CoverageReport",
    "StaticAnalyzer",
    "AnalysisIssue",
    "StaticAnalysisResult",
    "SecurityScanner",
    "SecurityIssue",
    "SecurityScanResult",
    "IncrementalDelivery",
    "CommitResult",
    "ChangeStats",
    "DeliveryConstraint",
    "ProgressTracker",
    "TaskProgress",
    "GoalProgress",
    "ProgressSnapshot",
    "SecurityAlignment",
    "AIDebate",
    "ArchitecturePatternValidator",
    "ComplianceChecker",
    "DeceptionDetector",
    "DebateResult",
    "PatternViolation",
    "ComplianceIssue",
    "DeceptionDetection",
    "CognitiveIntegration",
    "RateBuffer",
    "EmergenceInsight",
    "HarnessExecutionResult",
    "EmergenceEventType",
    "MatchingEngine",
    "ComponentMeta",
    "MatchThreshold",
    "MatchLevel",
    "MatchingStrategy",
]
