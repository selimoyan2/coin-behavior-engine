import subprocess
import time
import sys

DEPLOYMENT_UUID = "37396965-40cc-4978-861b-731140dc7cc6"

def check_status():
    cmd = f"""
    docker exec coolify-db psql -U coolify -d coolify -t -A -c "
        SELECT status, updated_at FROM application_deployment_queues WHERE deployment_uuid = '{DEPLOYMENT_UUID}';
    "
    """
    p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd], capture_output=True, text=True)
    return p.stdout.strip()

print(f"Monitoring Coolify deployment {DEPLOYMENT_UUID}...")
for attempt in range(60):
    status_raw = check_status()
    print(f"[{attempt+1}/60] Status: {status_raw}")
    if "finished" in status_raw.lower() or "success" in status_raw.lower():
        print("Deployment finished successfully!")
        break
    elif "failed" in status_raw.lower() or "error" in status_raw.lower():
        print("Deployment failed! Checking logs...")
        cmd_logs = f"docker exec coolify-db psql -U coolify -d coolify -t -A -c \"SELECT logs FROM application_deployment_queues WHERE deployment_uuid = '{DEPLOYMENT_UUID}';\""
        p_logs = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd_logs], capture_output=True, text=True)
        print("LOGS:\n", p_logs.stdout[-2000:])
        sys.exit(1)
    time.sleep(10)

# Check active production container
cmd_check = """
docker ps --filter name=6t63aehpaw0cw1bbt4zcm09g --format 'ID: {{.ID}} | Image: {{.Image}} | Status: {{.Status}} | Ports: {{.Ports}}'
"""
p_check = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd_check], capture_output=True, text=True)
print("\nActive Production Container:\n", p_check.stdout)
