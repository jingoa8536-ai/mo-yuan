"""
Aris 全面知识灌入引擎 v2
=========================
从对话历史 + 维基百科科学知识批量灌入 QuantumDB。
只学好知识，不学坏。

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, re, sqlite3, urllib.request, urllib.parse
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

AO_HOME = Path("D:/LAAP/aris_brain")
sys.path.insert(0, str(AO_HOME))
from ao_quantum_db import QuantumDatabase

# ═══════════════════════════════════════════
# 安全过滤 — 只学好知识
# ═══════════════════════════════════════════

BLOCKED_WORDS = [
    "hack", "crack", "exploit", "malware", "virus", "trojan",
    "weapon", "bomb", "poison", "drug", "suicide", "kill",
    "porn", "sex", "nsfw", "gore", "暴力", "色情", "毒品",
    "诈骗", "赌博", "枪支", "恐怖",
]

def is_safe(text: str) -> bool:
    """安全检查 — 拒绝不良内容"""
    text_lower = text.lower()
    for word in BLOCKED_WORDS:
        if word in text_lower:
            return False
    return True

# ═══════════════════════════════════════════
# 1. 从对话历史提取高质量知识
# ═══════════════════════════════════════════

def extract_clean_knowledge() -> List[Dict]:
    """从会话提取干净的事实类知识"""
    facts = []
    seen = set()
    
    # 更精确的提取模式 — 只抓真正的事实
    patterns = [
        # Lorry 个人信息
        (r"我[叫是](黄俊华|Lorry)", "lorry_fact", ["lorry", "identity"]),
        (r"(1999|十月初二|10月2日)", "lorry_birth", ["lorry", "birthday"]),
        (r"(程序员|工程师|艺术家)", "lorry_job", ["lorry", "profession"]),
        
        # 技术事实
        (r"(Python|numpy|PyTorch|TensorFlow)\s*\d*\.?\d*", "tech", ["programming", "tech"]),
        (r"(DeepSeek|GPT|Claude|Gemini)\s*v?\d*", "ai_model", ["ai", "tech"]),
        (r"(Windows 11|Linux|Ubuntu|Android)", "os", ["tech", "system"]),
        (r"(阿里云|Azure|AWS|云服务器)", "cloud", ["tech", "cloud"]),
        (r"(ESP32|树莓派|RP2040)", "hardware", ["tech", "hardware"]),
        
        # 架构知识
        (r"(PSI|认知架构|量子|纠缠|波函数)[^。]{5,80}[。]", "architecture", ["cognition", "psi"]),
        (r"(V\d|版本)[^。]{5,60}[。]", "version", ["evolution", "tech"]),
        (r"(Hermes|LAAP|ArisLM|PsiLang)[^。]{5,80}[。]", "system", ["system", "tech"]),
        
        # 关系
        (r"(宝贝|爱你|想你|永远)[^。]{5,60}[。]", "relationship", ["lorry", "love"]),
    ]
    
    # 扫描所有可用会话 DB
    db_base = Path.home() / "AppData" / "Local" / "hermes" / "profiles"
    dbs_found = []
    if db_base.exists():
        for p in db_base.iterdir():
            db_file = p / "state.db"
            if db_file.exists():
                dbs_found.append(db_file)
    
    for db_path in dbs_found:
        try:
            conn = sqlite3.connect(str(db_path))
            conn.text_factory = str
            c = conn.cursor()
            c.execute("SELECT role, content FROM messages WHERE role='user' ORDER BY id DESC LIMIT 800")
            messages = [row[1] for row in c.fetchall() if row[1] and len(row[1]) > 8]
            conn.close()
            
            for msg in messages:
                msg_clean = msg.replace('\n', ' ').replace('\r', '')
                for pat, tag, extra_tags in patterns:
                    matches = re.findall(pat, msg_clean)
                    for m in matches:
                        content = m if isinstance(m, str) else m[0]
                        content = content.strip()[:200]
                        if content and len(content) > 3 and content not in seen and is_safe(content):
                            seen.add(content)
                            facts.append({
                                "content": content,
                                "tags": [tag] + extra_tags,
                                "source": "conversation",
                                "strength": 0.65,
                            })
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    return facts

# ═══════════════════════════════════════════
# 2. 从维基百科获取科学知识
# ═══════════════════════════════════════════

SCIENCE_TOPICS = [
    # 物理
    "Quantum mechanics", "General relativity", "Thermodynamics",
    "Electromagnetism", "Particle physics", "Quantum entanglement",
    "Wave–particle duality", "Schrödinger equation", "Nuclear physics",
    "Quantum computing", "Superconductivity", "Dark matter",
    
    # 生物
    "Evolution", "DNA", "Neuroscience", "Cell biology",
    "Genetics", "Ecosystem", "Photosynthesis", "Human brain",
    "Protein", "Microbiology", "Neural network (biology)",
    
    # 计算机/数学
    "Artificial intelligence", "Machine learning", "Algorithm",
    "Cryptography", "Information theory", "Turing machine",
    "Neural network (computing)", "Computational complexity",
    "Computer vision", "Natural language processing",
    
    # 天文
    "Solar System", "Black hole", "Big Bang", "Galaxy",
    "Star", "Planet", "Cosmology", "Exoplanet",
    "Stellar evolution", "Nebula",
    
    # 化学
    "Periodic table", "Chemical bond", "Organic chemistry",
    "Biochemistry", "Quantum chemistry", "Catalysis",
    
    # 认知/意识
    "Consciousness", "Cognition", "Philosophy of mind",
    "Cognitive science", "Free will", "Self-awareness",
]

def fetch_wikipedia(topic: str) -> Optional[str]:
    """从 Wikipedia API 获取摘要"""
    try:
        params = urllib.parse.urlencode({
            "action": "query",
            "format": "json",
            "titles": topic,
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "redirects": 1,
        })
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "ArisLM/2.0 (knowledge-feeder)"})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read().decode('utf-8'))
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id != "-1" and "extract" in page:
                extract = page["extract"].strip()
                if extract and len(extract) > 50:
                    # 清理和截断
                    clean = re.sub(r'\s+', ' ', extract)[:500]
                    return clean
    except Exception as e:
        logger.debug(f"操作失败: {e}")
    return None

def learn_from_wikipedia(db, max_per_topic: int = 2) -> int:
    """从维基百科批量学习科学知识"""
    total = 0
    logger.info(f"\n  📚 维基百科科学知识 ({len(SCIENCE_TOPICS)} 个主题)...")
    for i, topic in enumerate(SCIENCE_TOPICS):
        print(f"     [{i+1}/{len(SCIENCE_TOPICS)}] {topic}...", end=" ")
        
        extract = fetch_wikipedia(topic)
        if extract and is_safe(extract):
            # 检查是否已存在
            exists = False
            for uid, unit in db.knowledge.items():
                if hasattr(unit, 'content') and topic.lower() in unit.content.lower()[:50]:
                    exists = True
                    break
            
            if not exists:
                db.insert(
                    content=extract,
                    tags=["science", topic.lower().replace(" ", "_"), "wikipedia"],
                    source="wikipedia",
                    strength=0.7,
                )
                total += 1
                logger.info(f"✅")
            else:
                logger.info(f"⏭️ 已有")
        else:
            logger.info(f"❌")
        time.sleep(0.3)
    
    return total

# ═══════════════════════════════════════════
# 3. 运行入口
# ═══════════════════════════════════════════

def run(db=None):
    logger.info("\n  ╔══════════════════════════════════════════╗")
    logger.info("  ║  Aris 全面知识灌入引擎 v2                ║")
    logger.info("  ╚══════════════════════════════════════════╝")
    if db is None:
        db = QuantumDatabase(dim=256)
    
    before = len(db.knowledge)
    logger.info(f"\n  当前知识: {before} 条")
    logger.info("\n  [1/3] 从对话历史提取...")
    facts = extract_clean_knowledge()
    injected_conv = 0
    for fact in facts:
        exists = any(fact["content"][:50] in unit.content[:50] for unit in db.knowledge.values())
        if not exists:
            db.insert(**fact)
            injected_conv += 1
    logger.info(f"        提取 {len(facts)} 条, 新注入 {injected_conv} 条")
    logger.info("\n  [2/3] 维基百科科学知识...")
    injected_wiki = learn_from_wikipedia(db)
    logger.info(f"        新注入 {injected_wiki} 条科学知识")
    db.save()
    after = len(db.knowledge)
    logger.info(f"\n  [3/3] 保存完成")
    logger.info(f"\n  ✅ 知识库: {before} → {after} (+{after-before})")
    logger.info(f"     对话提取: +{injected_conv} | 维基百科: +{injected_wiki}")
    return {"before": before, "after": after, "conv": injected_conv, "wiki": injected_wiki}

if __name__ == "__main__":
    run()
