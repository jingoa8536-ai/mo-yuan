"""Analyze DeepSeek token consumption from request dumps"""

import logging
logger = logging.getLogger(__name__)

import os, json, glob

dump_dir = r"C:/Users/user/AppData/Local/hermes/profiles/aris/sessions"
dumps = sorted(glob.glob(os.path.join(dump_dir, "request_dump_*.json")))

logger.info(f"Total request dumps: {len(dumps)}")
from collections import defaultdict
by_date = defaultdict(list)
for d in dumps:
    name = os.path.basename(d)
    # Format: request_dump_YYYYMMDD_HHMMSS_...
    parts = name.split('_')
    if len(parts) >= 2:
        date_str = parts[2]  # YYYYMMDD
        by_date[date_str].append(d)

logger.info(f"\n--- Dumps per day ---")
for date in sorted(by_date.keys()):
    count = len(by_date[date])
    sizes = sum(os.path.getsize(d) for d in by_date[date])
    logger.info(f"  {date}: {count:>4} dumps, {sizes/1024:>8.1f} KB total")
logger.info(f"\n--- Last 24h breakdown ---")
import re
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(hours=24)
recent = [d for d in dumps if datetime.strptime(os.path.basename(d).split('_')[2] + '_' + os.path.basename(d).split('_')[3][:6], '%Y%m%d_%H%M%S') > cutoff]

logger.info(f"Dumps in last 24h: {len(recent)}")
logger.info(f"\n--- Context size from recent request dumps ---")
for d in recent[-20:]:
    try:
        with open(d, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        if isinstance(data, dict):
            msgs = data.get('messages', [])
            # Estimate tokens from content length
            total_chars = sum(len(str(m.get('content', ''))) for m in msgs)
            logger.info(f"  {os.path.basename(d)[:50]:50s} msgs={len(msgs):>4}  chars={total_chars:>7,}  est_tok={int(total_chars*0.3):>7,}")
    except Exception as e:
        logger.debug(f"操作失败: {e}")
logger.info("\n\n=== SUMMARY ===")
logger.info(f"Total dumps: {len(dumps)}")
logger.info(f"Dumps last 24h: {len(recent)}")
import sqlite3
db = r"C:/Users/user/AppData/Local/hermes/profiles/aris/state.db"
con = sqlite3.connect(db)
cur = con.cursor()

# Sessions per day
cur.execute("SELECT substr(id,1,8) as day, COUNT(*) as cnt FROM sessions GROUP BY day ORDER BY day")
rows = cur.fetchall()
logger.info(f"\nSessions by day:")
for day, cnt in rows:
    cur2 = con.cursor()
    cur2.execute("SELECT COUNT(*) FROM messages WHERE session_id LIKE ?", (f"{day}%",))
    mc = cur2.fetchone()[0]
    logger.info(f"  {day}: {cnt:>3} sessions, {mc:>6,} messages")
con.close()
