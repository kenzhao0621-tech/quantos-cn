# Rejected Methods

| Method | Source | Rejection reason |
|--------|--------|------------------|
| Stockformer (wavelet + multi-task attention) | arXiv 2401.06139 | CSI300-only; no beat vs z-score baseline on full A-share universe after realistic costs |
| CLGNN (CNN-LSTM-GNN) | Entropy 2025 | Graph instability; weak transaction-cost modeling; reproduction burden |
| Self-attention cross-sectional ranker | FinRL 2024 | Long-short framing; full text not verified; retail lot constraints |
| Deep LSTM/Transformer WEI stack | Springer 2026 | Institutional scale; test-set tuning risk; not validated on our DuckDB pipeline |
| LLM / RL / agentic trading | N/A | Spec explicitly forbids adding complexity without OOS economic proof |

**Retained baseline:** Multi-factor z-score composite (momentum + trend + vol penalty) with tradability and cost penalties.
