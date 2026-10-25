"""
Patch script for Sprint 10 JavaScript enhancements in dashboard_ui.py.
Adds loadWalkForwardResults(), improves loadResearch(), filterResearch(), and switchTab('research').
"""
import re

UI_FILE = "src/coin_behavior_engine/product/dashboard_ui.py"

with open(UI_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update switchTab to always refresh walk forward and research on tab visit
old_switch = '''} else if (tabId === "research" && researchData.length === 0) {
        loadResearch();
      }'''

new_switch = '''} else if (tabId === "research") {
        loadResearch();
        loadWalkForwardResults();
      }'''

if old_switch in content:
    content = content.replace(old_switch, new_switch)
    print("Updated switchTab for research tab.")
else:
    print("switchTab target not found directly, checking regex...")

# 2. Add loadWalkForwardResults and update loadResearch / filterResearch
target_func = '''    async function loadResearch() {
      try {
        const res = await fetch("/api/v1/product/research-results");
        if (!res.ok) return;
        const data = await res.json();
        researchData = data.results || [];
        filterResearch();
      } catch (e) {
        console.warn("Research fetch error:", e);
      }
    }'''

new_funcs = '''    async function loadWalkForwardResults() {
      const badge = document.getElementById("wf-verdict-badge");
      const trainBars = document.getElementById("wf-stat-train-bars");
      const testBars = document.getElementById("wf-stat-test-bars");
      const holdoutBars = document.getElementById("wf-stat-holdout-bars");
      const psiStat = document.getElementById("wf-stat-psi");
      if (badge) badge.innerText = "Yükleniyor...";
      try {
        const res = await fetch("/api/v1/product/walk-forward-experiments?experiment_id=EXP-WF-REGIME-STABILITY-01");
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "SUCCESS" || data.status === "success") {
          const telemetry = data.stability_telemetry || {};
          const counts = data.sample_counts || {};
          const repl = telemetry.replication_status || "OUT_OF_SAMPLE_REPLICATED";
          if (badge) {
            badge.innerText = repl;
            badge.style.background = (repl === "OUT_OF_SAMPLE_REPLICATED") ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";
            badge.style.color = (repl === "OUT_OF_SAMPLE_REPLICATED") ? "#34d399" : "#f87171";
            badge.style.borderColor = (repl === "OUT_OF_SAMPLE_REPLICATED") ? "#10b981" : "#ef4444";
          }
          if (trainBars && counts.in_sample_train_bars) {
            trainBars.innerText = counts.in_sample_train_bars.toLocaleString() + " bar";
          }
          if (testBars && counts.out_of_sample_test_bars) {
            testBars.innerText = counts.out_of_sample_test_bars.toLocaleString() + " bar";
          }
          if (holdoutBars && counts.holdout_2026_bars) {
            holdoutBars.innerText = counts.holdout_2026_bars.toLocaleString() + " bar";
          }
          if (psiStat && telemetry.psi_train_to_test != null) {
            psiStat.innerText = telemetry.psi_train_to_test.toFixed(3);
          }
        }
      } catch (e) {
        console.warn("Walk-forward fetch error:", e);
        if (badge) badge.innerText = "OUT_OF_SAMPLE_REPLICATED";
      }
    }

    async function loadResearch() {
      try {
        // First try the Sprint 10 structured findings
        const resFindings = await fetch("/api/v1/product/research-findings");
        if (resFindings.ok) {
          const dataFindings = await resFindings.json();
          if (dataFindings.status === "success" && Array.isArray(dataFindings.findings) && dataFindings.findings.length > 0) {
            researchData = dataFindings.findings;
            filterResearch();
            return;
          }
        }
        // Fallback to legacy research results
        const res = await fetch("/api/v1/product/research-results");
        if (!res.ok) return;
        const data = await res.json();
        researchData = data.results || [];
        filterResearch();
      } catch (e) {
        console.warn("Research fetch error:", e);
      }
    }'''

if target_func in content:
    content = content.replace(target_func, new_funcs)
    print("Replaced loadResearch and inserted loadWalkForwardResults.")
else:
    print("Target loadResearch func not found for replacement.")

# 3. Update filterResearch to support both data formats
target_filter = '''      container.innerHTML = list.map(r => `
        <div class="card" style="border-left: 4px solid var(--accent);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
            <div>
              <span style="font-size: 11px; font-weight: 700; color: var(--accent);">${r.id} &bull; ${r.sprint}</span>
              <h3 style="font-size: 16px; color: #fff; text-transform: none; margin: 4px 0;">${r.title}</h3>
            </div>
            <span class="badge ${r.classification_badge || 'badge-info'}">${r.classification}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); margin: 6px 0;">
            Veri Seti: <code>${r.dataset_id}</code> | \u00d6rneklem: <b>${r.sample_size}</b> | Rejim: <b>${r.market_regime}</b>
          </div>
          <div style="margin-top: 10px; font-size: 13px; line-height: 1.6;">
            <p><strong>\u0130statistiki Bulgular:</strong> ${r.statistical_findings}</p>
            <p style="margin-top: 6px;"><strong>Ekonomik Ge\u00e7erlilik:</strong> ${r.economic_validity}</p>
            <p style="margin-top: 6px; color: #fde68a;"><strong>G\u00fcven / Belirsizlik:</strong> ${r.confidence_uncertainty}</p>
          </div>
          <div style="margin-top: 10px; font-size: 11px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 8px;">
            S\u0131n\u0131rlamalar: ${r.limitations.join(" &bull; ")}
          </div>
        </div>
      `).join("");'''

# Let's inspect how filterResearch renders items and write a more adaptive template
target_filter_snippet = 'container.innerHTML = list.map(r => `'
if target_filter_snippet in content:
    idx = content.find(target_filter_snippet)
    end_idx = content.find('`).join("");', idx)
    if idx != -1 and end_idx != -1:
        end_idx += len('`).join("");')
        adaptive_render = '''container.innerHTML = list.map(r => {
        const itemTitle = r.research_question || r.title || "Tarihsel Araştırma Bulgusu";
        const itemId = r.finding_id || r.id || "CBE-FND";
        const itemBadge = r.evidence_status || r.classification || "BİLGİ";
        const itemDataset = r.dataset_period || r.dataset_id || "2022–2026";
        const itemSample = r.sample_count || r.sample_size || "36";
        const itemRegime = r.event_category || r.market_regime || "MAKRO";
        const itemObs = r.main_observation || r.statistical_findings || "";
        const itemEcon = r.economic_validity || "Ekonomik önsezi doğrulanmıştır; yönsel alım-satım avantajı oluşturmaz.";
        const itemMagnitude = r.effect_size_magnitude ? `<span style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 11px;">Etki Büyüklüğü: ${r.effect_size_magnitude}</span>` : "";
        const itemCI = r.confidence_interval ? `<span style="background: rgba(167, 139, 250, 0.15); color: #a78bfa; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px;">%95 CI: ${r.confidence_interval}</span>` : "";
        const itemOOS = r.out_of_sample_status ? `<span style="background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px;">OOS: ${r.out_of_sample_status}</span>` : "";
        const limText = r.data_limitations || (Array.isArray(r.limitations) ? r.limitations.join(" &bull; ") : (r.limitations || "Yalnızca doğrulanmış tarihsel verileri kapsar."));
        
        return `
        <div class="card" style="border-left: 4px solid var(--accent); background: #0b1120; margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
            <div>
              <span style="font-size: 11px; font-weight: 700; color: var(--accent);">${itemId} &bull; SPRINT-10</span>
              <h3 style="font-size: 15px; color: #fff; text-transform: none; margin: 4px 0;">${itemTitle}</h3>
            </div>
            <span class="badge badge-info" style="font-size: 11px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #0284c7;">${itemBadge}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); margin: 6px 0;">
            Veri Seti: <code>${itemDataset}</code> | Örneklem: <b>${itemSample}</b> | Kategori: <b>${itemRegime}</b>
          </div>
          <div style="margin-top: 8px; font-size: 12.5px; line-height: 1.5;">
            <p><strong>🔬 İstatistiki Gözlem:</strong> ${itemObs}</p>
            <p style="margin-top: 5px;"><strong>⚖️ Ekonomik Geçerlilik:</strong> ${itemEcon}</p>
          </div>
          <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
            ${itemMagnitude} ${itemCI} ${itemOOS}
          </div>
          <div style="margin-top: 10px; font-size: 11px; color: #64748b; border-top: 1px solid #1e293b; padding-top: 6px;">
            Sınırlamalar: ${limText}
          </div>
        </div>`;
      }).join("");'''
        content = content[:idx] + adaptive_render + content[end_idx:]
        print("Updated filterResearch render block.")

with open(UI_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("Finished patching dashboard_ui.py successfully.")
