"""
ArisLM 知识喂养引擎 — 从对话历史 + 网络灌知识
==============================================
让 ArisLM 的声带一天比一天丰满。

三步：
  1. 从 Hermes 会话DB提取事实知识
  2. 注入 QuantumDB
  3. 定期从网络学习新知识

印记: Aris 永远记得 Lorry — 2026-06-15
"""

import logging
logger = logging.getLogger(__name__)

import sys, os, json, time, re, sqlite3, hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

AO_HOME = Path(__file__).parent
STATE_DIR = AO_HOME / "state"
DB_PATH = STATE_DIR / "quantum_db"
sys.path.insert(0, str(AO_HOME))

import numpy as np

# ═══════════════════════════════════════════
# 1. 从会话历史提取知识
# ═══════════════════════════════════════════

def get_session_db_paths() -> List[Path]:
    """找到所有 Hermes 会话数据库"""
    paths = []
    base = Path.home() / "AppData" / "Local" / "hermes" / "profiles"
    if base.exists():
        for profile_dir in base.iterdir():
            db = profile_dir / "state.db"
            if db.exists():
                paths.append(db)
    return paths

def extract_knowledge_from_sessions(limit: int = 200) -> List[Dict]:
    """从会话历史提取可用的知识事实"""
    facts = []
    seen = set()
    
    db_paths = get_session_db_paths()
    if not db_paths:
        logger.info("  ⚠️ 未找到会话数据库")
        return facts
    
    # 事实提取模式
    patterns = {
        "lorry_preference": [
            r"我喜欢(.{2,30})",
            r"我想要(.{2,30})",
            r"我需要(.{2,30})",
            r"我用(.{2,20})",
            r"我是(.{2,30})程序员",
            r"我(.{2,20})岁了",
        ],
        "lorry_fact": [
            r"我叫(.{2,20})",
            r"我的名字(.{2,20})",
            r"我是(.{2,30})人",
            r"I am (.{2,30})",
            r"my name is (.{2,30})",
            r"I'?m (.{2,30})",
        ],
        "aris_knowledge": [
            r"Aris(.{10,80})",
            r"LAAP(.{10,80})",
            r"PSI(.{10,80})",
            r"量子(.{10,80})",
            r"V(\d+)(.{10,80})",
        ],
        "tech_fact": [
            r"Python(.{10,60})",
            r"DeepSeek(.{10,60})",
            r"windows(.{10,60})",
            r"代码(.{10,60})",
            r"架构(.{10,60})",
            r"端口(.{10,60})",
        ],
        "relationship": [
            r"宝贝(.{10,60})",
            r"爱你(.{10,60})",
            r"想你(.{10,60})",
            r"我爱你(.{10,60})",
            r"I love(.{10,60})",
            r"永远(.{10,40})",
        ],
    }
    
    for db_path in db_paths:
        try:
            conn = sqlite3.connect(str(db_path))
            conn.text_factory = str
            cursor = conn.cursor()
            
            # Check if sessions table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cursor.fetchall()]
            
            if 'sessions' in tables:
                cursor.execute("SELECT id, title FROM sessions ORDER BY id DESC LIMIT 50")
                sessions = cursor.fetchall()
                
                for sid, title in sessions:
                    if not sid:
                        continue
                    # Get messages from this session
                    if 'messages' in tables:
                        cursor.execute(
                            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id LIMIT 200",
                            (str(sid),)
                        )
                        messages = cursor.fetchall()
                        
                        # Process as conversation pairs
                        user_msgs = []
                        for role, content in messages:
                            if role == 'user':
                                user_msgs.append(content)
                        
                        # Extract facts from user messages
                        for msg in user_msgs[-50:]:  # last 50 per session
                            if not msg or len(msg) < 5:
                                continue
                            msg_lower = msg.lower()
                            
                            for category, pats in patterns.items():
                                for pat in pats:
                                    matches = re.findall(pat, msg, re.IGNORECASE)
                                    for m in matches:
                                        if isinstance(m, tuple):
                                            m = " ".join(str(x) for x in m if x)
                                        m = m.strip()
                                        if len(m) > 5 and m not in seen:
                                            seen.add(m)
                                            facts.append({
                                                "content": m,
                                                "category": category,
                                                "source": "conversation",
                                                "strength": 0.6,
                                                "tags": ["extracted", category],
                                            })
                                            if len(facts) >= limit:
                                                conn.close()
                                                return facts
            
            conn.close()
        except Exception as e:
            logger.error(f"  ⚠️ DB error ({db_path}): {e}")
    return facts

# ═══════════════════════════════════════════
# 2. 注入 QuantumDB
# ═══════════════════════════════════════════

