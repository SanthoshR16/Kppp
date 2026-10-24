import os
import sqlite3

def audit():
    db_path = os.path.join("data", "db", "kppp.sqlite")
    print(f"Database Path: {db_path}")
    if os.path.exists(db_path):
        size = os.path.getsize(db_path)
        print(f"Database file size: {size:,} bytes")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cur.fetchall()
        print(f"\nTable Counts ({len(tables)} tables):")
        for (table_name,) in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM \"{table_name}\";")
                count = cur.fetchone()[0]
                print(f"  - {table_name}: {count} rows")
            except Exception as e:
                print(f"  - {table_name}: Error ({e})")
        conn.close()
    else:
        print("Database does NOT exist.")

    raw_path = os.path.join("data", "raw")
    print(f"\nRaw Data Path: {raw_path}")
    if os.path.exists(raw_path):
        folder_count = 0
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(raw_path):
            folder_count += len(dirs)
            file_count += len(files)
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_size += os.path.getsize(fp)
                except Exception:
                    pass
        print(f"Folders count: {folder_count}")
        print(f"Files count: {file_count}")
        print(f"Total size: {total_size:,} bytes")
    else:
        print("Raw directory does NOT exist.")

if __name__ == "__main__":
    audit()
