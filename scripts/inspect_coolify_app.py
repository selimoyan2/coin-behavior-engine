import subprocess

cmd = 'docker exec coolify-db psql -U coolify -d coolify -t -A -c "SELECT id, name, git_repository, git_branch, build_pack, fqdn, ports_exposes FROM applications WHERE uuid = \'6t63aehpaw0cw1bbt4zcm09g\';"'
p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd], capture_output=True, text=True)
print("APP INFO:", p.stdout)
if p.stderr:
    print("ERR:", p.stderr)
