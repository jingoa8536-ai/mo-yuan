# arXiv 查询集 v2 — 代码理解与核方法专注 (2026-07-05)

## 轮换原因

v1 查询集已连续6+周期返回0新论文（总计35篇全部吸收）。根据 `aris-rsi-evolution` 技能中的"查询轮换触发"规则：

- 连续3周期0新论文: ✅ 
- 补充扫描超过48h: ✅ (上次: 2026-07-02)

## v2 查询集 (12个查询, 聚焦代码理解+核方法+认知架构)

v2 从广泛的领域覆盖转向更精确的技术 niche，优先 Lorry 指定的代码理解领域。

```python
V2_ARXIV_QUERIES = [
    "code+representation+learning+transformer+embedding",
    "kernel+method+similarity+metric+learning+feature",
    "neural+code+understanding+program+synthesis+ast",
    "superposition+polysemantic+feature+geometry+high+dim",
    "self+improving+code+generation+agent+refinement",
    "cognitive+architecture+recursive+self+model+metacognition",
    "semantic+sparse+autoencoder+feature+interpretability",
    "cross+modal+representation+alignment+embedding+space",
    "in+context+learning+emergent+capability+scaling+law",
    "hierarchical+compositional+representation+structure+language",
    "attention+mechanism+hypernetwork+dynamic+weight+generation",
    "efficient+finetuning+adapter+lora+parameter+efficient+transfer",
]
```

## 领域匹配器(v2)

```python
V2_KEYWORD_SETS = {
    'code_understanding': ['code', 'program', 'syntax', 'ast', 'function', 'semantic', 'embedding'],
    'kernel_methods': ['kernel', 'metric', 'similarity', 'feature', 'manifold', 'inner product'],
    'superposition': ['superposition', 'polysemantic', 'feature collision', 'geometry', 'high dim'],
    'cognitive_arch': ['recursive', 'self-improving', 'metacognition', 'self-model', 'reflection'],
    'representation_learning': ['representation', 'alignment', 'embedding', 'cross-modal', 'hierarchical'],
    'scaling': ['scaling law', 'emergent', 'capability', 'size', 'compute'],
}
```

## 轮换后恢复期

允许6个周期（36小时）收集新论文后再评估v2是否也饱和。如果v2也饱和，添加Semantic Scholar API作为补充源。

## 验证

轮换后运行一次完整 cycle，检查是否有新论文被捕获。
