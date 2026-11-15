import subprocess
import time

script = r'''
import subprocess, time

for i in range(60):
    out = subprocess.check_output([
        'docker', 'exec', 'coolify-db', 'psql', '-U', 'coolify', '-d', 'coolify', '-t', '-A', '-c',
        "SELECT id, status, commit, updated_at FROM application_deployment_queues WHERE deployment_uuid = 'f3d39384-d62e-4890-ba2f-9979ce02f76c';"
    ]).decode('utf-8').strip()
    print(f"[{i*5}s] Status: {out}")
    if 'finished' in out or 'failed' in out or 'cancelled' in out:
        break
    time.sleep(5)
'''

proc = subprocess.Popen(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', 'python3'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = proc.communicate(input=script.encode('utf-8'))
print(out.decode('utf-8'))
