# CBE-0.8.0 DEPLOYMENT PREPARATION & SYSTEMD SPECIFICATION
*(DOCUMENTATION AND TEMPLATES ONLY — EXECUTION PROHIBITED)*

**TARGET CANDIDATE:** CBE-0.8.0 Shadow Collector  
**HOST ENVIRONMENT:** Linux VPS / Docker / Systemd  
**DEPLOYMENT STATUS:** NOT DEPLOYED / PREPARATION ONLY  

---

## 1. STANDALONE SYSTEMD SERVICE TEMPLATE

```ini
[Unit]
Description=Coin Behavior Engine CBE-0.8.0 Shadow Collector
After=network.target

[Service]
Type=simple
User=cbe
WorkingDirectory=/opt/coin-behavior-engine
Environment="PYTHONPATH=/opt/coin-behavior-engine/src"
Environment="CBE_SHADOW_NETWORK_ENABLED=true"
Environment="CBE_SHADOW_LIVE_ENABLED=true"
ExecStart=/opt/coin-behavior-engine/.venv/bin/python -m coin_behavior_engine.shadow_v080.cli --mode=live
Restart=on-failure
RestartSec=10s
LimitNOFILE=65535
MemoryMax=150M
CPUQuota=20%

[Install]
WantedBy=multi-user.target
```

---

## 2. PRODUCTION ISOLATION GUARANTEES

- The service runs as an independent daemon.
- It does **NOT** share memory, threads, or sockets with CBE-0.7.0.
- It stores data strictly in `/opt/coin-behavior-engine/data/shadow_v080/`.
- It executes **zero trades** and accesses **no private exchange API keys**.
