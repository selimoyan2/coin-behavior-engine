# ROLLBACK & EMERGENCY STOP PROCEDURE

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**EMERGENCY LATENCY TARGET:** < 5 Seconds  

---

## 1. IMMEDIATE KILL COMMAND (INSTANT MITIGATION)

If the shadow container causes any memory, CPU, or network anomaly on host `srv1114257`:

```bash
docker stop -t 2 cbe_080_prospective_shadow
```

This immediately halts all container execution within 2 seconds.

---

## 2. COMPLETE SERVICE DESTRUCTION & ROLLBACK

To completely remove the shadow collector without touching production:

```bash
# 1. Stop and remove container
docker rm -f cbe_080_prospective_shadow

# 2. Archive data volume (preserving scientific evidence)
docker run --rm -v cbe_080_shadow_data:/data -v /opt/backups:/backup alpine \
  tar -czf /backup/cbe_080_shadow_emergency_archive_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# 3. Remove volume (optional, only if disk space is critical)
# docker volume rm cbe_080_shadow_data
```

---

## 3. ZERO PRODUCTION IMPACT VERIFICATION

Following emergency stop:
1. Verify production CBE-0.7.0 container is healthy:
   `docker ps | grep cbe-0.7.0`
2. Verify production database integrity.
