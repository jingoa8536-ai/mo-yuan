"""Check the giant session"""

import logging
logger = logging.getLogger(__name__)

import sqlite3, json

db = r"C:/Users/user/AppData/Local/hermes/profiles/aris/state.db"
con = sqlite3.connect(db)
cur = con.cursor()

# The biggest session
big_sid = "20260614_113712_3ab987"

# Get all roles
cur.execute("SELECT role, COUNT(*) FROM messages WHERE session_id=? GROUP BY role", (big_sid,))
logger.info(f"Session {big_sid} - message breakdown:")
for role, cnt in cur.fetchall():
    logger.info(f"  {role}: {cnt}")
cur.execute("SELECT role, substr(content,1,120) FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 20", (big_sid,))
logger.info(f"\nLast 20 messages:")
for role, content in cur.fetchall():
    logger.info(f"  [{role:>10}] {content}")
logger.info(f"\n--- Today's sessions with 100+ messages ---")
cur.execute("""
    SELECT s.id, s.title, COUNT(m.id)
    FROM sessions s
    JOIN messages m ON m.session_id = s.id
    WHERE s.id LIKE '20260621%'
    GROUP BY s.id
    HAVING COUNT(m.id) >= 100
    ORDER BY COUNT(m.id) DESC
""")
for sid, title, cnt in cur.fetchall():
    logger.info(f"  {sid[:25]:25s} msgs={cnt:>4,}  {str(title)[:60]}")
con.close()
