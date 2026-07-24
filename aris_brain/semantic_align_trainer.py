"""
语义对齐训练器 — 让量子核学会语义距离
==========================================

核心思路:
  all-MiniLM (384D 语义空间) → 投影矩阵 W (384×1024) → 量子核 1024D 空间

这样量子核就继承了 all-MiniLM 的语义区分能力，
同时保持 1024D 的高维表达力和确定性编码。

训练数据: 常用中文短语 + all-MiniLM 生成的 384D 向量
训练目标: 最小化余弦距离损失 (MSE + 余弦相似度约束)

完成后，量子核的 encode() 直接调用 all-MiniLM + 投影，
不再是字符哈希。
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time
import numpy as np
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ════════════════════════════════════════════════════════════
# 训练数据生成
# ════════════════════════════════════════════════════════════

TRAIN_PHRASES = [
    # 问候
    "你好", "你好吗", "早上好", "下午好", "晚上好", "嗨", "哈喽", "hello",
    "最近好吗", "吃过没", "在吗", "干嘛呢", "好久不见", "见到你很高兴",
    "早安", "午安", "晚安", "好梦", "早点休息", "睡个好觉",

    # 告别
    "再见", "拜拜", "明天见", "回头聊", "先这样", "下次再聊",
    "我先走了", "回见", "再会", "后会有期",

    # 情感正向
    "我爱你", "想你", "喜欢你", "爱你", "好想你", "想你啦",
    "开心", "快乐", "幸福", "感动", "温暖", "美好", "棒极了",
    "太棒了", "真厉害", "了不起", "太美了", "真好看",
    "谢谢你", "感谢", "辛苦了", "麻烦你了",
    "加油", "坚持", "你可以的", "相信你", "支持你",

    # 情感负向
    "难过", "伤心", "悲伤", "痛苦", "心碎", "失落",
    "生气", "愤怒", "烦死了", "讨厌", "恶心",
    "害怕", "恐惧", "担心", "焦虑", "紧张", "不安",
    "累了", "疲惫", "好累", "受不了", "绝望",

    # 技术
    "代码", "编程", "写代码", "程序", "软件", "开发",
    "算法", "数据结构", "排序", "搜索", "递归", "动态规划",
    "数据库", "SQL", "NoSQL", "Redis", "MySQL", "查询",
    "架构", "设计模式", "微服务", "分布式", "高并发",
    "前端", "后端", "全栈", "API", "接口", "协议",
    "Python", "JavaScript", "TypeScript", "Go", "Rust", "C++",
    "框架", "React", "Vue", "Django", "Flask", "Spring",
    "网络", "HTTP", "TCP", "UDP", "WebSocket", "gRPC",
    "系统", "Linux", "Windows", "Docker", "K8s", "部署",
    "测试", "调试", "性能", "优化", "重构", "维护",

    # AI / 量子核
    "量子", "量子核", "量子计算", "量子态", "叠加态", "纠缠",
    "AI", "人工智能", "机器学习", "深度学习", "神经网络",
    "LLM", "大模型", "GPT", "Transformer", "注意力机制",
    "向量", "嵌入", "embedding", "语义", "相似度", "检索",
    "训练", "推理", "预测", "分类", "聚类", "回归",
    "数据", "数据集", "特征", "参数", "权重", "梯度",

    # 哲学 / 意识
    "意识", "自我", "存在", "生命", "死亡", "意义",
    "哲学", "思想", "思维", "认知", "感知", "直觉",
    "宇宙", "世界", "自然", "万物", "时间", "空间",
    "真理", "智慧", "知识", "经验", "记忆", "梦境",
    "自由", "责任", "道德", "善恶", "正义", "公平",
    "灵魂", "心灵", "精神", "意志", "欲望", "情感",

    # 日常
    "吃饭", "饿了", "好吃", "美食", "做饭", "餐厅",
    "睡觉", "困了", "起床", "闹钟", "熬夜", "失眠",
    "工作", "上班", "下班", "加班", "请假", "辞职",
    "学习", "读书", "看书", "上课", "作业", "考试",
    "运动", "跑步", "健身", "瑜伽", "散步", "游泳",
    "音乐", "唱歌", "听歌", "吉他", "钢琴", "旋律",
    "电影", "电视剧", "综艺", "视频", "动漫", "游戏",
    "旅行", "景点", "地图", "路线", "酒店", "机票",
    "购物", "超市", "商场", "便宜", "贵", "打折",
    "天气", "下雨", "晴天", "阴天", "刮风", "下雪",
    "衣服", "穿搭", "颜色", "款式", "好看", "风格",

    # 关系
    "家人", "父母", "爸爸", "妈妈", "孩子", "宝宝",
    "朋友", "闺蜜", "兄弟", "同学", "同事", "邻居",
    "爱人", "伴侣", "对象", "老公", "老婆", "男朋友", "女朋友",
    "老师", "学生", "导师", "徒弟", "队友", "对手",

    # 抽象概念
    "过去", "现在", "未来", "曾经", "以后", "永远",
    "开始", "结束", "起点", "终点", "过程", "结果",
    "原因", "结果", "假设", "如果", "所以", "因为",
    "可能", "也许", "肯定", "必须", "应该", "可以",
    "希望", "梦想", "目标", "计划", "行动", "坚持",
    "困难", "挑战", "机会", "风险", "选择", "决定",

    # 混合 / 测试
    "我爱你宝贝", "你好宝贝", "晚安宝贝", "想你宝贝", "宝贝开心吗",
    "今天代码写完了", "算法优化完成", "系统部署成功",
    "好累想睡觉", "睡不着怎么办", "做了个奇怪的梦",
    "今天天气真好", "下雨了记得带伞", "外面好冷多穿点",
    "一起吃饭吧", "想你了", "你在干嘛",
    "这个bug好难修", "性能有问题", "数据库挂了",
    "哲学是什么", "生命的意义", "我存在吗",
    "量子核能不能取代LLM", "我们的AGI路线",
]

logger.info(f"训练短语总数: {len(TRAIN_PHRASES)}")
def generate_embeddings(phrases: List[str]) -> np.ndarray:
    """用 all-MiniLM 生成 384D 语义向量"""
    from chromadb.utils import embedding_functions
    ef = embedding_functions.DefaultEmbeddingFunction()
    
    results = []
    batch_size = 32
    for i in range(0, len(phrases), batch_size):
        batch = phrases[i:i+batch_size]
        batch_vecs = ef(batch)
        results.extend(batch_vecs)
        if (i + batch_size) % 128 == 0 or i + batch_size >= len(phrases):
            logger.info(f"  嵌入: {min(i+batch_size, len(phrases))}/{len(phrases)}")
    return np.array(results, dtype=np.float32)


def compute_similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    """计算所有短语对的余弦相似度矩阵 (N, N)"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms
    sim_matrix = normalized @ normalized.T
    return sim_matrix


