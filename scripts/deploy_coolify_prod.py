import subprocess
import json
import time

COMMIT_SHA = "313fc5ca242e497f1e221002c798fc5910bd6284"

trigger_script = f"""
docker exec coolify php -r "
require '/var/www/html/vendor/autoload.php';
\$app = require_once '/var/www/html/bootstrap/app.php';
\$kernel = \$app->make(Illuminate\\\\Contracts\\\\Console\\\\Kernel::class);
\$kernel->bootstrap();

\$application = App\\\\Models\\\\Application::where('uuid', '6t63aehpaw0cw1bbt4zcm09g')->first();
\$deployment_uuid = (string) Illuminate\\\\Support\\\\Str::uuid();
echo 'Triggering deployment ' . \$deployment_uuid . ' for ' . \$application->name . PHP_EOL;
queue_application_deployment(
    application: \$application,
    deployment_uuid: \$deployment_uuid,
    commit: '{COMMIT_SHA}',
    force_rebuild: true
);
echo 'QUEUED_UUID:' . \$deployment_uuid . PHP_EOL;
"
"""

p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', trigger_script], capture_output=True, text=True)
print("TRIGGER OUT:\n", p.stdout)
if p.stderr:
    print("TRIGGER ERR:\n", p.stderr)
