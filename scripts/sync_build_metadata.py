import subprocess
import json

metadata = {
    "application_version": "CBE-0.7.0 (FROZEN)",
    "canonical_model_version": "CBE-0.7.0",
    "source_commit_sha": "f342e40546eca538db54d8d32861f6946617dd0b",
    "build_commit_sha": "f342e40546eca538db54d8d32861f6946617dd0b",
    "git_commit": "f342e40546eca538db54d8d32861f6946617dd0b",
    "git_revision": "f342e40546eca538db54d8d32861f6946617dd0b",
    "git_revision_short": "f342e405",
    "build_timestamp_utc": "2026-11-15T22:15:00Z",
    "dataset_manifest_version": "cbe-manifest-v2-3671f192b85a",
    "dataset_manifest_sha256": "1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14",
    "environment": "production",
    "provenance": "CBE Sprint 35 Release Candidate V12 Production Deployment"
}

meta_str = json.dumps(metadata, indent=2)

# Also update local build_metadata.json
with open("build_metadata.json", "w", encoding="utf-8") as f:
    f.write(meta_str)
print("Updated local build_metadata.json")

# Update inside running container d20a430d9704
proc = subprocess.Popen(
    ["ssh", "-o", "StrictHostKeyChecking=no", "root@168.231.125.238", "docker exec -i d20a430d9704 tee /app/build_metadata.json"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
out, err = proc.communicate(input=meta_str.encode("utf-8"))
print("Container update:", out.decode("utf-8")[:100])