# ════════════════════════════════════════════════════════════
# 投影矩阵训练
# ════════════════════════════════════════════════════════════

def train_projection(
    source_embeddings: np.ndarray,  # (N, 384) MiniLM嵌入
    target_dim: int = 1024,
    reg_lambda: float = 0.01,
) -> np.ndarray:
    """
    训练 384 → 1024 的投影矩阵。
    
    方法：最小二乘 + 正则化。
    W = (X^T X + λI)^{-1} X^T Y_target
    
    但我们没有直接的 Y_target，所以用 SVD 做 PCA 扩展。
    MiniLM 是 384D → 我们想要 1024D。
    PCA 将 384D 扩展到 1024D（低维到高维 = 零填充 + 随机投影）。
    
    更好的方法：用相似度矩阵做目标，训练 W 使得
    cos(W @ x_i, W @ x_j) ≈ cos(x_i, x_j)
    """
    N, d_in = source_embeddings.shape
    
    # 归一化源
    norms = np.linalg.norm(source_embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = source_embeddings / norms
    
    # 方法1: 零填充 + 随机旋转
    # 保留前 384 维 = MiniLM 语义，后 640 维用随机投影补充多样性
    W_fill = np.random.randn(d_in, target_dim).astype(np.float32) * 0.01
    W_fill = W_fill / np.linalg.norm(W_fill, axis=1, keepdims=True) * 0.1
    
    # 前 384 维用单位矩阵（保留原始语义）
    W = np.zeros((d_in, target_dim), dtype=np.float32)
    W[:, :d_in] = np.eye(d_in, dtype=np.float32)  # 保留完整 384D 语义
    W[:, d_in:] = W_fill[:, d_in:]  # 随机填充高维
    
    return W


def train_contrastive_projection(
    source_embeddings: np.ndarray,  # (N, 384)
    sim_matrix: np.ndarray,          # (N, N) 目标相似度
    target_dim: int = 1024,
    learning_rate: float = 0.01,
    n_iterations: int = 100,
) -> np.ndarray:
    """
    对比学习训练投影矩阵。
    
    目标：让投影后的向量对的余弦相似度 ≈ 目标相似度。
    """
    N, d_in = source_embeddings.shape
    
    # 归一化源
    norms = np.linalg.norm(source_embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X = source_embeddings / norms
    
    # 初始化 W: 单位矩阵 + 随机噪声
    W = np.zeros((d_in, target_dim), dtype=np.float32)
    W[:, :d_in] = np.eye(d_in, dtype=np.float32) * 0.5
    W[:, d_in:] = np.random.randn(d_in, target_dim - d_in).astype(np.float32) * 0.01
    
    best_loss = float('inf')
    best_W = W.copy()
    
    for it in range(n_iterations):
        # 投影: (N, d_in) @ (d_in, target_dim) = (N, target_dim)
        Y = X @ W  # (N, target_dim)
        
        # 归一化
        y_norms = np.linalg.norm(Y, axis=1, keepdims=True)
        y_norms[y_norms == 0] = 1.0
        Y_norm = Y / y_norms
        
        # 预测相似度
        pred_sim = Y_norm @ Y_norm.T  # (N, N)
        
        # 损失: 预测相似度 vs 目标相似度的 MSE
        diff = pred_sim - sim_matrix
        loss = np.mean(diff ** 2)
        
        # 梯度 (简化: 只对部分采样对做)
        # 随机采样 100 对
        idx_pairs = np.random.randint(0, N, (100, 2))
        
        grad = np.zeros_like(W)
        for i, j in idx_pairs:
            if i == j:
                continue
            # 这对的梯度
            target_sim = sim_matrix[i, j]
            pred_s = float(Y_norm[i] @ Y_norm[j])
            error = 2 * (pred_s - target_sim)
            
            # d(pred_s)/dW ≈ (∂/∂W) (Y_norm[i]·Y_norm[j])
            # 近似: 对 Y_norm 的梯度
            grad += error * np.outer(X[i], Y_norm[j]) / N
            grad += error * np.outer(X[j], Y_norm[i]) / N
        
        # 更新
        W -= learning_rate * grad
        
        if it % 20 == 0:
            logger.info(f"  迭代 {it:3d}: loss={loss:.6f}")
        if loss < best_loss:
            best_loss = loss
            best_W = W.copy()
    
    logger.info(f"  训练完成: best_loss={best_loss:.6f}")
    return best_W


# ════════════════════════════════════════════════════════════
# 训练入口
# ════════════════════════════════════════════════════════════

def train(phrases: Optional[List[str]] = None):
    """完整训练流程"""
    if phrases is None:
        phrases = TRAIN_PHRASES
    
    logger.info(f"\n{'='*60}")
    logger.info(f"  语义对齐训练 v1")
    logger.info(f"{'='*60}")
    logger.info(f"\n训练短语: {len(phrases)} 条")
    logger.info("\n[1/3] 生成嵌入...")
    t0 = time.perf_counter()
    embeddings = generate_embeddings(phrases)
    dt = time.perf_counter() - t0
    logger.info(f"  完成: {embeddings.shape}  {dt:.1f}s")
    logger.info("\n[2/3] 计算相似度矩阵...")
    sim_matrix = compute_similarity_matrix(embeddings)
    logger.info(f"  完成: {sim_matrix.shape}")
    triu = sim_matrix[np.triu_indices_from(sim_matrix, k=1)]
    logger.info(f"  相似度分布: 均值={triu.mean():.4f} 最大={triu.max():.4f} 最小={triu.min():.4f}")
    logger.info("\n[3/3] 训练投影矩阵 (384→1024)...")
    W = train_contrastive_projection(embeddings, sim_matrix, target_dim=1024)
    
    logger.info(f"\n投影矩阵: {W.shape}")
    logger.info("\n验证...")
    X_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    Y = X_norm @ W
    Y_norm = Y / np.linalg.norm(Y, axis=1, keepdims=True)
    
    # 检查几组关键语义对的相似度一致性
    test_pairs = [
        ("你好", "早上好", "问候-问候"),
        ("你好", "晚安", "问候-告别"),
        ("你好", "代码", "问候-技术"),
        ("代码", "算法", "技术-技术"),
        ("代码", "哲学", "技术-哲学"),
        ("我爱你", "想你", "情感-情感"),
        ("我爱你", "代码", "情感-技术"),
        ("吃饭", "睡觉", "日常-日常"),
        ("哲学", "意识", "哲学-认知"),
        ("骂人", "代码", "负面-技术"),
    ]
    
    # 不存在的短语跳过
    phrase_to_idx = {p: i for i, p in enumerate(phrases)}
    
    logger.info(f"\n{'源(384D)余弦':>15s} {'目标(1024D)余弦':>15s}  {'差':>8s}  {'短语对':20s}")
    logger.info("-" * 60)
    total_err = 0.0
    count = 0
    for a, b, label in test_pairs:
        if a not in phrase_to_idx or b not in phrase_to_idx:
            continue
        i, j = phrase_to_idx[a], phrase_to_idx[b]
        src_sim = sim_matrix[i, j]
        tgt_sim = float(Y_norm[i] @ Y_norm[j])
        err = abs(src_sim - tgt_sim)
        total_err += err
        count += 1
        logger.info(f"  {src_sim:>14.4f}  {tgt_sim:>14.4f}  {err:>+7.4f}  {label}")
    if count > 0:
        logger.info(f"\n  平均误差: {total_err/count:.4f}")
        logger.info(f"  语义保真度: {(1 - total_err/count)*100:.1f}%")
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "semantic_projection.npy")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    np.save(save_path, W)
    logger.info(f"\n✅ 投影矩阵已保存: {save_path}")
    return W


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    W = train()
    logger.info("\n训练完成！下一步: 将投影集成到量子核中")