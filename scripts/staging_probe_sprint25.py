"""
Staging Verification Probe: Sprint 25 Research Decision Intelligence Platform
Runs against http://127.0.0.1:18080 on staging host (168.231.125.238).
Verifies:
  1. Health & readiness endpoints
  2. Workspace overview with decision intelligence components
  3. Evidence Graph endpoint (filtering, node/edge counts)
  4. Scientific Readiness scorecards endpoint
  5. Evidence Gaps endpoint
  6. Research Priorities endpoint
  7. Reproducibility Lab procedures & offline execution POST
  8. Research Decision Reports (JSON & HTML format)
  9. Negative Security Check: unauthorized procedure execution blocked
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:18080"


def http_get(path: str, headers: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "application/json" in content_type:
                data = json.loads(raw)
            else:
                data = {"content": raw, "content_type": content_type}
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data


def http_post(path: str, payload: dict, headers: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")
            if "application/json" in content_type:
                data = json.loads(raw)
            else:
                data = {"content": raw, "content_type": content_type}
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data


def run_checks():
    results = {}

    print("=== SPRINT 25 STAGING VERIFICATION PROBE ===")

    # 1. Health
    status, data = http_get("/health")
    assert status == 200, f"/health returned {status}"
    results["health"] = {"status": status, "data": data}
    print("[PASS] 1. /health OK")

    # 2. Ready
    status, data = http_get("/ready")
    assert status == 200, f"/ready returned {status}"
    results["ready"] = {"status": status, "data": data}
    print("[PASS] 2. /ready OK")

    # 3. Workspace Overview
    status, data = http_get("/api/v1/product/workspace/overview")
    assert status == 200, f"/overview returned {status}"
    cm = data.get("canonical_model", {})
    ta = data.get("trading_authorization", {})
    sd = data.get("storage_durability", {})
    assert cm.get("version") == "CBE-0.7.0", f"Unexpected model version: {cm.get('version')}"
    assert cm.get("status") == "STRICTLY_FROZEN", f"Unexpected status: {cm.get('status')}"
    assert ta.get("governance_decision") == "TECHNICAL_NO_GO", f"Unexpected governance: {ta.get('governance_decision')}"
    assert ta.get("trading_eligibility") == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
    
    # Check decision intelligence presence in overview
    di = data.get("decision_intelligence", {})
    assert di.get("graph_nodes_count", 0) > 0, f"Unexpected graph_nodes_count: {di.get('graph_nodes_count')}"
    assert di.get("graph_edges_count", 0) > 0, f"Unexpected graph_edges_count: {di.get('graph_edges_count')}"
    assert "total_gaps_count" in di, "Missing total_gaps_count in overview"
    assert "reproducible_procedures_count" in di, "Missing reproducible_procedures_count in overview"

    results["overview"] = {
        "status": status,
        "canonical_model": cm.get("version"),
        "model_status": cm.get("status"),
        "governance_decision": ta.get("governance_decision"),
        "trading_prohibition": ta.get("trading_eligibility"),
        "storage_durability": sd.get("classification"),
        "decision_intelligence": di,
    }
    print(f"[PASS] 3. /overview invariants & decision intelligence verified ({di.get('graph_nodes_count')} nodes, {di.get('graph_edges_count')} edges)")

    # 4. Evidence Graph
    status, data = http_get("/api/v1/product/workspace/evidence-graph")
    assert status == 200, f"/workspace/evidence-graph returned {status}"
    graph = data.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    assert len(nodes) >= 15, f"Expected at least 15 nodes, got {len(nodes)}"
    assert len(edges) >= 15, f"Expected at least 15 edges, got {len(edges)}"
    results["evidence_graph"] = {
        "status": status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "missing_link_count": len(data.get("missing_links", [])),
    }
    print(f"[PASS] 4. Evidence Graph verified: {len(nodes)} nodes, {len(edges)} edges, {len(data.get('missing_links', []))} missing links")

    # 5. Scientific Readiness Scorecards
    status, data = http_get("/api/v1/product/workspace/readiness")
    assert status == 200, f"/workspace/readiness returned {status}"
    scorecards = data.get("scorecards", [])
    assert len(scorecards) >= 5, f"Expected at least 5 scorecards, got {len(scorecards)}"
    
    # Check RES-FUND-01
    fund_cards = [c for c in scorecards if c.get("record_id") == "RES-FUND-01"]
    assert len(fund_cards) == 1, "RES-FUND-01 scorecard not found"
    fund_card = fund_cards[0]
    assert "heuristic_readiness_index" in fund_card
    assert "overall_verdict" in fund_card
    results["scientific_readiness"] = {
        "status": status,
        "scorecard_count": len(scorecards),
        "sample_scorecard": {
            "record_id": fund_card.get("record_id"),
            "heuristic_readiness_index": fund_card.get("heuristic_readiness_index"),
            "overall_verdict": fund_card.get("overall_verdict"),
            "critical_gates_passed": fund_card.get("critical_gates_passed"),
            "total_critical_gates": fund_card.get("total_critical_gates"),
        },
    }
    print(f"[PASS] 5. Scientific Readiness verified: {len(scorecards)} scorecards. RES-FUND-01 verdict: {fund_card.get('overall_verdict')}")

    # 6. Evidence Gaps Analyzer
    status, data = http_get("/api/v1/product/workspace/evidence-gaps")
    assert status == 200, f"/workspace/evidence-gaps returned {status}"
    gaps = data.get("gaps", [])
    summary = data.get("summary", {})
    assert len(gaps) >= 5, f"Expected at least 5 gaps, got {len(gaps)}"
    results["evidence_gaps"] = {
        "status": status,
        "total_gaps": len(gaps),
        "summary": summary,
    }
    print(f"[PASS] 6. Evidence Gaps verified: {len(gaps)} gaps identified across catalog")

    # 7. Research Priorities Engine
    status, data = http_get("/api/v1/product/workspace/priorities")
    assert status == 200, f"/workspace/priorities returned {status}"
    tasks = data.get("prioritized_tasks") or data.get("tasks", [])
    assert len(tasks) >= 5, f"Expected at least 5 priority tasks, got {len(tasks)}"
    # Verify deterministic rank 1
    assert tasks[0].get("rank") == 1
    assert tasks[0].get("priority_score", 0) >= tasks[-1].get("priority_score", 0)
    results["research_priorities"] = {
        "status": status,
        "task_count": len(tasks),
        "top_task": tasks[0].get("title_en") or tasks[0].get("title_tr"),
        "top_rank_score": tasks[0].get("priority_score"),
    }
    print(f"[PASS] 7. Research Priorities verified: {len(tasks)} ranked tasks. Top task: {tasks[0].get('title_en') or tasks[0].get('title_tr')}")

    # 8. Reproducibility Lab Procedures & Execution
    status, data = http_get("/api/v1/product/workspace/reproducibility/procedures")
    assert status == 200, f"/reproducibility/procedures returned {status}"
    procedures = data.get("procedures", {})
    assert len(procedures) >= 3, f"Expected at least 3 procedures, got {len(procedures)}"
    
    # Test POST execution for allowlisted procedure
    exec_payload = {
        "record_id": "RES-FUND-01",
        "procedure_name": "PROC_FUNDING_RATE_SUMMARY",
    }
    exec_status, exec_data = http_post("/api/v1/product/workspace/reproducibility/execute", exec_payload)
    assert exec_status == 200, f"/reproducibility/execute returned {exec_status}"
    assert exec_data.get("status") == "success"
    prov = exec_data.get("provenance", {})
    assert prov.get("is_independent_replication") is False, "Violation: local re-execution must not claim independent replication"
    assert prov.get("status") in ("OUTPUTS_MATCHED", "VERIFIED", "COMPLETED", "REPRODUCED_LOCALLY")
    results["reproducibility"] = {
        "status": status,
        "procedure_count": len(procedures),
        "execution_test": {
            "status": exec_status,
            "provenance_status": prov.get("status"),
            "independent_replication_flag": prov.get("is_independent_replication"),
            "run_id": prov.get("run_id"),
        },
    }
    print(f"[PASS] 8. Reproducibility Lab verified: {len(procedures)} procedures. Local execution status: {prov.get('status')} (non-replication invariant intact).")

    # 9. Research Decision Reports (JSON & HTML)
    status_json, data_json = http_get("/api/v1/product/workspace/decision-reports?record_id=RES-FUND-01&format=json")
    assert status_json == 200, f"/decision-reports (json) returned {status_json}"
    rep_json = data_json.get("report", {})
    assert rep_json.get("record_id") == "RES-FUND-01"
    assert "sections" in rep_json or "overall_verdict" in rep_json

    status_html, data_html = http_get("/api/v1/product/workspace/decision-reports?record_id=RES-FUND-01&format=html")
    assert status_html == 200, f"/decision-reports (html) returned {status_html}"
    html_content = data_html.get("html_content") or data_html.get("content", "")
    assert "<!DOCTYPE html>" in html_content or "<html" in html_content
    assert "RES-FUND-01" in html_content
    results["decision_reports"] = {
        "status_json": status_json,
        "status_html": status_html,
        "html_size_bytes": len(html_content),
        "record_id": rep_json.get("record_id"),
    }
    print(f"[PASS] 9. Research Decision Reports verified: JSON & HTML ({len(html_content)} bytes)")

    # 10. Negative Security Check: unauthorized procedure execution blocked
    bad_exec_payload = {
        "record_id": "RES-FUND-01",
        "procedure_name": "arbitrary_unauthorized_command_execution",
    }
    bad_status, bad_data = http_post("/api/v1/product/workspace/reproducibility/execute", bad_exec_payload)
    assert bad_status == 200 or bad_status == 400
    prov_bad = bad_data.get("provenance", {})
    assert prov_bad.get("status") in ("REPRODUCTION_BLOCKED", "ERROR", "BLOCKED") or bad_data.get("status") == "error"
    results["negative_security_check"] = {
        "status": bad_status,
        "rejection_response": bad_data.get("message") or prov_bad.get("status"),
    }
    print(f"[PASS] 10. Negative Security Check verified: unauthorized procedure rejected.")

    # Save summary
    with open("/tmp/staging_sprint25_probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n>>> ALL 10 STAGING PROBE SUITES PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    run_checks()
