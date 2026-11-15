import subprocess

script = """
echo '=== INSPECT CONTAINER 0688330c7292 ==='
docker inspect 0688330c7292 --format '{{json .Config.Labels}}'
echo '=== INSPECT ENV ==='
docker inspect 0688330c7292 --format '{{json .Config.Env}}'
echo '=== INSPECT MOUNTS ==='
docker inspect 0688330c7292 --format '{{json .Mounts}}'
"""

p = subprocess.run(
    ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "root@168.231.125.238", "bash -s"],
    input=script.encode("utf-8"),
    capture_output=True
)
print(p.stdout.decode("utf-8", errors="replace"))
print(p.stderr.decode("utf-8", errors="replace"))
