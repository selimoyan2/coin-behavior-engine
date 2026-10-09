#!/usr/bin/env bash
# Read-Only VPS Resource Capacity Audit Script for CBE-0.8.0 Shadow Assessment
# SAFE / READ-ONLY: Does not modify system settings, packages, or services.

set -euo pipefail

echo "=========================================================="
echo "CBE-0.8.0 SHADOW COLLECTOR — READ-ONLY VPS AUDIT"
echo "Host: $(hostname) | Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================================="

echo -e "\n[1. MEMORY SUMMARY]"
free -m

echo -e "\n[2. MEMORY DETAILED INFO]"
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree"

echo -e "\n[3. CPU CORES & LOAD]"
echo "CPU Cores: $(nproc)"
uptime

echo -e "\n[4. DISK USAGE]"
df -h /

echo -e "\n[5. DOCKER / COOLIFY CONTAINER METRICS]"
if command -v docker >/dev/null 2>&1; then
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}"
else
    echo "Docker CLI not found or not in PATH."
fi

echo -e "\n[6. OOM-KILLER RECENT INCIDENTS]"
if command -v dmesg >/dev/null 2>&1; then
    dmesg -T | grep -i -E "oom[-_]killer|out of memory" | tail -n 10 || echo "No recent OOM events found."
else
    echo "dmesg not accessible."
fi

echo -e "\n=========================================================="
echo "AUDIT COMPLETE — Copy output into vps_capacity_report.txt"
echo "=========================================================="
