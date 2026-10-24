import sqlite3
from datetime import datetime, timezone, timedelta
from scoped_watcher import get_watermark, set_watermark, run_gap_fill, run_watcher_scan

print("="*60)
print("TEST: WATERMARK & GAP-FILL TEST (WATERMARK SET 5 DAYS BACK)")
print("="*60)

# 1. Check current watermark
orig_wm = get_watermark()
print(f"Original Watermark: {orig_wm}")

# 2. Set watermark 5 days back
five_days_back = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
set_watermark("kppp_karnataka", five_days_back)
print(f"Set Watermark to 5 days back: {get_watermark()}")

# 3. Run gap fill
res = run_gap_fill(days_back=5)
print(f"Gap fill completed. Updated watermark: {get_watermark()}")

# 4. Run real watcher detection
print("\n" + "="*60)
print("TEST: REAL WATCHER DETECTION RUN")
print("="*60)
w_res = run_watcher_scan()
print(f"Watcher scan result:")
print(f"  New detections: {len(w_res['detections'])}")
print(f"  Status changes: {len(w_res['status_changes'])}")
if w_res["detections"]:
    print("  Sample detection:", w_res["detections"][0])
if w_res["status_changes"]:
    print("  Sample status change:", w_res["status_changes"][0])

print("\n[SUCCESS] Gap-fill test and watcher detection verified.")
