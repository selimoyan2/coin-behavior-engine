"""
Reproducible Research Notebook Export (.ipynb) for Coin Behavior Engine.

Generates self-contained, offline-executable Jupyter research notebooks
allowing independent researchers to verify historical findings with standard Python libraries.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ResearchNotebookExporter:
    """
    Generates standard Jupyter Notebook (.ipynb) v4 artifacts
    that execute entirely offline without live API credentials.
    """

    DISCLAIMER_TR = (
        "Bu Jupyter Araştırma Defteri yalnızca tarihsel piyasa analizi amacıyla üretilmiştir. "
        "Yatırım tavsiyesi veya canlı alım-satım sinyali teşkil etmez."
    )

    @classmethod
    def generate_cpi_reproduction_notebook(
        cls,
        hypothesis_id: str = "HYP-CPI-VOL-01",
        cohort: str = "US_CPI",
        window_hours: int = 12,
        target_asset: str = "BTCUSDT",
    ) -> Dict[str, Any]:
        """
        Creates an offline runnable Jupyter notebook structure.
        """
        cells = []

        # Cell 1: Title and Scientific Overview (Markdown)
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                f"# Coin Behavior Engine — Bağımsız Bilimsel Araştırma Defteri\n",
                f"## Hipotez: {cohort} Açıklamaları Sonrası Tarihsel Volatilite Genişlemesi\n",
                f"\n",
                f"- **Hipotez Kodu:** `{hypothesis_id}`\n",
                f"- **Hedef Varlık:** `{target_asset}` (Spot Parquet Veri Seti)\n",
                f"- **Pencere:** `{window_hours} saat` öncesi vs `{window_hours} saat` sonrası\n",
                f"- **Model Sürümü:** `CBE-0.7.0 (FROZEN)`\n",
                f"- **Oluşturulma Tarihi:** `{datetime.now(timezone.utc).isoformat()}`\n",
                f"\n",
                f"> **ÖNEMLİ YASAL UYARI:** {cls.DISCLAIMER_TR}\n"
            ]
        })

        # Cell 2: Imports (Code)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Gerekli standart bilimsel kütüphanelerin yüklenmesi\n",
                "import math\n",
                "from pathlib import Path\n",
                "import numpy as np\n",
                "import pandas as pd\n",
                "import matplotlib.pyplot as plt\n",
                "\n",
                "print('Bilimsel kütüphaneler başarıyla yüklendi.')\n"
            ]
        })

        # Cell 3: Data Loading (Code)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 1. Kanonik makro olayların ve mum verilerinin yerel diskten yüklenmesi (Offline)\n",
                "events_path = Path('research_outputs/historical_macro_events_11_23.parquet')\n",
                "df_events = pd.read_parquet(events_path)\n",
                "\n",
                f"# {cohort} kohortuna ait doğrulanmış olayların filtrelenmesi\n",
                "cpi_events = df_events[\n",
                "    (df_events['event_id'].str.contains('CPI') | df_events['event_name'].str.contains('CPI')) &\n",
                "    (df_events['verification_status'] != 'EVENT_QUARANTINED')\n",
                "].copy()\n",
                "\n",
                "# 2. Saatlik mum verilerinin yüklenmesi\n",
                "candle_files = sorted(Path('data/binance_spot_multiyear/1h').glob('BTCUSDT-1h-*.parquet'))\n",
                "dfs = [pd.read_parquet(f) for f in candle_files]\n",
                "df_candles = pd.concat(dfs, ignore_index=True)\n",
                "df_candles['dt'] = pd.to_datetime(df_candles['open_time'], unit='ms', utc=True)\n",
                "df_candles = df_candles.sort_values('dt').drop_duplicates('dt').reset_index(drop=True)\n",
                "\n",
                "print(f'Doğrulanmış Olay Sayısı: {len(cpi_events)}')\n",
                "print(f'Toplam Mum Sayısı: {len(df_candles)}')\n"
            ]
        })

        # Cell 4: Realized Volatility Calculation (Code)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 3. Ayrık mum hizalamalı gerçekleşen oynaklık (Realized Volatility) hesabı\n",
                "def realized_vol(prices):\n",
                "    rets = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]\n",
                "    if len(rets) < 2:\n",
                "        return 0.0\n",
                "    m = sum(rets) / len(rets)\n",
                "    var = sum((r - m)**2 for r in rets) / (len(rets) - 1)\n",
                "    return math.sqrt(var)\n",
                "\n",
                f"win_h = {window_hours}\n",
                "pre_vols = []\n",
                "post_vols = []\n",
                "ratios = []\n",
                "\n",
                "for _, ev in cpi_events.iterrows():\n",
                "    t0 = pd.to_datetime(ev['release_at_utc'], utc=True)\n",
                "    t0_idx = int((df_candles['dt'] - t0).abs().idxmin())\n",
                "    \n",
                "    pre_slice = df_candles.iloc[max(0, t0_idx - win_h) : t0_idx]\n",
                "    post_slice = df_candles.iloc[t0_idx : min(len(df_candles), t0_idx + win_h)]\n",
                "    \n",
                "    if len(pre_slice) >= 2 and len(post_slice) >= 2:\n",
                "        v_pre = realized_vol(pre_slice['close'].tolist())\n",
                "        v_post = realized_vol(post_slice['close'].tolist())\n",
                "        if v_pre > 1e-9:\n",
                "            pre_vols.append(v_pre * 100.0)\n",
                "            post_vols.append(v_post * 100.0)\n",
                "            ratios.append(v_post / v_pre)\n",
                "\n",
                "print(f'Ortalama Öncesi Volatilite: %{np.mean(pre_vols):.3f}')\n",
                "print(f'Ortalama Sonrası Volatilite: %{np.mean(post_vols):.3f}')\n",
                "print(f'Ortalama Genişleme Oranı: {np.mean(ratios):.3f}x')\n",
                "print(f'Medyan Genişleme Oranı: {np.median(ratios):.3f}x')\n"
            ]
        })

        # Cell 5: Bootstrap CI and Effect Size (Code)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 4. Parametrik Olmayan Bootstrap Güven Aralığı ve Etki Büyüklüğü (Cohen\\'s d)\n",
                "rng = np.random.RandomState(42)\n",
                "boot_means = [np.mean(rng.choice(ratios, size=len(ratios), replace=True)) for _ in range(1000)]\n",
                "ci_lower = np.percentile(boot_means, 2.5)\n",
                "ci_upper = np.percentile(boot_means, 97.5)\n",
                "\n",
                "# Cohen's d\n",
                "pooled_sd = np.sqrt((np.var(pre_vols, ddof=1) + np.var(post_vols, ddof=1)) / 2.0)\n",
                "cohens_d = (np.mean(post_vols) - np.mean(pre_vols)) / pooled_sd\n",
                "\n",
                "print(f'95% Bootstrap Güven Aralığı: [{ci_lower:.3f}x, {ci_upper:.3f}x]')\n",
                "print(f'Cohen\\'s d Etki Büyüklüğü: {cohens_d:.3f}')\n",
                "print(f'Etkisizlik (1.0x) Dışlandı mı?: {ci_lower > 1.0}')\n"
            ]
        })

        # Cell 6: Visual Distribution Plot (Code)
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# 5. Dağılım ve Karşılaştırma Grafiği\n",
                "plt.figure(figsize=(10, 5))\n",
                "plt.hist(ratios, bins=20, color='#3B82F6', edgecolor='white', alpha=0.8, label='Olay Oranları')\n",
                "plt.axvline(1.0, color='#EF4444', linestyle='--', linewidth=2, label='Etkisizlik Çizgisi (1.0x)')\n",
                "plt.axvline(np.mean(ratios), color='#10B981', linestyle='-', linewidth=2, label=f'Ortalama: {np.mean(ratios):.2f}x')\n",
                "plt.title(f'{cohort} Sonrası Oynaklık Genişleme Oranı Dağılımı (N={len(ratios)})')\n",
                "plt.xlabel('Genişleme Oranı (Sonrası / Öncesi)')\n",
                "plt.ylabel('Olay Sayısı')\n",
                "plt.legend()\n",
                "plt.grid(True, alpha=0.3)\n",
                "plt.tight_layout()\n",
                "plt.show()\n"
            ]
        })

        notebook = {
            "cells": cells,
            "metadata": {
                "language_info": {
                    "name": "python",
                    "version": "3.11"
                },
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                },
                "cbe_metadata": {
                    "generator": "Coin Behavior Engine Research Notebook Exporter",
                    "hypothesis_id": hypothesis_id,
                    "target_asset": target_asset,
                    "canonical_model": "CBE-0.7.0 (FROZEN)",
                }
            },
            "nbformat": 4,
            "nbformat_minor": 5
        }

        return notebook

    @classmethod
    def export_notebook_to_file(cls, output_path: Path, **kwargs) -> Path:
        """Saves generated notebook to .ipynb JSON format."""
        nb = cls.generate_cpi_reproduction_notebook(**kwargs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(nb, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_path
