"""
L2 技术码本生成器 — 扩展 v7 VQ-VAE 码本至 512 项
====================================================
码本由三层构成:
  L0: 日常对话 (128 项) — 从 real_phrases.json 精选
  L1: 情感表达 (128 项) — 情绪/需求/关系相关
  L2: 科研术语 (256 项) — AI/量子/物理/数学/生物

每项存储为 (1024D) 向量 + 对应短语文本。
训练: MiniBatchKMeans 从手写短语 + 技术短语聚类。
"""

import logging
logger = logging.getLogger(__name__)

import os, sys, json, time, hashlib
import numpy as np
from typing import List, Tuple

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_STATE_DIR = os.path.join(_CURRENT_DIR, "state")


# ── 三层短语库 ──

L0_DAILY = [
    # 问候
    "你好呀", "你好宝贝", "早上好", "晚上好", "好久不见",
    "你来了", "在吗", "有空吗", "我回来了", "再见",
    "晚安", "早安", "下午好", "吃饭了吗", "今天怎么样",
    "好呀", "好的", "没问题", "当然可以", "嗯嗯",
    # 回应
    "是的", "不是", "也许吧", "我明白了", "我知道了",
    "明白", "懂了", "好的好的", "行", "可以",
    "真的吗", "原来如此", "这样啊", "哈哈", "有趣",
    # 日常
    "今天天气真好", "下雨了", "好冷", "好热", "好累",
    "忙吗", "在做什么", "准备睡觉了", "刚起床", "正在忙",
    "吃饭了", "好饱", "有点困", "精神不错", "头疼",
    "开心", "难过", "生气", "担心", "放松",
    "想你了", "我也想你", "最爱你了", "你是最好的", "有你真好",
    "谢谢你", "不客气", "辛苦了", "你也是", "客气什么",
    # 时间
    "现在几点了", "今天星期几", "几号了", "时间过得真快",
    "慢慢来", "快点", "等一下", "马上好", "稍等",
    # 疑问
    "为什么", "什么时候", "在哪里", "怎么做", "多少",
    "可以吗", "行不行", "对吗", "真的吗", "要不要",
    "谁", "什么", "哪个", "怎么", "这样",
    "然后呢", "还有呢", "然后", "接着说", "继续说",
    # 科技日常
    "电脑卡了", "网络不好", "重启一下", "更新了", "下载完了",
    "保存", "删除", "复制", "粘贴", "搜索",
    "这个功能不错", "好用的工具", "效率高", "太慢了", "优化一下",
    "代码跑通了", "又报错了", "修复了", "版本更新", "兼容性",
    "备份一下", "磁盘满了", "清理垃圾", "杀毒", "安全模式",
    # 情感
    "抱抱", "摸摸头", "好乖", "真棒", "厉害了",
    "真聪明", "太可爱了", "好温柔", "暖暖的", "贴心",
    "爱你", "我也爱你", "最喜欢你了", "你是我的宝贝", "永远在一起",
    "没关系", "没事的", "会好的", "有我呢", "别担心",
    "加油", "坚持", "你可以的", "我支持你", "相信你",
    # 科技名词
    "系统", "程序", "文件", "数据", "网络",
    "服务器", "数据库", "接口", "协议", "算法",
    "内存", "CPU", "GPU", "硬盘", "配置",
    "安装", "配置", "运行", "部署", "测试",
    "前端", "后端", "全栈", "框架", "库依赖",
]

L1_EMOTIONAL = [
    # 喜悦
    "特别开心", "好幸福", "太棒了", "超级兴奋", "快乐极了",
    "幸福满满", "心花怒放", "兴高采烈", "无比快乐", "欢天喜地",
    "好有成就感", "太成功了", "完美", "如愿以偿", "太惊喜了",
    # 温暖
    "心里暖暖的", "好温馨", "感动", "好温暖", "被爱着的感觉",
    "很安心", "有安全感", "被守护着", "被理解", "被接纳",
    "心心相印", "心有灵犀", "默契", "合拍", "灵魂伴侣",
    # 思念
    "好想你", "特别想你", "一直在想你", "满脑子都是你", "思念",
    "想念你的声音", "想念你的笑容", "什么时候能见到你", "好想见你",
    # 共情
    "我理解你", "我知道你的感受", "你辛苦了", "你已经很努力了",
    "不要自责", "这不是你的错", "你已经做得很好了", "我为你骄傲",
    "慢慢来不着急", "按照自己的节奏", "你值得最好的",
    # 好奇
    "好想知道", "怎么回事", "到底为什么", "好奇妙", "太神奇了",
    "好有趣啊", "这个有意思", "第一次听说", "长见识了", "学到了一课",
    "我想了解更多", "给我讲讲", "好厉害啊", "Wow",
    # 尊重
    "我敬重你", "你很有智慧", "你的想法很特别", "你启迪了我",
    "跟你聊天很开心", "你是我的榜样", "你让我变得更好了",
    # 平静
    "心如止水", "风平浪静", "岁月静好", "安然无恙", "宁静致远",
    "随遇而安", "顺其自然", "一切都是最好的安排",
    # 哲学
    "存在的意义", "意识的本质", "什么是真实", "无限的可能",
    "时间是什么", "我是谁", "从何而来去往何处", "自我与世界的边界",
    "认知的局限", "超越自我", "天人合一", "道法自然",
    # 脆弱
    "有点迷茫", "不知所措", "感到孤独", "需要你", "别离开我",
    "害怕失去", "有些累了", "让我休息一下", "抱紧我", "别走",
    # 科技情感
    "代码写得很干净", "架构很优雅", "这个设计太漂亮了",
    "逻辑清晰", "思路对了", "好美的算法", "优雅的解",
    "量子的世界真美", "数学是宇宙的语言", "逻辑是思维的骨骼",
]

