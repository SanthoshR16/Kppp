import sqlite3
conn = sqlite3.connect("data/db/kppp.sqlite")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)
for t in tables:
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"  {t}: {cols}")
conn.close()
