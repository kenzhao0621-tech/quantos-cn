# QuantOS CN — 中国 A 股智能量化操作系统

**运行模式:** RESEARCH_ONLY / PAPER_TRADING / SHADOW_LIVE  
**真实执行:** MANUAL_CONFIRM_ONLY（本批次禁用自动实盘）  
**内核:** VeighNa/vn.py 事件引擎（适配层） + Qlib 研究平面  
**控制平面:** FastAPI Gateway + 中文门户  

## 子系统状态

- Gateway: READY
- vn.py Runtime: adapter/shim (native optional)
- Qlib Provider: DuckDB/Parquet canonical
- Paper/Shadow: READY
- Risk Engine: 双层风控
- PDF 日报: READY