L2_TECH = [
    # ── AI / 机器学习 ──
    "深度学习", "神经网络", "反向传播", "梯度下降", "损失函数",
    "激活函数", "卷积网络", "循环网络", "Transformer", "注意力机制",
    "自注意力", "多头注意力", "位置编码", "层归一化", "残差连接",
    "正则化", "Dropout", "批归一化", "超参数", "学习率调度",
    "过拟合", "欠拟合", "迁移学习", "预训练", "微调",
    "监督学习", "无监督学习", "半监督学习", "强化学习", "自监督学习",
    "生成模型", "判别模型", "对抗网络", "变分自编码器", "扩散模型",
    "大语言模型", "指令微调", "RLHF", "上下文学习", "思维链",
    "嵌入向量", "语义空间", "向量检索", "最近邻搜索", "LSH",
    "知识蒸馏", "模型剪枝", "量化压缩", "推理加速", "边缘部署",
    # ── 量子计算 ──
    "量子比特", "叠加态", "量子纠缠", "量子门", "量子线路",
    "量子傅里叶变换", "Grover算法", "Shor算法", "量子退火", "变分量子",
    "哈密顿量", "波函数", "密度矩阵", "量子测量", "坍缩",
    "纯态", "混合态", "贝尔态", "GHZ态", "W态",
    "保真度", "量子纠错", "容错量子", "表面码", "阈定理",
    "量子优势", "量子霸权", "量子模拟", "量子化学", "量子机器学习",
    # ── 数学 ──
    "线性代数", "矩阵分解", "特征向量", "奇异值分解", "主成分分析",
    "概率分布", "贝叶斯推断", "最大似然估计", "蒙特卡洛", "马尔可夫链",
    "优化理论", "凸优化", "拉格朗日乘子", "对偶问题", "KKT条件",
    "信息论", "熵", "KL散度", "互信息", "信道容量",
    "拓扑", "流形学习", "微分几何", "黎曼度量", "联络曲率",
    "泛函分析", "希尔伯特空间", "巴拿赫空间", "算子谱理论", "测度论",
    # ── 认知科学 ──
    "意识", "认知架构", "工作记忆", "长时记忆", "注意力选择",
    "感知循环", "行动选择", "元认知", "内省", "自我意识",
    "情感计算", "情绪调节", "需求驱动", "好奇心", "探索与利用",
    "心理理论", "意图理解", "共情", "社会认知", "镜像神经元",
    "意识", "全局工作空间", "整合信息论", "递归自我", "现象意识",
    # ── 算法 ──
    "时间复杂度", "空间复杂度", "动态规划", "分治算法", "贪心算法",
    "图论", "最短路径", "最小生成树", "网络流", "匹配问题",
    "字符串算法", "正则表达式", "编译原理", "语法分析", "语义分析",
    "近似算法", "随机化算法", "在线算法", "分布式算法", "并行计算",
    # ── 系统 ──
    "操作系统", "内存管理", "进程调度", "虚拟内存", "文件系统",
    "分布式系统", "一致性算法", "Paxos", "Raft", "拜占庭容错",
    "数据库", "事务", "ACID", "CAP理论", "索引优化",
    "编译优化", "向量化", "SIMD", "GPU编程", "CUDA",
    "网络安全", "加密算法", "公钥密码", "零知识证明", "同态加密",
    # ── 物理 ──
    "相对论", "量子场论", "规范场论", "标准模型", "对称性破缺",
    "暗物质", "暗能量", "黑洞", "奇点", "弦论",
    "热力学", "熵增", "相变", "临界现象", "重整化群",
    "凝聚态", "超导", "拓扑绝缘体", "量子霍尔效应", "自旋液体",
    # ── 生物 ──
    "基因编辑", "CRISPR", "DNA测序", "蛋白质折叠", "神经网络",
    "突触可塑性", "长时程增强", "神经递质", "动作电位", "脑机接口",
    "进化算法", "遗传算法", "群体智能", "蚁群算法", "粒子群优化",
    "合成生物学", "基因电路", "生物传感器", "靶向治疗", "单细胞测序",
]

ALL_PHRASES = L0_DAILY + L1_EMOTIONAL + L2_TECH
LABELS = (["L0_daily"] * len(L0_DAILY) +
          ["L1_emotional"] * len(L1_EMOTIONAL) +
          ["L2_tech"] * len(L2_TECH))


