import subprocess

script = r'''
import subprocess

p = subprocess.run(['docker', 'exec', 'coolify', 'php', '-r', """
require '/var/www/html/vendor/autoload.php';
$app = require_once '/var/www/html/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

$application = App\Models\Application::where('uuid', '6t63aehpaw0cw1bbt4zcm09g')->first();
$deployment_uuid = (string) Illuminate\Support\Str::uuid();
echo "Triggering deployment $deployment_uuid for " . $application->name . "\n";
queue_application_deployment(
    application: $application,
    deployment_uuid: $deployment_uuid,
    commit: 'f342e40546eca538db54d8d32861f6946617dd0b',
    force_rebuild: true
);
echo "SUCCESS: Queued deployment $deployment_uuid\n";
"""], capture_output=True, text=True)

print('STDOUT:', p.stdout)
print('STDERR:', p.stderr)
print('CODE:', p.returncode)
'''

proc = subprocess.Popen(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', 'python3'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = proc.communicate(input=script.encode('utf-8'))
print(out.decode('utf-8'))
