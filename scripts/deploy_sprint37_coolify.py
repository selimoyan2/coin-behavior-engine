import subprocess
import json
import time
import sys

COMMIT_SHA = "057d0af32b9de15a8d54ed9bcf0605727960ea6c"
REMOTE_HOST = "root@168.231.125.238"

trigger_script = f"""
docker exec coolify php -r "
require '/var/www/html/vendor/autoload.php';
\\$app = require_once '/var/www/html/bootstrap/app.php';
\\$kernel = \\$app->make(Illuminate\\\\Contracts\\\\Console\\\\Kernel::class);
\\$kernel->bootstrap();

\\$application = App\\\\Models\\\\Application::where('uuid', '6t63aehpaw0cw1bbt4zcm09g')->first();
\\$deployment_uuid = (string) Illuminate\\\\Support\\\\Str::uuid();
echo 'Triggering deployment ' . \\$deployment_uuid . ' for ' . \\$application->name . PHP_EOL;
queue_application_deployment(
    application: \\$application,
    deployment_uuid: \\$deployment_uuid,
    commit: '{COMMIT_SHA}',
    force_rebuild: true
);
echo 'QUEUED_UUID:' . \\$deployment_uuid . PHP_EOL;
"
"""

print(f"Triggering Coolify deployment for commit {COMMIT_SHA}...")
p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', REMOTE_HOST, trigger_script], capture_output=True, text=True)
print("TRIGGER STDOUT:\n", p.stdout)
if p.stderr:
    print("TRIGGER STDERR:\n", p.stderr)

deployment_uuid = None
for line in p.stdout.splitlines():
    if line.startswith("QUEUED_UUID:"):
        deployment_uuid = line.split(":", 1)[1].strip()

if not deployment_uuid:
    print("ERROR: Failed to extract queued deployment UUID!")
    sys.exit(1)

print(f"Monitoring Coolify deployment {deployment_uuid}...")
t0 = time.time()
for attempt in range(120):
    cmd = f"""
    docker exec coolify-db psql -U coolify -d coolify -t -A -c "
        SELECT status, updated_at FROM application_deployment_queues WHERE deployment_uuid = '{deployment_uuid}';
    "
    """
    p_status = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', REMOTE_HOST, cmd], capture_output=True, text=True)
    status_raw = p_status.stdout.strip()
    elapsed = int(time.time() - t0)
    print(f"[{attempt+1}/120 - {elapsed}s] Status: {status_raw}")
    
    if "finished" in status_raw.lower() or "success" in status_raw.lower():
        print(f"Deployment finished successfully in {elapsed}s!")
        break
    elif "failed" in status_raw.lower() or "error" in status_raw.lower() or "killed" in status_raw.lower():
        print(f"Deployment failed after {elapsed}s! Checking logs...")
        cmd_logs = f"docker exec coolify-db psql -U coolify -d coolify -t -A -c \"SELECT logs FROM application_deployment_queues WHERE deployment_uuid = '{deployment_uuid}';\""
        p_logs = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', REMOTE_HOST, cmd_logs], capture_output=True, text=True)
        print("LOGS:\n", p_logs.stdout[-3000:])
        sys.exit(1)
    time.sleep(5)

# Inspect active production container
cmd_check = """
docker ps --filter name=6t63aehpaw0cw1bbt4zcm09g --format 'ID: {{.ID}} | Image: {{.Image}} | Status: {{.Status}} | Ports: {{.Ports}}'
"""
p_check = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', REMOTE_HOST, cmd_check], capture_output=True, text=True)
print("\nActive Production Container:\n", p_check.stdout)

evidence = {
    "deployment_uuid": deployment_uuid,
    "commit_sha": COMMIT_SHA,
    "elapsed_seconds": int(time.time() - t0),
    "active_containers": p_check.stdout.strip().splitlines()
}

with open("scripts/latest_coolify_deployment.json", "w", encoding="utf-8") as f:
    json.dump(evidence, f, indent=2)
