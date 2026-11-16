import subprocess
import json

def run_ssh(cmd_str):
    ssh_cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238',
        cmd_str
    ]
    p = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return p

backup_script = """
set -e
echo "=== 1. CURRENT PRODUCTION CONTAINER INSPECTION ==="
docker inspect d20a430d9704 --format 'ID: {{.Id}} | Name: {{.Name}} | Image: {{.Image}} | State: {{.State.Status}} | StartedAt: {{.State.StartedAt}} | Restarts: {{.RestartCount}}'
docker inspect d20a430d9704 --format 'Mounts: {{json .Mounts}}'

echo "\n=== 2. CREATING PREDEPLOYMENT BACKUP DIR ==="
BACKUP_DIR="/root/cbe_backups/sprint36_predeploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "\n=== 3. BACKING UP PRODUCTION CONTAINER DATA ==="
# Find prospective volumes or container files
docker cp d20a430d9704:/app/data/prospective "$BACKUP_DIR/prospective" || echo "No /app/data/prospective in container"
docker cp d20a430d9704:/app/build_metadata.json "$BACKUP_DIR/build_metadata_prod.json" || true

# Backup docker image tag for instant rollback
docker tag 6t63aehpaw0cw1bbt4zcm09g:f342e40546eca538db54d8d32861f6946617dd0b cbe-production-rollback-sprint35:f342e40

# Calculate SHA256 of backed up files
cd "$BACKUP_DIR"
find . -type f -exec sha256sum {} + > sha256_checksums.txt

echo "\n=== 4. BACKUP SUMMARY ==="
echo "Backup Location: $BACKUP_DIR"
cat sha256_checksums.txt | head -n 30
echo "Total files backed up: $(wc -l < sha256_checksums.txt)"
"""

res = run_ssh(backup_script)
print(res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)
