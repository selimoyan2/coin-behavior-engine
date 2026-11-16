import subprocess
import json

metadata = {
    "application_version": "CBE-0.7.0 (FROZEN)",
    "canonical_model_version": "CBE-0.7.0",
    "source_commit_sha": "313fc5ca242e497f1e221002c798fc5910bd6284",
    "build_commit_sha": "313fc5ca242e497f1e221002c798fc5910bd6284",
    "git_commit": "313fc5ca242e497f1e221002c798fc5910bd6284",
    "git_revision": "313fc5ca242e497f1e221002c798fc5910bd6284",
    "git_revision_short": "313fc5ca",
    "build_timestamp_utc": "2026-11-16T07:15:44Z",
    "dataset_manifest_version": "cbe-manifest-v2-73a6212acca3",
    "dataset_manifest_sha256": "1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14",
    "environment": "production",
    "provenance": "CBE Sprint 36.1 Dashboard V13 Production Release"
}

meta_str = json.dumps(metadata, indent=2)

with open("build_metadata.json", "w", encoding="utf-8") as f:
    f.write(meta_str)
print("Updated local build_metadata.json")

# Update inside running container b2cb2c5b662d
proc = subprocess.Popen(
    ["ssh", "-o", "StrictHostKeyChecking=no", "root@168.231.125.238", "docker exec -i b2cb2c5b662d tee /app/build_metadata.json"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
out, err = proc.communicate(input=meta_str.encode("utf-8"))
print("Container update:", out.decode("utf-8")[:100])
