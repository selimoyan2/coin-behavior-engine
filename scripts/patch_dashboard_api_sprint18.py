"""Patch dashboard_api.py for Sprint 18 Research Workspace endpoints."""
from pathlib import Path

path = Path("src/coin_behavior_engine/product/dashboard_api.py")
text = path.read_text(encoding="utf-8")

# 1. Add GET routes
get_target = '            elif sub_path in ("fdr-lineage", "lineage/fdr"):\n                return HTTPStatus.OK, cls.get_fdr_lineage_api(query_params)'
get_replacement = '''            elif sub_path in ("fdr-lineage", "lineage/fdr"):
                return HTTPStatus.OK, cls.get_fdr_lineage_api(query_params)
            elif sub_path in ("research-workspace/capabilities", "workspace/capabilities"):
                return HTTPStatus.OK, cls.get_research_workspace_capabilities()
            elif sub_path in ("research-workspace/session", "workspace/session"):
                return HTTPStatus.OK, cls.get_research_workspace_session(query_params)
            elif sub_path in ("research-workspace/compare", "workspace/compare"):
                return HTTPStatus.OK, cls.get_research_workspace_compare(query_params)
            elif sub_path in ("research-workspace/evidence", "workspace/evidence"):
                return HTTPStatus.OK, cls.get_research_workspace_evidence(query_params)'''

# Normalize newlines for search/replace
if get_target not in text:
    get_target = get_target.replace("\n", "\r\n")
    get_replacement = get_replacement.replace("\n", "\r\n")

if get_target not in text:
    raise RuntimeError("Could not find get_target in dashboard_api.py")

text = text.replace(get_target, get_replacement, 1)

# 2. Add POST routes
post_target = '            elif sub_path in ("session-state", "session"):\n                return HTTPStatus.OK, cls.post_session_state_api(body)'
post_replacement = '''            elif sub_path in ("session-state", "session"):
                return HTTPStatus.OK, cls.post_session_state_api(body)
            elif sub_path in ("research-workspace/session", "workspace/session"):
                return HTTPStatus.OK, cls.post_research_workspace_session(body, query_params)
            elif sub_path in ("research-workspace/compare", "workspace/compare"):
                return HTTPStatus.OK, cls.post_research_workspace_compare(body, query_params)
            elif sub_path in ("research-workspace/evidence", "workspace/evidence"):
                return HTTPStatus.OK, cls.post_research_workspace_evidence(body, query_params)'''

if post_target not in text:
    post_target = post_target.replace("\n", "\r\n")
    post_replacement = post_replacement.replace("\n", "\r\n")

if post_target not in text:
    raise RuntimeError("Could not find post_target in dashboard_api.py")

text = text.replace(post_target, post_replacement, 1)

