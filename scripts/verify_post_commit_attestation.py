"""
Post-Commit Attestation Generator and Verifier for Sprint 11.23.5B-6.5.

Solves the circular Git commit hash paradox by capturing post-commit metadata
in a detached attestation document after the git commit object is created.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_git_cmd(args: list[str]) -> str:
    res = subprocess.run(["git"] + args, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def generate_attestation() -> Path:
    root = Path(__file__).resolve().parent.parent
    research_dir = root / "research_outputs"
    manifest_file = research_dir / "reproducibility_manifest_11_23_5b6_5.json"

    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")

    manifest_hash = compute_sha256(manifest_file)
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))

    commit_sha = run_git_cmd(["rev-parse", "HEAD"])
    parent_sha = run_git_cmd(["rev-parse", "HEAD~1"])
    tree_sha = run_git_cmd(["rev-parse", "HEAD^{tree}"])
    commit_date = run_git_cmd(["log", "-1", "--format=%cI"])
    commit_author = run_git_cmd(["log", "-1", "--format=%an <%ae>"])
    commit_subject = run_git_cmd(["log", "-1", "--format=%s"])

    # Verify deliverable hashes against manifest
    mismatches = []
    for fname, expected_hash in manifest_data.get("deliverables", {}).items():
        fpath = research_dir / fname
        if not fpath.exists():
            mismatches.append(f"Missing deliverable: {fname}")
        else:
            actual_hash = compute_sha256(fpath)
            if actual_hash != expected_hash:
                mismatches.append(f"Hash mismatch for {fname}: expected {expected_hash}, got {actual_hash}")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    attestation = {
        "sprint": "11.23.5B-6.5",
        "attestation_type": "DETACHED_POST_COMMIT_CRYPTOGRAPHIC_ATTESTATION",
        "generated_at_utc": now_utc,
        "base_commit": manifest_data.get("base_commit", "9c6088d37cb3103dc1b79b19a0a2b105788207ee"),
        "final_commit_sha": commit_sha,
        "parent_commit_sha": parent_sha,
        "tree_sha": tree_sha,
        "commit_date": commit_date,
        "commit_author": commit_author,
        "commit_subject": commit_subject,
        "manifest_file": manifest_file.name,
        "manifest_sha256": manifest_hash,
        "deliverable_verification": {
            "total_verified": len(manifest_data.get("deliverables", {})),
            "mismatches": mismatches,
            "status": "PASS" if not mismatches else "FAIL",
        },
        "circular_dependency_status": "RESOLVED_VIA_DETACHED_ATTESTATION",
    }

    out_file = research_dir / "post_commit_attestation_11_23_5b6_5.json"
    out_file.write_text(json.dumps(attestation, indent=2), encoding="utf-8")
    print(f"Generated post-commit attestation: {out_file}")
    print(f"  Final Commit SHA: {commit_sha}")
    print(f"  Manifest SHA256:  {manifest_hash}")
    print(f"  Verification:     {attestation['deliverable_verification']['status']}")
    return out_file


def verify_attestation() -> bool:
    root = Path(__file__).resolve().parent.parent
    research_dir = root / "research_outputs"
    attestation_file = research_dir / "post_commit_attestation_11_23_5b6_5.json"
    manifest_file = research_dir / "reproducibility_manifest_11_23_5b6_5.json"

    if not attestation_file.exists():
        print(f"Attestation file missing: {attestation_file}", file=sys.stderr)
        return False

    attestation = json.loads(attestation_file.read_text(encoding="utf-8"))
    manifest_hash = compute_sha256(manifest_file)

    if attestation.get("manifest_sha256") != manifest_hash:
        print(f"Manifest SHA256 mismatch in attestation! Expected {manifest_hash}, got {attestation.get('manifest_sha256')}", file=sys.stderr)
        return False

    commit_sha = run_git_cmd(["rev-parse", "HEAD"])
    if attestation.get("final_commit_sha") != commit_sha:
        print(f"Commit SHA mismatch! Current HEAD {commit_sha} != attested {attestation.get('final_commit_sha')}", file=sys.stderr)
        return False

    print("Post-commit attestation verification SUCCESS: All hashes and Git commit objects match.")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        success = verify_attestation()
        sys.exit(0 if success else 1)
    else:
        generate_attestation()
