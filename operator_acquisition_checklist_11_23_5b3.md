# CBE — SPRINT 11.23.5B-3: OPERATOR EVIDENCE ACQUISITION CHECKLIST
## Air-Gapped / Manual Procurement of Official BLS CPI Schedule Evidence

**Target Agency:** U.S. Bureau of Labor Statistics (BLS)  
**Target Release:** Consumer Price Index (CPI) YoY Release  
**Status:** ACTION REQUIRED BY HUMAN OPERATOR  
**Date:** 2026-10-20 17:29:11 UTC

---

### STEP-BY-STEP ACQUISITION INSTRUCTIONS

The Coin Behavior Engine operates in strictly offline research mode and cannot autonomously download external web pages. The human operator must manually acquire and import the authentic schedule document following these steps:

#### Step 1: Secure Browser Download
- Navigate from an authorized operator workstation to the official BLS CPI release schedule:
  `https://www.bls.gov/schedule/news_release/cpi.htm`
- Alternatively, access the BLS comprehensive annual release calendar:
  `https://www.bls.gov/schedule/2026/home.htm`
- Save the complete, unmodified HTML or PDF document locally.

#### Step 2: Checksum Verification on Operator Workstation
- On the operator workstation, compute the cryptographic SHA-256 hash:
  - Linux/macOS: `sha256sum cpi_schedule.htm`
  - Windows PowerShell: `Get-FileHash -Algorithm SHA256 .\cpi_schedule.htm`
- Record the resulting 64-character hexadecimal digest.

#### Step 3: Record Provenance Sidecar
- Prepare a provenance JSON sidecar file (`cpi_schedule.provenance.json`):
  ```json
  {
    "declared_source_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
    "retrieved_at_utc": "2026-10-20T17:29:11.687164+00:00",
    "retrieval_operator_id": "OP-ADMIN-01",
    "retrieval_method": "MANUAL_AIR_GAPPED_OPERATOR_DOWNLOAD",
    "workstation_ip_hash": "e3b0c442...",
    "declared_sha256": "<INSERT_COMPUTED_HASH>"
  }
  ```

#### Step 4: Ingestion via Controlled Importer
- Transfer the document and sidecar to the CBE repository environment.
- Ingest via the `ControlledEvidenceImporter`:
  ```python
  from coin_behavior_engine.prospective import ControlledEvidenceImporter
  importer = ControlledEvidenceImporter()
  receipt = importer.import_evidence(
      raw_bytes=raw_document_bytes,
      declared_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
      declared_mime_type="text/html",
      provenance_sidecar=provenance_data,
      expected_sha256=expected_hash,
  )
  ```

#### Step 5: Verification & Event Identity Derivation
- Pass the imported receipt to `OfficialScheduleVerificationEngine.verify_schedule_offline()`:
  - Confirm release date and 08:30:00 AM Eastern time.
  - Verify deterministic zoneinfo UTC conversion.
  - Derive canonical event ID: `EVT-BLS-CPI-2026Mxx-YYYYMMDD`.
  - Confirm no placeholder tokens exist.

#### Step 6: Two-Person Review & Formal Approval
- Research operator drafts `PilotProposal` v2.0.0.
- Distinct `APPROVAL_ADMIN` reviews proposal and signs authorization record using offline provisioned production key.
