import subprocess

script = r'''
import subprocess

out = subprocess.check_output([
    'docker', 'exec', 'coolify-db', 'psql', '-U', 'coolify', '-d', 'coolify', '-t', '-A', '-c',
    "SELECT id, deployment_uuid, status, commit, created_at, updated_at FROM application_deployment_queues WHERE deployment_uuid = '053956b9-1af9-4867-84ac-ce6e4a0619ac';"
]).decode('utf-8')
print('Deployment Status:\n', out.strip())
'''

proc = subprocess.Popen(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', 'python3'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = proc.communicate(input=script.encode('utf-8'))
print(out.decode('utf-8'))
