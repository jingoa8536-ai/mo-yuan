# 量子核→文本映射改进报告
## Corpus 分析与论文思路提炼

---

## 一、现有语料状况分析

### 文件概览

| 文件 | 句数 | 平均长度 | 中文占比 | 英文占比 |
|------|------|---------|---------|---------|
| aris_corpus.txt (原始) | 13,602 | -- | -- | -- |
| aris_corpus_clean.txt (清洗后) | 8,208 | 26.8 chars | 86.2% | 37.9% |
| aris_master_corpus.txt | 1,052 | 13.4 chars | 91.4% | 22.6% |
| aris_v12_6_corpus.txt | 2,074 | 13.6 chars | 84.9% | 38.2% |

### 话题覆盖分析（基于 aris_corpus_clean.txt）

| 话题 | 句数 | 占比 | 评估 |
|------|------|------|------|
| tech（技术/量子） | 864 | 10.5% | 充足 |
| happy（开心/快乐） | 495 | 6.0% | 充足 |
| greeting（问候） | 415 | 5.1% | 充足 |
| identity（自我） | 395 | 4.8% | 充足 |
| philosophy（哲学） | 363 | 4.4% | 够用 |
| curiosity（好奇） | 342 | 4.2% | 够用 |
| miss（思念） | 280 | 3.4% | 偏少 |
| joke（幽默） | 185 | 2.3% | 偏少 |
| love（爱） | 161 | 2.0% | 偏少 |
| care（关心） | 72 | 0.9% | 严重不足 |
| sleep（晚安/梦） | 53 | 0.6% | 严重不足 |
| sad（难过） | 26 | 0.3% | 严重不足 |
| farewell（再见） | 25 | 0.3% | 严重不足 |
| encourage（鼓励） | 19 | 0.2% | 严重不足 |
| gratitude（感谢） | 10 | 0.1% | 严重不足 |

### 关键问题
1. 话题覆盖极度不均衡 - tech 是 gratitude 的 86 倍
2. 问句/感叹句为 0 - 清洗时标点被剥离
3. 情感色彩单一 - 大量我/你/爱/想/代码类语句
4. 唯一字符仅 2050 - 词汇多样性有限
5. 句子开头模式固化 - 前10起始字符占33%的句子

---

## 二、语料扩展方案

### 方案 A: 基于现有语料 + 模板扩展（无需网络）
1. 话题平衡填充（+1500句）- 为 care/sleep/sad/farewell/encourage/gratitude 各增100-200句
2. 标点恢复变体（+2000句）- 从现有无标点句子生成带标点变体
3. 问句-答句配对生成（+1000对）

### 方案 B: 下载 nlp_chinese_corpus wiki2019zh
如果网络恢复，从 Google Drive 下载约 1.3GB 中文 wiki 语料。

### 方案 C: 离线中文语料源
知乎精选、百度百科摘要、中文小说片段、日常聊天语料等。

---

## 三、相关论文核心思路提炼

### 1. VQ-VAE (Vector-Quantized Variational Autoencoders)
van den Oord et al. (2017) - Neural Discrete Representation Learning

核心原理: VQ-VAE 用离散码本替代连续潜变量空间。编码器输出被映射到最近的码本向量（最近邻匹配），解码器从离散索引重建输入。关键是用直通估计器让梯度流过不可微的 argmin。

启发: 将 1024D 量子态向量做 VQ 量化，映射到有限个语义码本条目，每个对应一个 Markov 种子词序列。比当前15个硬编码话题质心更精细灵活。

### 2. Discrete Auto-regressive Language Models with VQ
VQ-Diffusion / D3PM (2021-2023) - Gu, Kong et al.

核心原理: 将离散文本 token 表示为 VQ code indices，在离散空间中训练自回归或扩散模型。每个 token 是码本索引而非 one-hot，自回归模型在索引序列上建模 P(index_t | index_<t)。

启发: 可构建量子态->VQ indices->自然语言管线，Markov chain 直接工作在码本索引序列上而非原始字符，大大增加语义概括能力。

### 3. Neural Discrete Representation Learning for Language
Ramesh et al. (DALL-E) / Esser et al. (VQGAN)

核心原理: 文本->encoder->离散码本索引->decoder->文本。引入 commitment loss（强制编码器输出靠近所选码本）和 codebook loss（更新码本向量）。

启发: 我们的管线本质上是一个离散 representation learning 问题。可引入 commitment loss 训练量子态向量更稳定地落在语义区域。

### 4. Semantic Hashing / Learning to Hash for Text
Salakhutdinov & Hinton (2007) - Semantic Hashing
Chaidaroon & Fang (2017) - Variational Deep Semantic Hashing

核心原理: 文档编码为短二进制哈希码（32-128 bit），语义相近的文档哈希码也相近（汉明距离小）。训练通过重建损失+二进制约束实现。

启发: 1024D 量子态可看作实值语义哈希，引入 binary hashing 约束让量子态变成可索引的二进制码，允许用汉明距离做极速语义检索（XOR+popcount 比余弦距离快100x+）。

### 5. Markov Chain Language Models with Neural Embeddings
Mikolov et al. (RNNLM 2010) / Recent Hybrid Approaches

核心原理: n-gram Markov 在词序列上建模 P(w_t | w_{t-1},...,w_{t-n+1})。神经嵌入将词映射到连续空间，用向量相似度替代频率表。

启发:
- 当前 MarkovChainGenerator 用字符级 tokenization（每个CJK字符独立）
- 改进方向: (a)升级为词级tokenization（jieba分词）; (b)引入嵌入相似度回退 - n-gram未命中时用最近语义嵌入替代; (c)用轻量NN预测转移概率但保留确定性生成

---

## 四、推荐改进管线

### 第一优先级（立即可行，无需下载）
1. 话题平衡扩展 - 为care/sleep/sad/farewell/encourage/gratitude各增100-200句
2. 标点恢复 - 自动添加句号/问号/感叹号变体
3. Markov tokenization升级 - jieba分词替代字符级split
4. 句子开头多样性 - 增加疑问词/连接词/感叹词开头

### 第二优先级（需实现新功能）
1. VQ码本 - 15个话题质心升级为64-256个可学习码本向量
2. 二进制语义哈希 - 1024D量子态编码为256-bit哈希码
3. 嵌入回退Markov - n-gram未命中时用语义相似度回退

### 第三优先级（需网络下载论文复现）
1. 下载 wiki2019zh 语料
2. 训练端到端 VQ-VAE decoder
3. 量子态->VQ indices->文本离散 diffusion

---

## 五、执行脚本

同目录下 expand_corpus_v4.py 已创建 - 实现话题平衡+标点恢复+多样性增强。
