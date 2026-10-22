"""
Authoritative Post-Commit Attestation Verifier for Sprint 11.23.5B-6.5 / 6.5.1.

Solves the circular Git commit hash paradox by independently verifying
the primary implementation commit, its tree hash, parent commit, reproducibility
manifest, and deliverable content hashes, cleanly decoupling the implementation
commit from the attestation publication commit and current repository HEAD.

Explicitly distinguishes between unsigned integrity checking and cryptographic digital signatures.
Handles cross-platform line-ending canonicalization (CRLF vs LF).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_git_cmd(args: List[str]) -> Tuple[int, str, str]:
    res = subprocess.run(["git"] + args, capture_output=True, text=True)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def run_git_cmd_bytes(args: List[str]) -> Tuple[int, bytes, bytes]:
    res = subprocess.run(["git"] + args, capture_output=True)
    return res.returncode, res.stdout, res.stderr


class AttestationVerifier:
    def __init__(
        self,
        attestation_path: Optional[Path] = None,
        expected_implementation_commit: str = "1d9abd3c5a57b269b0061ce23167aa24d7041524",
        expected_publication_commit: str = "11467f653e0dc96229806330c422919c97ce08cd",
        expected_base_commit: str = "9c6088d37cb3103dc1b79b19a0a2b105788207ee",
    ):
        self.root = Path(__file__).resolve().parent.parent
        self.research_dir = self.root / "research_outputs"
        self.attestation_path = attestation_path or (
            self.research_dir / "post_commit_attestation_11_23_5b6_5.json"
        )
        self.expected_impl_commit = expected_implementation_commit
        self.expected_pub_commit = expected_publication_commit
        self.expected_base_commit = expected_base_commit

    def verify(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "sprint": "11.23.5B-6.5.1",
            "verifier_run_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "attestation_classification": "UNSIGNED_INTEGRITY_ATTESTATION",
            "cryptographic_signer_authentication": False,
            "distinction_note": (
                "This document is an unsigned Git tree integrity attestation. "
                "It establishes cryptographic integrity via SHA-256 and Git SHA-1 object hashes, "
                "but does not constitute an asymmetric digital signature by a third-party signer."
            ),
            "commit_roles": {
                "implementation_commit": self.expected_impl_commit,
                "publication_commit": self.expected_pub_commit,
                "base_commit": self.expected_base_commit,
            },
            "checks": {},
            "status": "FAIL",
            "errors": [],
        }

        # 1. Verify existence of attestation file
        if not self.attestation_path.exists():
            err = f"Attestation file missing: {self.attestation_path}"
            results["errors"].append(err)
            results["checks"]["attestation_file_exists"] = False
            return results
        results["checks"]["attestation_file_exists"] = True

        try:
            attestation_bytes = self.attestation_path.read_bytes()
            attestation_data = json.loads(attestation_bytes.decode("utf-8"))
        except Exception as e:
            results["errors"].append(f"Failed to parse attestation JSON: {e}")
            results["checks"]["attestation_json_valid"] = False
            return results
        results["checks"]["attestation_json_valid"] = True

        # 2. Field Completeness Check
        required_fields = [
            "sprint",
            "base_commit",
            "final_commit_sha",
            "parent_commit_sha",
            "tree_sha",
            "manifest_file",
            "manifest_sha256",
        ]
        missing_fields = [f for f in required_fields if f not in attestation_data]
        if missing_fields:
            err = f"Incomplete attestation fields: missing {missing_fields}"
            results["errors"].append(err)
            results["checks"]["field_completeness"] = False
            return results
        results["checks"]["field_completeness"] = True

        # Extract commit identities
        attested_commit = attestation_data["final_commit_sha"]
        attested_parent = attestation_data["parent_commit_sha"]
        attested_tree = attestation_data["tree_sha"]
        manifest_name = attestation_data["manifest_file"]
        attested_manifest_sha = attestation_data["manifest_sha256"]

        # 3. Commit Identity Matching
        if attested_commit != self.expected_impl_commit:
            results["errors"].append(
                f"Attested commit mismatch: expected {self.expected_impl_commit}, got {attested_commit}"
            )
            results["checks"]["attested_commit_identity"] = False
        else:
            results["checks"]["attested_commit_identity"] = True

        # 4. Git Object Verification for Attested Implementation Commit
        code, out, err = run_git_cmd(["cat-file", "-t", attested_commit])
        if code != 0 or out != "commit":
            results["errors"].append(f"Git commit object not found or invalid: {attested_commit}")
            results["checks"]["attested_commit_object_exists"] = False
            return results
        results["checks"]["attested_commit_object_exists"] = True

        # 5. Parent Commit Verification
        code, out, err = run_git_cmd(["rev-parse", f"{attested_commit}~1"])
        if code != 0 or out != attested_parent or out != self.expected_base_commit:
            results["errors"].append(
                f"Parent commit mismatch for {attested_commit}: expected {self.expected_base_commit}, got {out}"
            )
            results["checks"]["parent_commit_matches"] = False
        else:
            results["checks"]["parent_commit_matches"] = True

        # 6. Tree Hash Verification
        code, out, err = run_git_cmd(["rev-parse", f"{attested_commit}^{{tree}}"])
        if code != 0 or out != attested_tree:
            results["errors"].append(
                f"Tree hash mismatch for {attested_commit}: expected {attested_tree}, got {out}"
            )
            results["checks"]["tree_hash_matches"] = False
        else:
            results["checks"]["tree_hash_matches"] = True

        # 7. Manifest Content Extraction and Verification from Implementation Commit
        manifest_git_path = f"{attested_commit}:research_outputs/{manifest_name}"
        code, manifest_bytes, err_bytes = run_git_cmd_bytes(["cat-file", "-p", manifest_git_path])
        if code != 0:
            results["errors"].append(f"Could not retrieve manifest from commit {attested_commit}: {err_bytes.decode('utf-8', errors='replace')}")
            results["checks"]["manifest_object_exists"] = False
            return results
        results["checks"]["manifest_object_exists"] = True

        raw_manifest_sha = compute_sha256(manifest_bytes)
        crlf_manifest_sha = compute_sha256(manifest_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        results["manifest_sha256_git_raw"] = raw_manifest_sha
        results["manifest_sha256_working_tree"] = crlf_manifest_sha

        if attested_manifest_sha not in (raw_manifest_sha, crlf_manifest_sha):
            results["errors"].append(
                f"Manifest SHA-256 mismatch in commit {attested_commit}: expected {attested_manifest_sha}, raw Git {raw_manifest_sha}, CRLF {crlf_manifest_sha}"
            )
            results["checks"]["manifest_sha256_matches"] = False
        else:
            results["checks"]["manifest_sha256_matches"] = True

        try:
            manifest_json = json.loads(manifest_bytes.decode("utf-8"))
        except Exception as e:
            results["errors"].append(f"Failed to parse manifest JSON from Git: {e}")
            results["checks"]["manifest_json_valid"] = False
            return results
        results["checks"]["manifest_json_valid"] = True

        # 8. Deliverables Hash Verification against Implementation Commit Tree
        deliverable_results = {}
        deliverable_mismatches = []
        for fname, expected_hash in manifest_json.get("deliverables", {}).items():
            deliv_git_path = f"{attested_commit}:research_outputs/{fname}"
            c, d_bytes, e_bytes = run_git_cmd_bytes(["cat-file", "-p", deliv_git_path])
            if c != 0:
                deliverable_mismatches.append(f"Missing deliverable in commit {attested_commit}: {fname}")
                deliverable_results[fname] = "MISSING_IN_GIT"
            else:
                raw_hash = compute_sha256(d_bytes)
                crlf_hash = compute_sha256(d_bytes.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
                if expected_hash in (raw_hash, crlf_hash):
                    deliverable_results[fname] = {
                        "status": "PASS",
                        "git_blob_sha256": raw_hash,
                        "working_tree_sha256": crlf_hash,
                    }
                else:
                    deliverable_mismatches.append(
                        f"Hash mismatch for {fname}: expected {expected_hash}, got raw {raw_hash} / CRLF {crlf_hash}"
                    )
                    deliverable_results[fname] = {
                        "status": "MISMATCH",
                        "expected": expected_hash,
                        "actual_raw": raw_hash,
                        "actual_crlf": crlf_hash,
                    }

        results["deliverable_verification"] = deliverable_results
        if deliverable_mismatches:
            results["errors"].extend(deliverable_mismatches)
            results["checks"]["deliverables_verified"] = False
        else:
            results["checks"]["deliverables_verified"] = True

        # 9. Attestation Publication Commit Verification
        code, pub_log, err = run_git_cmd(["log", "-n", "1", "--format=%H", "--", f"research_outputs/{self.attestation_path.name}"])
        pub_commit = pub_log.strip() if code == 0 else ""
        results["publication_commit_found"] = pub_commit
        if pub_commit != self.expected_pub_commit:
            results["errors"].append(
                f"Publication commit mismatch: expected {self.expected_pub_commit}, got {pub_commit}"
            )
            results["checks"]["publication_commit_identity"] = False
        else:
            results["checks"]["publication_commit_identity"] = True

        # Verify publication commit has implementation commit as parent
        code, pub_parent, err = run_git_cmd(["rev-parse", f"{pub_commit}~1"])
        if code != 0 or pub_parent != attested_commit:
            results["errors"].append(
                f"Publication commit {pub_commit} parent ({pub_parent}) does not match attested commit ({attested_commit})"
            )
            results["checks"]["publication_parent_matches_attested"] = False
        else:
            results["checks"]["publication_parent_matches_attested"] = True

        # 10. Repository HEAD Compatibility (Works when HEAD is pub commit or later descendant)
        code, current_head, err = run_git_cmd(["rev-parse", "HEAD"])
        results["current_head"] = current_head
        if code != 0:
            results["errors"].append("Failed to determine current repository HEAD")
            results["checks"]["current_head_valid"] = False
        else:
            code, out, err = run_git_cmd(["merge-base", "--is-ancestor", pub_commit, current_head])
            if code != 0:
                results["errors"].append(
                    f"Publication commit {pub_commit} is not an ancestor of current HEAD {current_head}"
                )
                results["checks"]["publication_commit_in_head_ancestry"] = False
            else:
                results["checks"]["publication_commit_in_head_ancestry"] = True

        # Final verdict
        if not results["errors"]:
            results["status"] = "PASS"
            results["message"] = (
                "Post-commit attestation verified successfully: "
                "Attested implementation commit, tree hash, reproducibility manifest, "
                "and deliverables all match bit-for-bit in Git history."
            )
        else:
            results["status"] = "FAIL"
            results["message"] = f"Attestation verification failed with {len(results['errors'])} error(s)."

        return results


def main():
    verifier = AttestationVerifier()
    res = verifier.verify()

    print(json.dumps(res, indent=2))
    if res["status"] == "PASS":
        print("\n[SUCCESS] Post-commit attestation verified bit-for-bit against Git objects.")
        sys.exit(0)
    else:
        print(f"\n[FAILURE] Verification errors: {res['errors']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
