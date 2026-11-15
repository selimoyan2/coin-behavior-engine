import subprocess
import re

# Let's inspect test collection per module
p = subprocess.run([r".venv\Scripts\pytest.exe", "--collect-only", "-q"], capture_output=True, text=True)
lines = p.stdout.splitlines()

module_counts = {}
current_module = None
count = 0

for line in lines:
    m = re.match(r"\s*<Module (.*?)>", line)
    if m:
        if current_module:
            module_counts[current_module] = count
        current_module = m.group(1)
        count = 0
    elif "<Function " in line:
        count += 1

if current_module:
    module_counts[current_module] = count

total = sum(module_counts.values())
print(f"Total modules: {len(module_counts)}, Total collected tests: {total}")
for mod, cnt in sorted(module_counts.items()):
    print(f"  {mod}: {cnt}")
