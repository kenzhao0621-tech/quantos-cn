"""Stock dossier generator — Chinese analysis archive."""

from __future__ import annotations

from tools.china_quant.models import StockRecord
from tools.china_quant.risk import TradeLevels
from tools.china_quant.scoring_v2 import FactorScore


def render_dossier(
    stock: StockRecord,
    score: FactorScore,
    levels: TradeLevels,
    *,
    rank: int,
    regime: str,
    sector_stage: str,
    policy_summary: str,
    institutional_summary: str,
    data_freshness: str,
    final_status: str = "ACTIONABLE_PAPER_TRADE",
) -> str:
    bull_p, base_p, bear_p = 35, 45, 20
    return f"""# 个股量化分析档案

## 1. 基本信息

- 股票名称：{stock.name}
- 股票代码：{stock.code}
- 交易所：{stock.exchange}
- 板块：{stock.board}
- 行业/板块：{stock.sector}
- ST状态：{"是" if stock.is_st else "否"}
- 数据新鲜度：{data_freshness}

## 2. 一句话结论

在{regime}环境下，{stock.name}为概率加权研究标的（非确定性预测），综合评分{score.total:.0f}/100，排名第{rank}。

## 3. 综合评分

- 总分：{score.total:.0f}
- 市场状态适配：{score.regime_fit:.0f}/10
- 板块轮动：{score.sector_rotation:.0f}/15
- 趋势：{score.trend_momentum:.0f}/15
- 价量：{score.price_volume:.0f}/10
- 流动性：{score.liquidity:.0f}/10
- 基本面：{score.fundamentals:.0f}/15
- 估值：{score.valuation:.0f}/10
- 政策催化：{score.policy_catalyst:.0f}/5
- 机构证据：{score.institutional:.0f}/5
- 风控：{score.risk_control:.0f}/5
- 扣分：{score.deductions:.0f}
- 备注：{"；".join(score.notes) or "无"}

## 4. 大盘与板块背景

- 市场状态：{regime}
- 板块阶段：{sector_stage}
- 政策摘要：{policy_summary}

## 5. 价格与趋势结构

- 最新价（样本）：{stock.price}
- 涨跌幅：{stock.change_pct:+.2f}%
- 相对强度评分：{stock.trend_score:.0f}/15

## 6. 基本面

- 基本面评分：{stock.fundamental_score:.0f}/15（样本/fixture）

## 7. 估值

- 估值评分：{stock.valuation_score:.0f}/10

## 8. 政策与事件

- {stock.official_catalyst or "无已确认公告（样本）"}

## 9. 机构动向

- {institutional_summary or "无公开披露信号（样本）"}

## 10. 交易计划

- 理想买入区间：{levels.entry_low:.2f}–{levels.entry_high:.2f}
- 买入确认：{levels.entry_confirm}
- 取消条件：{levels.cancel_condition}
- 止损：{levels.stop_price:.2f}（-{levels.stop_pct:.0f}%）
- 第一止盈：{levels.target1:.2f}
- 第二止盈：{levels.target2:.2f}
- 盈亏比：{levels.reward_risk}
- 建议仓位：{levels.position_pct}

## 11. 情景分析

### 乐观（约{bull_p}%）
- 条件：板块延续、放量突破
- 路径：目标一→目标二

### 基准（约{base_p}%）
- 条件：震荡上行
- 路径：触及第一止盈后部分减仓

### 悲观（约{bear_p}%）
- 条件：跌破止损或板块转弱
- 路径：止损退出

## 12. 风险清单

- 市场风险、板块轮动、流动性、执行（涨跌停/T+1）、数据与模型风险

## 13. 什么情况说明判断错误

- 收盘有效跌破止损 {levels.stop_price:.2f}
- 板块逻辑失效
- 出现未priced-in的负面公告

## 14. Sources

- 数据来源：fixture/样本（非实时）
- 限制：仅供纸面交易研究

## 15. Final status

**{final_status}**
"""
