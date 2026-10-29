import subprocess
from pathlib import Path

files_to_sync = [
    ("src/coin_behavior_engine/product/unified_research_workspace.py", "/app/src/coin_behavior_engine/product/unified_research_workspace.py"),
    ("src/coin_behavior_engine/product/dashboard_api.py", "/app/src/coin_behavior_engine/product/dashboard_api.py"),
    ("src/coin_behavior_engine/product/dashboard_ui.py", "/app/src/coin_behavior_engine/product/dashboard_ui.py"),
]

for local_path, remote_path in files_to_sync:
    print(f"Syncing {local_path} -> {remote_path} on staging container 86881ba01b3e...")
    # scp to host /tmp, then docker cp into container
    scp_cmd = ["scp", local_path, f"root@168.231.125.238:/tmp/{Path(local_path).name}"]
    subprocess.run(scp_cmd, check=True)
    cp_cmd = ["ssh", "root@168.231.125.238", f"docker cp /tmp/{Path(local_path).name} 86881ba01b3e:{remote_path}"]
    subprocess.run(cp_cmd, check=True)

# Restart staging container to ensure fresh module imports
restart_cmd = ["ssh", "root@168.231.125.238", "docker restart 86881ba01b3e"]
subprocess.run(restart_cmd, check=True)

print("Staging container successfully updated and restarted!")
