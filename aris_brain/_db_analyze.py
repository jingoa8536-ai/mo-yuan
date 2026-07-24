"""Analyze state.db for token consumption"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, os

db = r"C:/Users/user/AppData/Local/hermes/profiles/aris/state.db"
sz = os.path.getsize(db)
logger.info(f"state.db: {sz:,} bytes ({sz/1024/1024:.1f} MB)")
con = sqlite3.connect(db)
cur = con.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
for (tname,) in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{tname}"')
        cnt = cur.fetchone()[0]
        logger.info(f"  {tname}: {cnt:,} rows")
    except:
        logger.error(f"  {tname}: (error)")
try:
    cur.execute("SELECT id, title, created FROM sessions ORDER BY created DESC LIMIT 10")
    rows = cur.fetchall()
    logger.info(f"\n--- Last 10 sessions ---")
    for r in rows:
        logger.info(f"  ID={r[0]}, title='{str(r[1])[:60]}', created={r[2]}")
except Exception as e:
    logger.info(f"No sessions table: {e}")
try:
    cur.execute("SELECT session_id, COUNT(*) as cnt FROM messages GROUP BY session_id ORDER BY cnt DESC LIMIT 10")
    rows = cur.fetchall()
    logger.info(f"\n--- Top 10 sessions by message count ---")
    for r in rows:
        logger.info(f"  session={r[0][:30]}... messages={r[1]:,}")
    cur.execute("SELECT COUNT(*) FROM messages")
    total = cur.fetchone()[0]
    logger.info(f"\nTotal messages in DB: {total:,}")
except Exception as e:
    logger.info(f"No messages table: {e}")
con.close()