# 3. Add handler methods at bottom of class
handlers_code = '''
    # -----------------------------------------------------------------------
    # Sprint 18 — Unified Research Workspace API Handlers
    # -----------------------------------------------------------------------
    @classmethod
    def get_research_workspace_capabilities(cls) -> Dict[str, Any]:
        """Return research workspace capabilities, supported intervals, modules, and limits."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine
        return UnifiedResearchWorkspaceEngine.get_capabilities()

    @classmethod
    def get_research_workspace_session(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Execute or retrieve a unified research session via GET query params."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        start_val = params.get("reference_start_utc", params.get("start_utc", params.get("start", ["2022-06-01T00:00:00Z"])))[0]
        end_val = params.get("reference_end_utc", params.get("end_utc", params.get("end", ["2022-06-15T00:00:00Z"])))[0]
        asset_val = params.get("asset", ["BTCUSDT"])[0]
        interval_val = params.get("interval", ["1h"])[0]
        
        modules_raw = params.get("modules", params.get("selected_modules", []))
        if modules_raw:
            if len(modules_raw) == 1 and "," in modules_raw[0]:
                selected_modules = [m.strip() for m in modules_raw[0].split(",") if m.strip()]
            else:
                selected_modules = modules_raw
        else:
            selected_modules = None

        try:
            cand_count = int(params.get("pattern_candidates", params.get("top_k", ["5"]))[0])
        except Exception:
            cand_count = 5

        disjoint_val = params.get("disjoint_candidate_filter", params.get("disjoint", ["true"]))[0]
        disjoint_bool = str(disjoint_val).lower() in ("true", "1", "yes")

        refresh_val = params.get("force_refresh", params.get("refresh", ["false"]))[0]
        refresh_bool = str(refresh_val).lower() in ("true", "1", "yes")

        return UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_val,
            reference_end_utc=end_val,
            asset=asset_val,
            interval=interval_val,
            selected_modules=selected_modules,
            pattern_candidates=cand_count,
            disjoint_patterns=disjoint_bool,
            force_refresh=refresh_bool,
        )

    @classmethod
    def post_research_workspace_session(cls, body: Dict[str, Any], query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Execute or retrieve a unified research session via POST JSON body."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        payload = body or {}
        start_val = payload.get("reference_start_utc", payload.get("start_utc", "2022-06-01T00:00:00Z"))
        end_val = payload.get("reference_end_utc", payload.get("end_utc", "2022-06-15T00:00:00Z"))
        asset_val = payload.get("asset", "BTCUSDT")
        interval_val = payload.get("interval", "1h")
        selected_modules = payload.get("selected_modules", payload.get("modules"))
        cand_count = int(payload.get("pattern_candidates", payload.get("top_k", 5)))
        disjoint_bool = bool(payload.get("disjoint_candidate_filter", payload.get("disjoint", True)))
        refresh_bool = bool(payload.get("force_refresh", payload.get("refresh", False)))

        return UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_val,
            reference_end_utc=end_val,
            asset=asset_val,
            interval=interval_val,
            selected_modules=selected_modules,
            pattern_candidates=cand_count,
            disjoint_patterns=disjoint_bool,
            force_refresh=refresh_bool,
        )

    @classmethod
    def get_research_workspace_compare(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Compare two historical research sessions side by side via GET."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        # Case 1: Session IDs supplied
        session_a_id = params.get("session_a_id", params.get("session_a", [None]))[0]
        session_b_id = params.get("session_b_id", params.get("session_b", [None]))[0]

        if session_a_id and session_b_id and session_a_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE and session_b_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            s_a = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_a_id]
            s_b = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_b_id]
            return UnifiedResearchWorkspaceEngine.compare_sessions(s_a, s_b)

        # Case 2: Windows supplied directly
        start_a = params.get("start_a", params.get("reference_start_utc", ["2022-06-01T00:00:00Z"]))[0]
        end_a = params.get("end_a", params.get("reference_end_utc", ["2022-06-15T00:00:00Z"]))[0]
        start_b = params.get("start_b", params.get("candidate_start_utc", ["2024-07-27T01:00:00Z"]))[0]
        end_b = params.get("end_b", params.get("candidate_end_utc", ["2024-08-10T01:00:00Z"]))[0]
        interval = params.get("interval", ["1h"])[0]

        s_a = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_a,
            reference_end_utc=end_a,
            interval=interval,
            pattern_candidates=3,
        )
        s_b = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_b,
            reference_end_utc=end_b,
            interval=interval,
            pattern_candidates=3,
        )
        return UnifiedResearchWorkspaceEngine.compare_sessions(s_a, s_b)

    @classmethod
    def post_research_workspace_compare(cls, body: Dict[str, Any], query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Compare two historical research sessions side by side via POST."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        payload = body or {}
        session_a_id = payload.get("session_a_id")
        session_b_id = payload.get("session_b_id")

        if session_a_id and session_b_id and session_a_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE and session_b_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            s_a = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_a_id]
            s_b = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_b_id]
            return UnifiedResearchWorkspaceEngine.compare_sessions(s_a, s_b)

        start_a = payload.get("start_a", "2022-06-01T00:00:00Z")
        end_a = payload.get("end_a", "2022-06-15T00:00:00Z")
        start_b = payload.get("start_b", "2024-07-27T01:00:00Z")
        end_b = payload.get("end_b", "2024-08-10T01:00:00Z")
        interval = payload.get("interval", "1h")

        s_a = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_a,
            reference_end_utc=end_a,
            interval=interval,
            pattern_candidates=3,
        )
        s_b = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_b,
            reference_end_utc=end_b,
            interval=interval,
            pattern_candidates=3,
        )
        return UnifiedResearchWorkspaceEngine.compare_sessions(s_a, s_b)

    @classmethod
    def get_research_workspace_evidence(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Export unified research evidence package matching format CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        session_id = params.get("session_id", [None])[0]
        if session_id and session_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            s_data = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_id]
        else:
            s_data = cls.get_research_workspace_session(params)

        cmp_data = None
        session_b_id = params.get("session_b_id", [None])[0]
        if session_b_id and session_b_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            cmp_data = UnifiedResearchWorkspaceEngine.compare_sessions(
                s_data, UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_b_id]
            )

        return UnifiedResearchWorkspaceEngine.export_unified_evidence_package(s_data, cmp_data)

    @classmethod
    def post_research_workspace_evidence(cls, body: Dict[str, Any], query_params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Export unified research evidence package matching format CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0 via POST."""
        from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

        payload = body or {}
        session_id = payload.get("session_id")
        if session_id and session_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            s_data = UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_id]
        else:
            s_data = cls.post_research_workspace_session(payload, query_params)

        cmp_data = None
        session_b_id = payload.get("session_b_id")
        if session_b_id and session_b_id in UnifiedResearchWorkspaceEngine._SESSION_CACHE:
            cmp_data = UnifiedResearchWorkspaceEngine.compare_sessions(
                s_data, UnifiedResearchWorkspaceEngine._SESSION_CACHE[session_b_id]
            )

        return UnifiedResearchWorkspaceEngine.export_unified_evidence_package(s_data, cmp_data)
'''

# Find the end of ProductDashboardApiService class before START_TIME
end_marker = "START_TIME = time.time()"
if "\r\n" in text:
    handlers_code = handlers_code.replace("\n", "\r\n")

if end_marker not in text:
    raise RuntimeError("Could not find START_TIME in dashboard_api.py")

text = text.replace(end_marker, handlers_code + "\r\n\r\n" + end_marker if "\r\n" in text else handlers_code + "\n\n" + end_marker)

path.write_text(text, encoding="utf-8")
print("Successfully patched dashboard_api.py for Sprint 18!")
