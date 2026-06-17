# QuantOS CN 产品介绍

**版本：** 4.x · **市场：** 中国 A 股 · **形态：** 本地 Web 门户 + Python 网关  
**最后更新：** 2026-06-17

---

## 一句话定位

**QuantOS CN** 是面向个人投资者与量化研究者的 **A 股本地量化操作系统**：把「数据 → 选股 → 模拟 → 辅助实盘」串成一条可审计、可解释、可复现的闭环，且**默认不自动扣款**。

---

## 解决什么问题？

### 对新手投资者

- 不知道量化工具从何下手 → **四步向导**（更新数据 / 选股 / 模拟 / 券商）  
- 看不懂代码和因子 → **中文门户** + **增强版选股指南** + 名称与专业说明列  
- 担心误触实盘 → **Paper 优先** + 风险确认弹窗 + 实盘门控  

### 对量化研究者

- 需要本地数据与可复现回测 → **DuckDB 仓库** + 网关回测 + Purged K-Fold  
- 需要 honest 的样本外结论 → 验证状态显式标注 `NOT_READY` / `PASS`  
- 需要接券商但不写死一家 → **多券商注册表** + 执行路径路由  

### 对注重隐私的用户

- 不想把策略上传云端 → **本地优先**，运行时状态在 `data/`（默认不上传 Git）  
- 需要审计轨迹 → 订单 JSONL、学习账本、验收报告  

---

## 核心产品能力

### 1. 智能选股引擎

- **预设策略**：均衡 / 动量 / 趋势 / 低波动  
- **模式**：收盘 EOD（约 1 秒）· 实时智能（需先刷新行情）  
- **筛选**：最小成交额、偏好/排除板块、**最低价/最高价**、按资金自动限价  
- **输出**：排名、中文名称、Sparkline、收益区间、下行风险、一手建议、Alpha158-lite 分  
- **指南**：每次运行附带「增强版选股指南」步骤与术语表  

### 2. 模拟与晋级链

```
研究 (RESEARCH_ONLY)
    ↓
Paper 模拟 (PAPER_TRADING)     ← T+1、费用、仓位、Kill Switch
    ↓
Shadow 影子 (SHADOW_LIVE)      ← 零真实订单
    ↓
订单票据 + 券商 handoff        ← 人工在官方 App 确认
```

### 3. 券商与执行

| 路径 | 说明 |
|------|------|
| 浏览器打开官方交易页 | 东方财富、华泰涨乐等（默认推荐） |
| CSV / QMT 文件投递 | 进阶用户，本地 MiniQMT |
| Sidecar 远程 | Mac 隧道场景（见 `docs/MAC_BROKER_EXECUTION.md`） |

**原则：** 系统可预填、可导出，**不可**代替你在券商端点击「确认买入」。

### 4. 风控与门控

- 资金上限、单票上限、最大回撤预算  
- Kill Switch 紧急停机  
- 实盘门控：`real_money_enabled`、`user_confirmed_risk`、`legal_review_passed`  
- `unattended_auto_enabled` 默认 **false**

### 5. 研究与报告

- 量化日报（Markdown / PDF）  
- 模型实验室、过拟合检测（DSR / PBO）  
- 多智能体研究工作流（政策、板块、个股）  

---

## 典型使用场景

| 场景 | 推荐路径 |
|------|----------|
| 周末研究下周标的 | 更新数据 → EOD 选股 → 阅读榜首解读 → 加入自选 |
| 用小资金练手 | 设 ¥5,000 + 最高价 ¥50 → Paper 跟踪 1 周 |
| 模拟满意后辅助下单 | 启用实盘门控 → 连接券商 → 选股页点「实盘」→ App 确认 |
| 每日盘前决策 | `make daily-report` 或门户「量化日报」 |
| 开发者验收 | `scripts/run_autonomous_remediation_acceptance.py` |

---

## 部署与就绪状态

| 级别 | 含义 | 当前典型状态 |
|------|------|----------------|
| `PRODUCTION_READY_FOR_PAPER` | 可日常 Paper | ✅ 工程测试通过 |
| `PRODUCTION_READY_FOR_MANUAL_LIVE` | 可辅助实盘（人工确认） | ⚠️ 需经济验证达标 |
| `PARTIALLY_READY` | 可用但有限制 | 见验收报告 |
| 无人值守自动实盘 | — | ❌ **不支持 / 禁止** |

详见 [acceptance/FINAL_ACCEPTANCE_REPORT.md](acceptance/FINAL_ACCEPTANCE_REPORT.md)。

---

## 与竞品差异（摘要）

完整对比见 [COMPARISON.md](COMPARISON.md)。

- **vs 聚宽/米筐**：本地、透明、不绑定云策略托管  
- **vs vn.py 裸框架**：自带 A 股门户、选股、Paper、新手 UX  
- **vs 券商 App**：多因子排序 + 学习账本 + 可审计票据，非替代交易终端  

---

## 系统要求

| 项目 | 最低 | 推荐 |
|------|------|------|
| OS | macOS 12+ / Ubuntu 20.04+ | macOS / Linux 本机 |
| Python | 3.9 | 3.9–3.11 |
| 磁盘 | 2 GB（含 DuckDB） | 10 GB+（长历史） |
| 网络 | 拉取行情与 Tushare | 稳定宽带 |

---

## 获取与升级

```bash
git clone https://github.com/kenzhao0621-tech/netlify-demo.git
cd netlify-demo
make bootstrap && make app
```

升级：`git pull` → `make bootstrap` → `make portal-stop && make app`

---

## 支持与反馈

- 📖 [用户指南](USER_GUIDE.md)  
- 🐛 [GitHub Issues](https://github.com/kenzhao0621-tech/netlify-demo/issues)  
- 🔧 [贡献指南](../CONTRIBUTING.md)  

---

*QuantOS CN — 让 A 股量化研究可落地、可解释、可审计。*
