import json
import subprocess

ssh_cmd = [
    "ssh", "root@168.231.125.238",
    "python3 - << 'EOF'\n"
    "import urllib.request, json\n"
    "url = 'http://127.0.0.1:18080/api/v1/product/pattern-discovery/compare-v2?window_a_start=2022-06-01T00:00:00Z&window_a_end=2022-06-15T00:00:00Z&window_b_start=2024-07-27T01:00:00Z&window_b_end=2024-08-10T01:00:00Z'\n"
    "req = urllib.request.Request(url)\n"
    "res = urllib.request.urlopen(req)\n"
    "obj = json.loads(res.read())\n"
    "summary = {\n"
    "    'comparison_id': obj.get('comparison_id'),\n"
    "    'reference_start_utc': obj.get('reference_start_utc'),\n"
    "    'candidate_start_utc': obj.get('candidate_start_utc'),\n"
    "    'similarity_analysis_keys': list(obj.get('similarity_analysis', {}).keys()),\n"
    "    'status': obj.get('status')\n"
    "}\n"
    "print(json.dumps(summary, indent=2))\n"
    "EOF"
]

res = subprocess.run(ssh_cmd, capture_output=True, text=True)
print("STDOUT:")
print(res.stdout)
