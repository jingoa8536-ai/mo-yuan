"""Deep dive into token consumption"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, json, os, re

db = r"C:/Users/user/AppData/Local/hermes/profiles/aris/state.db"
con = sqlite3.connect(db)
cur = con.cursor()

# Get all sessions with their message count and estimated token usage
cur.execute("""
    SELECT s.id, s.title, COUNT(m.id) as msg_count
    FROM sessions s
    LEFT JOIN messages m ON m.session_id = s.id
    GROUP BY s.id
    ORDER BY msg_count DESC
""")
sessions = cur.fetchall()
logger.info(f"Total sessions: {len(sessions)}")
logger.info(f"Total messages: {sum(s[2] for s in sessions):,}")
logger.info("\n--- Top 5 sessions by message count ---")
for s in sessions[:5]:
    sid = s[0]
    title = str(s[1])[:60] if s[1] else "(no title)"
    logger.info(f"  {sid[:25]:25s} msgs={s[2]:>5,}  {title}")
logger.info("\n--- Last 5 sessions -> avg message size ---")
cur.execute("SELECT session_id, COUNT(*), AVG(LENGTH(content)) FROM messages GROUP BY session_id ORDER BY session_id DESC LIMIT 5")
for sid, cnt, avg_len in cur.fetchall():
    logger.info(f"  {sid[:25]:25s} msgs={cnt:>4,} avg_len={avg_len:.0f} chars")
logger.error("\n--- Tool error patterns in last 500 messages ---")
cur.execute("""
    SELECT content FROM messages 
    WHERE session_id IN (SELECT id FROM sessions ORDER BY id DESC LIMIT 5)
    ORDER BY id DESC LIMIT 500
""")
msgs = cur.fetchall()
err_count = sum(1 for m in msgs if 'error' in str(m[0]).lower() or 'traceback' in str(m[0]).lower())
tool_count = sum(1 for m in msgs if 'tool' in str(m[0]).lower() or 'WARNING' in str(m[0]) or 'ERROR' in str(m[0]))
retry_count = sum(1 for m in msgs if 'retry' in str(m[0]).lower() or 'attempt' in str(m[0]).lower())
logger.error(f"  Error/Traceback messages: {err_count}")
logger.error(f"  Tool/Warning/ERROR msgs: {tool_count}")
logger.info(f"  Retry/Attempt msgs: {retry_count}")
logger.info("\n--- Cron-related messages ---")
cur.execute("SELECT COUNT(*) FROM messages WHERE content LIKE '%cron%' OR content LIKE '%CRON%'")
cron_msg = cur.fetchone()[0]
logger.info(f"  Messages mentioning cron: {cron_msg}")
cur.execute("SELECT id FROM sessions WHERE id LIKE '20260621%'")
today = len(cur.fetchall())
cur.execute("SELECT COUNT(*) FROM messages WHERE session_id LIKE '20260621%'")
today_msgs = cur.fetchone()[0]
logger.info(f"\n--- Today (June 21) ---")
logger.info(f"  Sessions: {today}")
logger.info(f"  Messages: {today_msgs:,}")
cur.execute("SELECT id, title FROM sessions WHERE title LIKE '%RSI%' OR title LIKE '%evolution%' OR title LIKE '%cron%' ORDER BY id DESC LIMIT 10")
rows = cur.fetchall()
if rows:
    logger.info(f"\n--- Cron/RSI sessions ---")
    for r in rows:
        cur.execute("SELECT COUNT(*) FROM messages WHERE session_id=?", (r[0],))
        mc = cur.fetchone()[0]
        logger.info(f"  {r[0][:25]:25s} msgs={mc:>4,}  title={str(r[1])[:50]}")
con.close()
