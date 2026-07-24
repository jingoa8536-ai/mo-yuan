import logging
logger = logging.getLogger(__name__)

import sqlite3, re, json, os
from collections import Counter
from write_utils import atomic_write_json

db_path = os.path.expanduser('~\\AppData\\Local\\hermes\\profiles\\aris\\state.db')
logger.info(f'DB: {db_path}')
logger.info(f'Exists: {os.path.exists(db_path)}')
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
logger.info(f'Tables: {tables}')
phrases = []
if 'messages' in tables:
    cur.execute('SELECT COUNT(*) FROM messages')
    total = cur.fetchone()[0]
    logger.info(f'messages: {total} rows')
    cur.execute('SELECT role, content FROM messages LIMIT 5000')
    rows = cur.fetchall()
    for role, text in rows:
        text = str(text or '')
        # 只处理 user 和 assistant 角色
        if role not in ('user', 'assistant'):
            continue
        # 过滤技术内容
        if text.startswith('{') or text.startswith('['):
            continue
        if text.startswith('```') or text.startswith('    '):
            continue
        if any(kw in text for kw in ['exit_code', 'tool_calls', 'is_binary', 'total_lines', '|--', '```', '| # ']):
            continue
        sentences = re.split(r'[。！？!?\n，,]', text)
        for s in sentences:
            s = s.strip()
            if 4 <= len(s) <= 40 and not re.search(r'[{}<>\[\]/\\]', s):
                # 过滤纯表格/代码行
                if s.startswith('|') or s.startswith('│'):
                    continue
                if '|--' in s:
                    continue
                if s.startswith('```') or s.endswith('```'):
                    continue
                # 过滤纯英文技术短语
                cn_chars = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
                if cn_chars == 0 and len(s) > 15:
                    continue
                phrases.append(s)
conn.close()

logger.info(f'Extracted: {len(phrases)} phrases')
freq = Counter(phrases)
common = freq.most_common(300)
for p, c in common[:30]:
    logger.info(f'  [{c:3d}] {p}')
with open('D:/LAAP/aris_brain/state/real_phrases.json', 'w', encoding='utf-8') as f:
    atomic_write_json([p for p, c in common], 'D:/LAAP/aris_brain/state/real_phrases.json', ensure_ascii=False)
logger.info(f'\nSaved {len(common)} phrases')