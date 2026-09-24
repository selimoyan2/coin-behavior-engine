"""Script to execute Sprint 01.1 Research Integrity, Threshold & Leakage Audit."""

from coin_behavior_engine.audit.runner import ResearchIntegrityAuditor

if __name__ == "__main__":
    auditor = ResearchIntegrityAuditor()
    results = auditor.run_all_audits()
