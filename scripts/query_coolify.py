import subprocess

def run_query(q):
    cmd = ['ssh', 'root@168.231.125.238', f'docker exec -i coolify-db psql -U coolify -d coolify -c "{q}"']
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(f"=== {q} ===")
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

run_query("SELECT id, status, updated_at FROM application_deployment_queues WHERE id = 574;")
