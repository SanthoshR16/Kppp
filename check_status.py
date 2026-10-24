import json, os, sqlite3

cp = json.load(open("data/checkpoint.json"))
print(f"Chunks completed: {len(cp['completed_chunks'])}")
print(f"Last updated: {cp['last_updated']}")

# Current DB counts
conn = sqlite3.connect("data/db/kppp.sqlite")
cur = conn.cursor()
for t in ["tenders", "bids", "tender_files", "tender_items", "departments", "debarred_suppliers", "flags"]:
    cur.execute(f"SELECT count(*) FROM {t}")
    print(f"  {t}: {cur.fetchone()[0]} rows")
    
db_size = os.path.getsize("data/db/kppp.sqlite")
print(f"DB size: {db_size:,} bytes ({db_size/(1024*1024):.2f} MB)")

# Raw folder count
raw_count = sum(1 for d in os.scandir("data/raw") if d.is_dir())
print(f"Raw tender folders: {raw_count}")

# Heartbeat
if os.path.exists("data/heartbeat.json"):
    hb = json.load(open("data/heartbeat.json"))
    print(f"Heartbeat: {hb}")
else:
    print("No heartbeat file yet")
conn.close()
