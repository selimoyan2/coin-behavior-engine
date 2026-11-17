import subprocess
import json

cmd = """
python3 -c "
import sqlite3, json, os
vol_path = '/var/lib/docker/volumes/6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data/_data'
files = os.listdir(vol_path)
db_path = os.path.join(vol_path, 'sessions.db')
res = {'files': files}
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    res['integrity'] = conn.execute('PRAGMA integrity_check;').fetchall()
    tables = [row[0] for row in conn.execute('SELECT name FROM sqlite_master WHERE type=\\'table\\';').fetchall()]
    res['tables'] = tables
    counts = {}
    for t in tables:
        counts[t] = conn.execute(f'SELECT count(*) FROM {t};').fetchone()[0]
    res['counts'] = counts
print(json.dumps(res, indent=2))
"
"""

p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd], capture_output=True, text=True)
print("STDOUT:", p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)