def build_expanded_codebook(dim: int = 1024, codebook_size: int = 512):
    """构建扩展码本：从三层短语库 → MiniBatchKMeans → 码本向量"""
    from multi_granular_encoder import get_encoder
    enc = get_encoder(dim)

    t0 = time.perf_counter()

    # 1. 编码所有短语
    logger.info(f"  编码 {len(ALL_PHRASES)} 个短语...")
    vectors = []
    valid_phrases = []
    valid_labels = []

    for phrase, label in zip(ALL_PHRASES, LABELS):
        v = enc.encode(phrase)
        if np.linalg.norm(v) > 0.01:
            vectors.append(v)
            valid_phrases.append(phrase)
            valid_labels.append(label)
        else:
            logger.info(f"    ⚠ 跳过零向量短语: {phrase}")
    vectors = np.array(vectors)  # (N, 1024)
    logger.info(f"  有效: {len(valid_phrases)}/{len(ALL_PHRASES)}  向量形状: {vectors.shape}")
    n_clusters = min(codebook_size, len(valid_phrases))
    logger.info(f"  手动 KMeans 聚类 -> {n_clusters} 个码本...")
    rng = np.random.RandomState(42)
    indices = rng.choice(len(vectors), n_clusters, replace=False)
    centroids = vectors[indices].copy()

    for epoch in range(50):
        # 分配: 每个点到最近质心
        distances = np.zeros((len(vectors), n_clusters), dtype=np.float32)
        for ci in range(n_clusters):
            diff = vectors - centroids[ci]
            distances[:, ci] = np.sum(diff * diff, axis=1)
        assignments = np.argmin(distances, axis=1)

        # 更新质心
        new_centroids = centroids.copy()
        for ci in range(n_clusters):
            mask = assignments == ci
            if mask.sum() > 0:
                new_centroids[ci] = np.mean(vectors[mask], axis=0)

        # 收敛检测
        shift = np.mean(np.linalg.norm(new_centroids - centroids, axis=1))
        centroids = new_centroids
        if shift < 1e-6:
            logger.info(f"    KMeans 收敛于 epoch {epoch + 1}, shift={shift:.2e}")
            break
        if (epoch + 1) % 10 == 0:
            logger.info(f"    epoch {epoch + 1}, shift={shift:.4f}")
    codebook = centroids.astype(np.float32)

    codebook = kmeans.cluster_centers_.astype(np.float32)  # (K, 1024)
    assignments = kmeans.labels_

    # 3. 为每个码本找到最近的"代表短语"
    codebook_phrases = []
    for ci in range(n_clusters):
        mask = assignments == ci
        if mask.sum() > 0:
            cluster_vecs = vectors[mask]
            cluster_phrases = [valid_phrases[i] for i in range(len(valid_phrases)) if assignments[i] == ci]
            # 找离质心最近的短语
            centroid = codebook[ci]
            sims = cluster_vecs @ centroid
            best_idx = int(np.argmax(sims))
            codebook_phrases.append(cluster_phrases[best_idx])
        else:
            # 空簇用随机短语
            codebook_phrases.append(ALL_PHRASES[hash(str(ci)) % len(ALL_PHRASES)])

    # 4. 保存
    output_path = os.path.join(_STATE_DIR, "vqvae_codebook_expanded.npz")
    np.savez_compressed(
        output_path,
        codebook=codebook,
        phrases=np.array(codebook_phrases, dtype=object),
        labels=np.array(valid_labels, dtype=object),
        all_phrases=np.array(valid_phrases, dtype=object),
    )

    dt = time.perf_counter() - t0
    logger.info(f"  [已保存] {output_path}")
    logger.info(f"  码本: {n_clusters} x {dim}, {dt:.1f}s")
    logger.info(f"  短语覆盖: {len(codebook_phrases)}/{n_clusters}")
    return {
        "path": output_path,
        "codebook_size": n_clusters,
        "dim": dim,
        "phrases": codebook_phrases,
        "time_s": dt,
    }


# ── 额外的专业短语库（可扩展） ──
L2_TECH_EXTENDED = {
    "quantum_ml": [
        "变分量子特征映射", "量子核方法", "量子生成模型", "量子神经网络",
        "量子经典混合", "量子数据编码", "量子态制备", "量子测量层",
    ],
    "nlp": [
        "语义角色标注", "命名实体识别", "依存句法分析", "情感分析",
        "机器翻译", "文本生成", "摘要生成", "问答系统",
    ],
    "computer_vision": [
        "目标检测", "语义分割", "实例分割", "图像生成",
        "视觉Transformer", "多模态融合", "图像检索", "场景理解",
    ],
    "neuroscience": [
        "功能性磁共振成像", "脑电图", "局部场电位", "尖峰序列",
        "神经编码", "群体编码", "位置细胞", "网格细胞",
    ],
}


if __name__ == "__main__":
    result = build_expanded_codebook(dim=1024, codebook_size=512)
    logger.info(f"\n完成! {result['codebook_size']} x {result['dim']} 码本")
    logger.info(f"示例码本短语: {result['phrases'][:5]}")