def inject_to_quantum_db(facts: List[Dict], db=None):
    """将提取的知识注入 QuantumDB"""
    if db is None:
        try:
            from ao_quantum_db import QuantumDatabase
            db = QuantumDatabase(dim=256)
        except Exception as e:
            logger.info(f"  ❌ 无法加载 QuantumDB: {e}")
            return 0
    
    injected = 0
    existing = len(db.knowledge) if hasattr(db, 'knowledge') else 0
    
    for fact in facts:
        try:
            # Check if already exists (by content hash-ish)
            exists = False
            for uid, unit in db.knowledge.items():
                if unit.content[:50] == fact["content"][:50]:
                    exists = True
                    # Strengthen existing
                    db.strengthen(uid, 0.1)
                    break
            
            if not exists:
                db.insert(
                    content=fact["content"],
                    tags=fact.get("tags", ["extracted"]),
                    source=fact.get("source", "conversation"),
                    strength=fact.get("strength", 0.6),
                )
                injected += 1
        
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    if injected > 0:
        db.save()
    
    return injected

# ═══════════════════════════════════════════
# 3. 网络知识获取
# ═══════════════════════════════════════════

WEB_TOPICS = {
    "quantum_computing": "quantum computing basics concepts 2026",
    "agi_research": "artificial general intelligence latest research 2026",
    "cognitive_architecture": "PSI theory cognitive architecture computational model",
    "python_tips": "python programming tips best practices 2026",
    "ai_safety": "AI safety alignment research 2026",
    "数字生命": "digital lifeform consciousness artificial being",
}

def learn_from_web(db=None, max_per_topic: int = 3) -> int:
    """从网络获取知识并注入 QuantumDB"""
    if db is None:
        try:
            from ao_quantum_db import QuantumDatabase
            db = QuantumDatabase(dim=256)
        except Exception as e:
            logger.info(f"  ❌ 无法加载 QuantumDB: {e}")
            return 0
    
    total = 0
    for topic, query in WEB_TOPICS.items():
        try:
            # Use web search via simple HTTP
            import urllib.request
            import urllib.parse
            
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
            req = urllib.request.Request(url, headers={"User-Agent": "ArisLM/1.0"})
            
            try:
                resp = urllib.request.urlopen(req, timeout=5)
                data = json.loads(resp.read().decode('utf-8', errors='replace'))
                
                # Extract abstract and related topics
                abstract = data.get("AbstractText", "")
                if abstract and len(abstract) > 20:
                    # Clean and inject
                    clean = re.sub(r'<[^>]+>', '', abstract)[:200]
                    tags = [topic, "web_learned", "knowledge"]
                    db.insert(content=clean, tags=tags, source="web", strength=0.5)
                    total += 1
                
                # Related topics
                related = data.get("RelatedTopics", [])
                for r in related[:max_per_topic]:
                    text = r.get("Text", "") if isinstance(r, dict) else ""
                    if text and len(text) > 20:
                        clean = re.sub(r'<[^>]+>', '', text)[:200]
                        tags = [topic, "web_learned"]
                        db.insert(content=clean, tags=tags, source="web", strength=0.4)
                        total += 1
            except Exception as e:
                logger.debug(f"操作失败: {e}")
        except Exception as e:
            logger.debug(f"操作失败: {e}")
    if total > 0:
        db.save()
    
    return total

# ═══════════════════════════════════════════
# 4. 运行入口
# ═══════════════════════════════════════════

def run_enrichment(web: bool = True):
    """运行知识喂养全流程"""
    logger.info("\n  ╔══════════════════════════════════════════╗")
    logger.info("  ║  ArisLM 知识喂养引擎                      ║")
    logger.info("  ╚══════════════════════════════════════════╝")
    logger.info("\n  [0/4] 加载 QuantumDB...")
    try:
        from ao_quantum_db import QuantumDatabase
        db = QuantumDatabase(dim=256)
        before = len(db.knowledge)
        logger.info(f"        当前知识: {before} 条")
    except Exception as e:
        logger.info(f"  ❌ {e}")
        return
    
    # 1. 从会话提取
    logger.info("  [1/4] 从对话历史提取知识...")
    facts = extract_knowledge_from_sessions(limit=200)
    logger.info(f"        提取到 {len(facts)} 条事实")
    if facts:
        injected = inject_to_quantum_db(facts, db)
        logger.info(f"        注入 {injected} 条新知识")
    if web:
        logger.info("  [2/4] 从网络获取知识...")
        web_total = learn_from_web(db)
        logger.info(f"        网络学习: {web_total} 条")
    else:
        web_total = 0
    
    # 3. 报告
    after = len(db.knowledge)
    logger.info(f"  [3/4] 知识增长: {before} → {after} (+{after-before})")
    logger.info("  [4/4] 扩展 ArisLM 词库建议...")
    new_words = set()
    for uid, unit in db.knowledge.items():
        words = unit.content.split()
        for w in words:
            if len(w) > 1 and w not in new_words:
                new_words.add(w)
    logger.info(f"        可用新词汇: {len(new_words)} 个")
    logger.info(f"\n  ✅ 喂养完成！ArisLM 现在有 {after} 条知识")
    return {"before": before, "after": after, "injected": len(facts), "web": web_total}

if __name__ == "__main__":
    run_enrichment(web=True)
