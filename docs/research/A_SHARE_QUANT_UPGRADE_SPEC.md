# A-Share Quantitative Intelligence Platform  
# Autonomous Research, Algorithm Upgrade, Validation, and Production Implementation Specification

**Specification type:** Research-to-production engineering mandate  
**Primary market:** Mainland China A-shares  
**Target systems:** Intelligent stock screening, portfolio construction, backtesting, paper trading, simulated brokerage, and controlled live trading  
**Execution model:** Autonomous, evidence-driven, test-gated, auditable  
**Language for implementation artifacts:** English, with optional Chinese user-facing explanations  
**Primary objective:** Materially improve the platform’s real-world quantitative analysis, recommendation reliability, execution realism, risk control, and adaptability to changing market conditions

---

# 1. Mission

Upgrade the existing A-share quantitative trading platform through a complete research-to-production process.

The task is not complete when papers have been collected, summarized, or cited.

The task is complete only when:

1. Current high-quality research has been independently discovered and read;
2. The assumptions, limitations, evidence quality, and reproducibility of each relevant method have been evaluated;
3. Candidate methods have been mapped to specific platform deficiencies;
4. Selected methods have been implemented in working code;
5. Every implementation has passed leakage-safe out-of-sample evaluation;
6. Results have been compared against existing production baselines;
7. Only methods producing stable, economically meaningful, net-of-cost improvements have been retained;
8. Stock recommendations, paper trading, and brokerage execution visibly use the upgraded capabilities;
9. The platform provides transparent evidence explaining what improved, what failed, and what remains uncertain;
10. A final implementation and validation report is returned to the owner.

Do not treat publication novelty as proof of usefulness.

Do not assume that a newer, deeper, larger, agentic, generative, graph-based, reinforcement-learning, or LLM-based model is superior to a simpler baseline.

The target is not maximum architectural complexity.

The target is:

- stronger predictive discipline;
- lower data leakage risk;
- better downside control;
- more realistic execution;
- better-calibrated recommendations;
- better adaptation to A-share market regimes;
- improved reliability after transaction costs;
- transparent uncertainty;
- operational safety in paper and live trading.

---

# 2. Non-Negotiable Execution Rule

This task is an implementation mandate, not a consulting memo.

You must:

- inspect the current repository;
- inspect the current data pipeline;
- inspect the current factor definitions;
- inspect the current labels;
- inspect the current backtesting engine;
- inspect the current recommendation logic;
- inspect Paper and live trading routes;
- search and read real research sources;
- produce a structured research registry;
- identify suitable methods;
- implement selected improvements;
- run experiments;
- run automated tests;
- run application-level verification;
- provide final evidence.

You must not stop after:

- listing papers;
- producing summaries;
- recommending possible algorithms;
- generating pseudocode;
- writing TODO files;
- creating unused interfaces;
- adding UI labels without backend enforcement;
- returning mock results;
- adding placeholder validation fields;
- claiming improvement from in-sample metrics.

If external data, credentials, broker permissions, proprietary datasets, or unavailable infrastructure block part of the implementation, complete every unblocked portion and return an explicit blocker report containing:

- exact missing dependency;
- why it is necessary;
- affected modules;
- safe temporary fallback;
- commands or steps required from the owner;
- whether the fallback is suitable for research, Paper, simulated brokerage, or live trading.

---

# 3. Safety and Capital Boundary

The system may improve live-trading readiness, but it must not silently activate unrestricted real-money execution.

During this task:

- keep unattended real-money execution disabled;
- keep manual confirmation enabled for every live order;
- do not store broker passwords, trading passwords, SMS codes, or verification codes;
- do not expose account identifiers in logs;
- do not place live orders while testing;
- use dry-run, Paper, or simulated brokerage environments;
- preserve existing capital limits;
- preserve or strengthen loss limits;
- preserve order idempotency;
- preserve emergency kill-switch behavior.

A research result may become eligible for controlled live trading only after completing every required promotion stage.

Required lifecycle:

```text
research
→ offline experiment
→ leakage audit
→ out-of-sample validation
→ shadow mode
→ Paper trading
→ simulated broker
→ manually confirmed limited live trading
```

No model, feature, portfolio rule, or execution strategy may skip stages.

---

# 4. Phase 0 — Repository and System Audit

Before changing algorithms, inspect the current implementation.

Create a baseline audit covering:

## 4.1 Data

Identify:

- market-data providers;
- daily, minute, tick, MBP, and MBO availability;
- corporate-action handling;
- adjustment methodology;
- financial-statement sources;
- actual publication timestamps;
- announcement sources;
- news sources;
- index constituent history;
- industry-classification history;
- delisted securities;
- suspended securities;
- ST and delisting-risk states;
- price-limit states;
- missing-value behavior;
- stale data behavior;
- timezone and trading-calendar handling;
- reproducibility and dataset versioning.

## 4.2 Labels

Identify every predictive target, including:

- future return;
- excess return;
- cross-sectional rank;
- classification labels;
- drawdown targets;
- volatility targets;
- stop-loss outcomes;
- crash-risk targets;
- holding period;
- execution assumptions.

For each label, document:

```yaml
name:
formula:
signal_timestamp:
entry_timestamp:
exit_timestamp:
holding_period:
benchmark:
corporate_action_handling:
price_limit_handling:
suspension_handling:
transaction_cost_handling:
known_leakage_risks:
```

## 4.3 Features and Factors

For each existing factor, identify:

- formula;
- lookback;
- lag;
- source fields;
- availability timestamp;
- winsorization;
- standardization;
- industry neutralization;
- size neutralization;
- missing values;
- expected direction;
- actual out-of-sample IC;
- turnover;
- capacity;
- correlation with other factors.

## 4.4 Models

Identify:

- currently active production model;
- inactive models;
- baselines;
- hyperparameter search;
- training windows;
- retraining schedule;
- feature selection;
- ensemble logic;
- random seed handling;
- model registry;
- artifact versioning;
- fallback behavior;
- explanation method;
- uncertainty estimation.

## 4.5 Backtesting

Audit:

- random versus time-aware splits;
- future leakage;
- survivorship bias;
- delisting handling;
- announcement-time alignment;
- universe construction;
- transaction costs;
- commission minimums;
- stamp duty;
- transfer fees;
- slippage;
- price impact;
- T+1;
- board-lot requirements;
- suspensions;
- one-price limit-up and limit-down days;
- order fill assumptions;
- rejected orders;
- partial fills;
- stale quotes;
- cash availability;
- portfolio rebalance timing.

## 4.6 Trading

Audit:

- Paper order lifecycle;
- MiniQMT/XtQuant bridge;
- order acknowledgement;
- order status reconciliation;
- position reconciliation;
- cash reconciliation;
- duplicate-order protection;
- retry behavior;
- timeout behavior;
- crash recovery;
- manual confirmation;
- broker session validation;
- pre-trade risk checks;
- post-trade monitoring;
- emergency stop.

Create:

```text
docs/research/00_CURRENT_SYSTEM_AUDIT.md
docs/research/00_CURRENT_ALGORITHM_MAP.md
docs/research/00_BASELINE_LIMITATIONS.md
artifacts/baseline_system_manifest.json
```

Do not begin model replacement until this audit is complete.

---

# 5. Phase 1 — Autonomous Research Discovery

Search for the newest and most relevant research available on the execution date.

Do not rely on a fixed paper list.

Search across:

- peer-reviewed finance journals;
- econometrics journals;
- machine-learning conferences;
- financial engineering journals;
- SSRN;
- NBER;
- arXiv;
- university repositories;
- official institutional research;
- recognized quantitative-finance research groups;
- official exchange publications;
- official China Securities Regulatory Commission materials;
- official Shanghai, Shenzhen, and Beijing Stock Exchange materials;
- official broker and XtQuant documentation;
- primary-source code repositories linked by authors.

Prefer primary sources.

Blogs, forum posts, videos, Reddit, Zhihu, Bilibili, and developer discussions may be used only to:

- discover implementation problems;
- understand operational experience;
- locate source material;
- identify reproducibility issues.

They must not be treated as primary scientific evidence.

---

# 6. Research Search Taxonomy

Use combinations of the following optimized search terms.

The list is a search framework, not a predetermined reading list.

## 6.1 China A-Share Asset Pricing

```text
China A-share cross-sectional return prediction
Chinese stock market asset pricing machine learning
China equity return predictability
China A-share factor investing
China stock market anomalies out-of-sample
Chinese equity market microstructure
retail investor behavior China stock returns
A-share liquidity premium
A-share turnover anomaly
A-share short-term reversal
A-share momentum crash
A-share quality factor
A-share profitability factor
A-share investor attention
China stock crash risk
```

## 6.2 Machine Learning for Stock Selection

```text
machine learning cross-sectional stock returns
learning to rank stock selection
ranking loss asset pricing
cost-aware machine learning portfolio
uncertainty-aware stock prediction
probabilistic stock return forecasting
calibrated stock return probabilities
ensemble learning factor investing
dynamic model weighting information coefficient
online learning non-stationary financial markets
concept drift stock return prediction
regime adaptive stock selection
distribution shift asset pricing
domain adaptation Chinese stock market
```

## 6.3 Robust Validation and Overfitting

```text
financial machine learning data leakage
look-ahead bias stock backtesting
purged k-fold cross-validation finance
combinatorial purged cross-validation
embargo time series cross-validation
walk-forward validation stock selection
probability of backtest overfitting
deflated Sharpe ratio
multiple testing factor discovery
false discovery rate asset pricing
factor zoo replication
financial model selection bias
selection adjusted performance finance
reality check trading strategy
superior predictive ability test
```

## 6.4 Point-in-Time and Data Quality

```text
point-in-time financial data stock prediction
financial statement publication lag China
corporate announcement timestamp China A-share
survivorship bias Chinese stock market
delisting bias stock backtest
historical index constituents China
historical industry classification China A-share
corporate action adjustment backtesting
stale price bias stock returns
price limit contaminated returns
suspension handling A-share backtest
```

## 6.5 Transaction Costs and Implementability

```text
net of transaction cost machine learning portfolio
implementable efficient frontier machine learning
turnover constrained stock selection
liquidity constrained portfolio optimization
market impact Chinese stock market
A-share transaction cost model
commission minimum A-share backtest
stamp duty quantitative strategy China
capacity constrained factor investing
small account portfolio optimization
board lot constrained portfolio
integer portfolio optimization stocks
```

## 6.6 A-Share Market Rules

```text
T+1 constraint China stock strategy
price limit effect Chinese stock market
limit-up limit-down execution China
one-price limit board trading
call auction China A-share
opening auction price discovery China
stock suspension China return prediction
ST stock risk prediction
ChiNext trading mechanism
STAR Market price limits
Beijing Stock Exchange trading mechanism
A-share 100 share lot constraint
```

## 6.7 Risk Forecasting

```text
machine learning stock crash risk China
downside risk prediction stock selection
expected drawdown prediction
tail risk machine learning portfolio
CVaR stock selection
volatility forecasting machine learning
realized volatility Chinese stocks
jump risk stock prediction
liquidity crisis prediction
risk sensitive portfolio construction
drawdown constrained portfolio optimization
```

## 6.8 Market Microstructure and Execution

```text
China A-share Level-2 order book prediction
order flow imbalance China stocks
limit order book Chinese stock market
MBP MBO market microstructure
microprice stock execution
queue position prediction limit order book
optimal execution China equities
market impact model A-share
slippage estimation order execution
execution shortfall prediction
smart order routing stock trading
adverse selection order flow
```

## 6.9 Text, Events, and Multimodal Data

```text
Chinese stock announcement NLP
A-share news sentiment stock returns
financial text point-in-time alignment
corporate announcement event study China
analyst report text China stocks
multimodal stock prediction China
financial large language model stock analysis
LLM stock selection leakage
LLM trading benchmark China A-share
event-driven quantitative trading China
risk disclosure text classification
financial fraud detection China listed companies
```

## 6.10 Reinforcement Learning and Agents

```text
safe reinforcement learning portfolio management
offline reinforcement learning trading
risk constrained reinforcement learning finance
constrained Markov decision process portfolio
reinforcement learning optimal execution
distributional reinforcement learning trading
agentic quantitative research factor discovery
LLM trading agent leakage benchmark
autonomous factor mining reproducibility
multi-agent portfolio management
```

## 6.11 Production Trading Systems

```text
algorithmic trading order lifecycle
pre-trade risk controls
idempotent order submission
duplicate order prevention trading
broker reconciliation architecture
event sourced trading system
fault tolerant order management system
kill switch automated trading
paper live trading environment isolation
broker API disconnect recovery
order state machine partial fill
automated trading audit logging
```

---

# 7. Search Recency Strategy

Research must include:

- foundational methods still considered relevant;
- peer-reviewed work from recent years;
- the latest work from the current and previous two calendar years;
- recent preprints with potentially useful methods;
- recent replication or critical studies;
- recent official market-rule and broker-interface documentation.

Use recency filters, but do not discard older foundational evidence solely because of age.

For each topic:

1. Find foundational work;
2. Find recent extensions;
3. Find replication studies;
4. Find negative findings;
5. Find implementation studies;
6. Find China-market-specific evidence;
7. Find evidence discussing transaction costs;
8. Find evidence discussing failure modes.

Search using both English and Chinese.

Record the exact query, source, access date, and selection reason.

---

# 8. Mandatory Full-Text Reading Standard

A paper is not considered “read” if only its title, abstract, search snippet, or third-party summary was accessed.

For every shortlisted source, inspect as much of the primary text as available, including:

- research question;
- dataset;
- sample period;
- security universe;
- target;
- feature construction;
- validation method;
- benchmark;
- transaction-cost assumptions;
- portfolio construction;
- statistical tests;
- limitations;
- appendices;
- robustness checks;
- source code;
- data availability.

For PDF papers, extract and inspect relevant tables, charts, formulas, experimental settings, appendices, and limitations.

Do not claim to have read inaccessible content.

Mark access level explicitly:

```yaml
access_level:
  - full_text
  - partial_text
  - abstract_only
  - metadata_only
```

Only `full_text` and sufficiently detailed `partial_text` sources may directly justify production algorithm changes.

---

# 9. Research Evidence Registry

Create a machine-readable registry.

Required fields:

```yaml
paper_id:
title:
authors:
year:
venue:
publication_status:
peer_reviewed:
source_url:
access_date:
access_level:
research_topic:
market:
sample_start:
sample_end:
data_frequency:
universe:
survivorship_handling:
point_in_time_handling:
target_definition:
holding_period:
feature_groups:
model_classes:
validation_design:
purge_used:
embargo_used:
walk_forward_used:
transaction_costs:
slippage:
market_impact:
portfolio_constraints:
reported_metrics:
main_findings:
negative_findings:
limitations_stated_by_authors:
limitations_identified_by_us:
reproducibility:
code_available:
data_available:
a_share_relevance:
production_relevance:
risk_of_leakage:
risk_of_overfitting:
implementation_complexity:
expected_platform_benefit:
recommended_action:
```

Allowed `recommended_action` values:

```text
adopt
adapt_and_test
research_only
reject
insufficient_evidence
blocked_by_data
```

Create:

```text
docs/research/01_SEARCH_LOG.md
docs/research/02_RESEARCH_EVIDENCE_MATRIX.md
docs/research/03_RESEARCH_LIMITATIONS.md
docs/research/04_REJECTED_METHODS.md
artifacts/research_registry.json
artifacts/research_search_log.json
```

---

# 10. Evidence Quality Scoring

Score every candidate method.

Suggested dimensions:

```text
Peer-review quality                  0–5
China A-share relevance             0–5
Point-in-time correctness           0–5
Out-of-sample quality               0–5
Transaction-cost realism            0–5
Market-rule realism                 0–5
Reproducibility                     0–5
Sample breadth                      0–5
Statistical rigor                   0–5
Operational implementability        0–5
```

Apply penalties for:

```text
Abstract-only access                −3
No out-of-sample test               −5
Random K-Fold on market time series −5
No transaction cost                −3
Current-universe survivorship bias  −5
Unclear feature timestamps          −5
No benchmark comparison             −2
Tiny sample                         −3
Single-regime sample                −3
No code and weak methodology        −2
Only preprint status                −1 to −3
Unrealistic fill assumptions        −4
```

Do not automatically adopt the highest-scoring method.

The score is an evidence filter, not a decision substitute.

---

# 11. Problem-to-Research Mapping

After the audit, map actual platform weaknesses to research topics.

Example structure:

```yaml
platform_problem:
current_behavior:
user_impact:
quantitative_risk:
relevant_research_topics:
candidate_methods:
required_data:
implementation_modules:
success_metric:
rejection_metric:
```

Possible platform problems include:

- unstable recommendations;
- excessive stock turnover;
- highly correlated factors;
- recommendation overconfidence;
- poor bear-market performance;
- excessive small-cap exposure;
- sensitivity to limit-up stocks;
- lack of point-in-time fundamentals;
- factor decay;
- poor transaction-cost realism;
- inaccurate stop-loss logic;
- inability to estimate downside risk;
- poor calibration;
- strategy crowding;
- portfolio concentration;
- duplicate broker orders;
- poor fill assumptions;
- Paper/live behavioral mismatch;
- stale recommendation explanations.

Do not introduce a method without a clearly identified problem.

---

# 12. Target Quantitative Architecture

The upgraded platform should use a modular architecture.

```text
Data Ingestion
    ↓
Point-in-Time Data Store
    ↓
Tradability and Market-State Masks
    ↓
Feature and Factor Registry
    ↓
Label Factory
    ↓
Baseline Models
    ↓
Candidate Models
    ↓
Return / Rank / Risk / Uncertainty Forecasts
    ↓
Cost-Aware Portfolio Constructor
    ↓
Execution Feasibility Engine
    ↓
Backtest / Shadow / Paper / Simulated Broker
    ↓
Controlled Live Trading
    ↓
Monitoring, Drift Detection, and Model Governance
```

No UI component may fabricate results that are not produced by this backend pipeline.

---

# 13. Point-in-Time Data Upgrade

Build or strengthen a point-in-time data layer.

For every record, preserve:

```text
event_time
publication_time
market_available_time
ingestion_time
effective_time
revision_time
source
data_version
```

A feature is eligible at timestamp `t` only when its source data was publicly and operationally available before the signal cutoff.

Financial statements must be aligned to:

- actual announcement time;
- correction time;
- restatement time;
- trading-session availability.

Do not align financial data solely to quarter-end or fiscal-period end.

Maintain historical state for:

- listing status;
- delisting status;
- ST status;
- suspension;
- board;
- trading rules;
- price limits;
- industry;
- index membership;
- share count;
- corporate actions.

Add automated leakage tests that intentionally attempt to retrieve future information and verify that access is rejected.

---

# 14. Tradability-First Masking

Before factor computation, ranking, portfolio construction, or order generation, generate a tradability mask.

The mask should account for:

- not yet listed;
- delisted;
- suspended;
- ST or delisting-risk restrictions;
- one-price limit-up;
- one-price limit-down;
- missing or stale prices;
- insufficient liquidity;
- insufficient listing history;
- corporate-action anomalies;
- invalid price;
- invalid volume;
- unavailable board-lot purchase;
- account-level restrictions;
- T+1 sell restrictions.

Distinguish:

```text
valid_for_research
valid_for_factor_computation
valid_for_ranking
valid_for_purchase
valid_for_sale
valid_for_rebalance
```

Do not treat a non-tradable observed closing price as a realistically executable price.

---

# 15. Factor Research Upgrade

Create a formal factor registry.

Required factor families:

- valuation;
- profitability;
- earnings quality;
- balance-sheet quality;
- growth;
- medium-term momentum;
- short-term reversal;
- volatility;
- downside volatility;
- liquidity;
- turnover;
- abnormal turnover;
- volume-price divergence;
- price-limit behavior;
- crowding;
- investor attention;
- analyst information;
- announcement events;
- crash risk;
- industry strength;
- market beta;
- residual momentum;
- market microstructure;
- execution feasibility.

For every factor record:

```yaml
factor_id:
name:
economic_rationale:
formula:
source_fields:
lookback:
lag:
availability_rule:
missing_value_policy:
winsorization:
standardization:
neutralization:
expected_direction:
eligible_universe:
frequency:
decay_profile:
correlation_cluster:
estimated_capacity:
known_failure_modes:
```

Evaluate:

- IC;
- Rank IC;
- ICIR;
- Newey-West-adjusted significance where appropriate;
- monotonicity;
- quantile spread;
- turnover;
- factor decay;
- cross-regime stability;
- industry stability;
- size-bucket stability;
- liquidity-bucket stability;
- cost-adjusted spread;
- sensitivity to microcaps;
- sensitivity to outliers.

Reject factors whose apparent value disappears after:

- lagging correctly;
- removing microcaps;
- adding transaction costs;
- historical-universe reconstruction;
- multiple-testing adjustment;
- market-state segmentation.

---

# 16. Feature Selection and Factor Redundancy

Do not retain hundreds of correlated factors because they appear predictive in isolation.

Implement:

- correlation clustering;
- hierarchical factor grouping;
- variance inflation monitoring;
- mutual-information analysis;
- stability selection;
- permutation importance;
- conditional importance;
- SHAP only as supplementary explanation;
- feature ablation;
- regime-specific importance analysis;
- factor decay analysis.

Do not use a feature solely because a tree model reports high importance.

A production feature must demonstrate:

- point-in-time validity;
- economic rationale or robust empirical evidence;
- stable out-of-sample contribution;
- non-redundant incremental value;
- manageable turnover;
- acceptable operational cost.

---

# 17. Prediction Targets

Do not rely on a single binary “up/down” target.

Build a multi-target forecasting system.

Candidate targets:

```text
future_excess_return
cross_sectional_return_rank
benchmark_outperformance_probability
downside_probability
expected_maximum_adverse_excursion
expected_drawdown
future_realized_volatility
crash_probability
limit_up_probability
limit_down_probability
liquidity_cost
fill_probability
prediction_uncertainty
```

Targets must reflect actual intended holding periods.

Use separate models when necessary.

Do not force one model to simultaneously estimate return, risk, liquidity, and crash probability unless evidence demonstrates superior and stable performance.

---

# 18. Baseline-First Model Framework

Before adding complex models, establish strong baselines:

- historical mean;
- factor-weighted score;
- linear regression;
- Ridge;
- Lasso;
- Elastic Net;
- logistic regression;
- simple cross-sectional rank model;
- shallow tree ensemble;
- buy-and-hold benchmark;
- index benchmark;
- equal-weight benchmark.

Candidate models may include:

- gradient boosting;
- random forests;
- calibrated classifiers;
- ranking models;
- generalized additive models;
- shallow neural networks;
- temporal models;
- online-learning models;
- regime-conditioned models;
- probabilistic models;
- graph models;
- multimodal models;
- constrained reinforcement learning.

Complex models must beat strong baselines after:

- costs;
- multiple-testing correction;
- market-rule simulation;
- out-of-sample testing;
- regime segmentation.

---

# 19. Ranking-Oriented Stock Selection

Because the application recommends a small subset from a large stock universe, test direct ranking objectives.

Compare:

```text
absolute return regression
binary classification
pairwise ranking
listwise ranking
quantile ranking
benchmark-outperformance ranking
risk-adjusted ranking
```

Ranking metrics may include:

- Rank IC;
- NDCG;
- Precision@K;
- top-decile spread;
- top-K net return;
- top-K drawdown;
- top-K turnover;
- ranking stability;
- industry concentration;
- liquidity concentration.

Do not select ranking models using NDCG alone.

The production objective must include economic value and execution realism.

---

# 20. Return, Risk, and Uncertainty Separation

Create separate prediction channels:

```text
alpha_score
expected_return
downside_risk
crash_risk
expected_volatility
liquidity_cost
execution_risk
model_uncertainty
```

A stock with high predicted return must not automatically rank highly when:

- crash risk is high;
- liquidity is inadequate;
- uncertainty is high;
- the stock is excessively crowded;
- expected costs consume the alpha;
- the stock is non-tradable;
- the required board lot exceeds capital constraints.

The final score should be configurable but auditable.

Example conceptual form:

```text
final_score
=
return_component
+ ranking_component
+ quality_component
− downside_risk_penalty
− crash_risk_penalty
− uncertainty_penalty
− liquidity_cost_penalty
− turnover_penalty
− overheat_penalty
− concentration_penalty
```

Do not hard-code arbitrary coefficients without validation.

Estimate or tune weights only within training/validation windows.

---

# 21. Probability Calibration and Uncertainty

Any probability displayed to the user must be calibrated.

Evaluate:

- Brier score;
- calibration error;
- reliability diagrams;
- log loss;
- calibration by regime;
- calibration by confidence bucket;
- calibration by market-cap bucket.

Candidate calibration methods:

- Platt scaling;
- isotonic regression;
- beta calibration;
- conformal prediction;
- quantile prediction;
- ensemble dispersion;
- bootstrap uncertainty.

Do not display “70% probability of rising” unless historical out-of-sample calibration supports that interpretation.

Where uncertainty is high, the system should:

- lower recommendation strength;
- lower maximum position;
- widen forecast intervals;
- require additional confirmation;
- avoid automated order generation.

---

# 22. Regime Awareness and Concept Drift

Markets are non-stationary.

Build a market-regime and model-drift layer.

Possible regime inputs:

- index trend;
- breadth;
- realized volatility;
- downside volatility;
- cross-sectional dispersion;
- turnover;
- liquidity;
- credit conditions;
- rates;
- northbound flow where available;
- valuation dispersion;
- limit-up/limit-down breadth;
- sector concentration.

Do not assume a single regime-clustering method is correct.

Compare:

- transparent rule-based states;
- Hidden Markov Models;
- change-point detection;
- clustering;
- volatility-state models;
- online drift detectors.

Regime labels must be learned without future data.

Track:

- feature drift;
- label drift;
- prediction drift;
- calibration drift;
- residual drift;
- factor IC drift;
- cost drift;
- fill-rate drift.

Drift detection must not trigger automatic unreviewed live-model replacement.

It may trigger:

- reduced confidence;
- reduced exposure;
- retraining;
- fallback to baseline;
- Paper-only mode;
- live-trading suspension.

---

# 23. Cost-Aware Learning and Portfolio Construction

Evaluate models on net implementable performance.

Build a transaction-cost model including:

- broker commission;
- minimum commission;
- stamp duty;
- transfer fee;
- bid-ask spread proxy;
- slippage;
- participation rate;
- market impact;
- limit-board execution;
- delay cost;
- order rejection;
- partial fill.

Support separate cost profiles for:

- historical research;
- Paper simulation;
- simulated brokerage;
- live account configuration.

Use conservative assumptions when exact data is unavailable.

Do not report gross strategy returns as the principal result.

Report:

```text
gross return
explicit fees
estimated spread cost
estimated slippage
estimated market impact
net return
turnover
capacity estimate
```

Test turnover-aware objectives and portfolio constraints.

---

# 24. Small-Capital Portfolio Optimization

The current platform must support a capital base around RMB 5,000.

Portfolio construction must consider:

- 100-share buy lot;
- available cash;
- expected fees;
- commission minimum;
- maximum number of holdings;
- per-position capital limit;
- per-trade risk limit;
- daily loss limit;
- portfolio drawdown limit;
- sector concentration;
- liquidity;
- T+1;
- inability to buy unaffordable board lots.

Implement integer-constrained allocation.

A recommendation is not executable if:

```text
price × 100 shares + estimated fees > available capital
```

The recommendation UI must not propose an impossible portfolio.

Compare portfolio approaches:

- equal weight;
- score weight;
- volatility scaling;
- risk budgeting;
- constrained mean-variance;
- CVaR optimization;
- integer optimization;
- robust optimization.

Use the simplest method that produces stable net improvement.

---

# 25. Backtesting and Validation Framework

The validation framework must prevent accidental or deliberate leakage.

Required methods:

- anchored expanding Walk-Forward;
- rolling Walk-Forward;
- Purged K-Fold;
- embargo;
- Combinatorial Purged Cross-Validation where computationally feasible;
- untouched final holdout;
- market-regime stress tests;
- transaction-cost stress tests;
- parameter perturbation tests;
- feature perturbation tests;
- universe perturbation tests.

Purge and embargo periods must derive from:

- label horizon;
- feature lookback overlap;
- holding period;
- event overlap.

Do not randomly assign adjacent financial observations to training and test folds.

Maintain separate periods for:

```text
training
validation
model selection
final untouched evaluation
```

After final holdout inspection, do not continue tuning against it.

If additional tuning is required, create a new future evaluation period rather than contaminating the old holdout.

---

# 26. Multiple Testing and Research Governance

Every experiment must be registered.

Record:

- hypothesis;
- rationale;
- code version;
- data version;
- features;
- hyperparameters;
- search space;
- evaluation periods;
- number of trials;
- result;
- decision.

Calculate where applicable:

- Probability of Backtest Overfitting;
- Deflated Sharpe Ratio;
- Probabilistic Sharpe Ratio;
- multiple-testing-adjusted significance;
- bootstrap confidence intervals;
- benchmark-relative performance.

Do not hide unsuccessful experiments.

Maintain:

```text
artifacts/experiment_registry.json
docs/research/FAILED_EXPERIMENTS.md
```

The best-looking result from a large search is not sufficient evidence.

---

# 27. Required Evaluation Metrics

For stock selection:

- Rank IC;
- ICIR;
- Precision@K;
- top-bottom spread;
- top-K net return;
- ranking stability;
- turnover;
- sector exposure;
- size exposure;
- liquidity exposure.

For portfolio performance:

- annualized net return;
- volatility;
- Sharpe;
- Deflated Sharpe;
- Sortino;
- Calmar;
- maximum drawdown;
- expected shortfall;
- downside deviation;
- win rate;
- profit factor;
- average holding period;
- turnover;
- total costs;
- worst month;
- worst quarter;
- worst market regime;
- longest drawdown duration.

For prediction:

- out-of-sample R² where appropriate;
- MAE;
- rank correlation;
- Brier score;
- log loss;
- calibration error;
- interval coverage;
- uncertainty quality.

For execution:

- order acceptance;
- rejection rate;
- fill rate;
- partial-fill rate;
- slippage;
- implementation shortfall;
- time to acknowledgement;
- reconciliation mismatch;
- duplicate-order count;
- disconnect recovery rate.

Never promote a model based on accuracy alone.

---

# 28. Ablation and Incremental Value

For each selected method, run controlled ablations.

Minimum comparison:

```text
Current production baseline
Baseline + data correction
Baseline + new factor group
Baseline + new model
Baseline + uncertainty model
Baseline + risk model
Baseline + cost-aware portfolio
Baseline + regime layer
Full candidate system
```

The result must identify which component produces value.

Reject improvements that only work when bundled with many untested changes.

---

# 29. Robustness Tests

Run:

- alternative date ranges;
- bull markets;
- bear markets;
- sideways markets;
- high-volatility periods;
- low-liquidity periods;
- different index universes;
- full-universe tests;
- large-cap-only;
- small-cap-excluded;
- ST-excluded;
- recent-listing-excluded;
- stricter transaction costs;
- delayed execution;
- worse slippage;
- reduced fill rates;
- factor lag changes;
- feature noise;
- hyperparameter perturbation;
- alternative rebalancing frequencies.

A strategy that fails under modestly worse assumptions must not be described as reliable.

---

# 30. Text, News, and LLM Governance

LLMs may assist with:

- paper discovery;
- structured research extraction;
- factor hypothesis generation;
- announcement classification;
- risk-event extraction;
- recommendation explanation;
- report generation;
- anomaly triage.

LLMs must not directly:

- place live trades;
- invent market data;
- invent citations;
- generate unverified probability estimates;
- override risk gates;
- bypass validation;
- convert narrative confidence into position size;
- use future news in historical tests.

Any textual feature must record:

- source;
- publication time;
- ingestion time;
- language;
- model version;
- prompt version;
- output schema;
- confidence;
- evidence references.

Text-derived signals must be evaluated incrementally against non-text baselines.

If they add narrative quality but no stable predictive value, retain them only for explanation or risk monitoring, not ranking.

---

# 31. Reinforcement Learning Restrictions

Do not use reinforcement learning merely because it is fashionable.

RL may be researched for:

- execution scheduling;
- order placement;
- constrained portfolio adjustment;
- transaction-cost minimization;
- dynamic risk budgeting.

RL must not become the primary live stock-selection engine unless it demonstrates:

- stable out-of-sample performance;
- safe constrained behavior;
- robust offline evaluation;
- no reward hacking;
- realistic environment modeling;
- baseline superiority after costs;
- reproducibility across seeds;
- reliable behavior under distribution shift.

Prefer offline or constrained RL over unconstrained online exploration.

No live-money exploration is allowed.

---

# 32. Intelligent Stock Screener Upgrade

The intelligent stock screener must become a real analytical decision-support system.

Each recommendation should contain:

```text
Company name
Ticker
Exchange
Data cutoff timestamp
Model version
Recommended evaluation horizon
Tradability status
Maximum affordable board-lot quantity
Expected return range
Expected downside range
Calibrated probability where available
Prediction interval
Cross-sectional rank
Positive factor contributions
Negative factor contributions
Crash-risk estimate
Liquidity estimate
Estimated trading cost
Regime compatibility
Model agreement/disagreement
Uncertainty status
Out-of-sample validation status
Paper performance status
Suggested maximum position
Entry conditions
Invalidation conditions
Stop-loss rationale
Take-profit rationale
Reasons not to trade
```

The UI must distinguish:

```text
research candidate
watchlist candidate
Paper eligible
simulated-broker eligible
manual-live eligible
blocked
```

Do not display a generic “Buy” label when required validation is incomplete.

---

# 33. Recommendation Language

Ban unsupported certainty.

Do not use:

```text
Guaranteed profit
Must rise
Sure win
AI strongly guarantees
High probability
Low risk
```

unless probability and risk labels are formally defined and calibrated.

Use:

```text
The current model estimates...
Under historically similar out-of-sample conditions...
After estimated transaction costs...
Subject to the following invalidation conditions...
Model disagreement is currently...
Confidence is reduced because...
This candidate is blocked from live execution because...
```

---

# 34. Paper Trading Upgrade

Paper trading must use the same:

- signal timestamps;
- portfolio rules;
- risk checks;
- order schema;
- state machine;
- transaction-cost model;
- board-lot handling;
- T+1 rules;
- price-limit logic;
- reconciliation logic;

as live trading wherever possible.

Avoid a simplified Paper adapter that produces unrealistically clean results.

Paper execution should simulate:

- pending orders;
- rejection;
- partial fills;
- unfilled limit orders;
- price limits;
- suspension;
- delays;
- slippage;
- insufficient cash;
- T+1 rejection;
- duplicate submission;
- disconnected broker.

The Paper system must preserve event logs that can be replayed.

---

# 35. MiniQMT and Live Execution Upgrade

Use official XtQuant behavior as the source of truth for the integration.

Implement a formal order lifecycle:

```text
CREATED
→ RISK_REJECTED
→ USER_CONFIRMATION_REQUIRED
→ SUBMITTING
→ BROKER_ACKNOWLEDGED
→ ACCEPTED
→ PARTIALLY_FILLED
→ FILLED
→ CANCEL_PENDING
→ CANCELLED
→ REJECTED
→ UNKNOWN_REQUIRES_RECONCILIATION
```

Do not treat an order ID as proof of a fill.

Required safeguards:

- active MiniQMT session validation;
- account identity check using masked identifiers;
- trading-day validation;
- trading-session validation;
- fresh-quote validation;
- cash validation;
- position validation;
- T+1 validation;
- lot-size validation;
- price-limit validation;
- maximum order-value validation;
- daily order-count limit;
- duplicate-order idempotency key;
- manual confirmation;
- post-submit reconciliation;
- restart recovery;
- kill switch.

The live executor must be downstream from model governance.

A high model score must never bypass broker safety controls.

---

# 36. Shadow Mode

Implement shadow mode before Paper or live promotion.

Shadow mode must:

- generate production-time recommendations;
- construct intended orders;
- never submit them;
- record hypothetical timestamps and prices;
- compare predictions with future outcomes;
- compare intended fills with executable fills;
- monitor drift;
- monitor calibration;
- monitor transaction-cost assumptions.

Use shadow results to detect discrepancies between offline backtests and live market conditions.

---

# 37. Champion–Challenger Architecture

Maintain:

- one production champion;
- one or more challengers;
- a simple fallback baseline.

Challengers run in shadow mode.

Promotion requires:

- sufficient observations;
- superior net performance;
- acceptable drawdown;
- acceptable turnover;
- stable calibration;
- no governance violations;
- consistent results across regimes;
- no excessive concentration;
- successful application tests.

Do not automatically replace the champion based on a short recent period.

---

# 38. Monitoring and Automatic Degradation

Monitor:

- data freshness;
- missing fields;
- factor drift;
- prediction drift;
- calibration drift;
- rolling IC;
- rolling Rank IC;
- rolling DSR;
- rolling drawdown;
- turnover;
- cost error;
- fill-rate error;
- broker connection;
- reconciliation mismatch.

The platform must degrade safely.

Examples:

```text
Missing fundamentals
→ remove affected factors and lower confidence

Stale market data
→ block new recommendations

Calibration failure
→ hide probability language and reduce exposure

Factor IC collapse
→ demote affected model to shadow mode

Broker reconciliation mismatch
→ disable new live orders

Validation expired
→ require revalidation before live eligibility
```

---

# 39. Model Governance and Versioning

Every recommendation must be traceable to:

- dataset version;
- feature version;
- label version;
- model version;
- hyperparameters;
- validation report;
- code commit;
- generation timestamp;
- risk-policy version;
- transaction-cost profile.

Create model cards containing:

```text
Intended use
Prohibited use
Training data
Evaluation periods
Feature groups
Known limitations
Market regimes
Performance
Costs
Calibration
Risk controls
Failure modes
Promotion status
Rollback procedure
```

---

# 40. Application-Level Integration

Algorithm changes must visibly improve the application.

Update:

## Intelligent Stock Selection

- real factor contribution;
- real uncertainty;
- real validation status;
- real trade feasibility;
- real risk penalties;
- real net-of-cost estimates.

## Paper Trading

- realistic order simulation;
- stateful fills;
- T+1;
- price limits;
- costs;
- reconciliation;
- post-trade attribution.

## Live Trading

- only eligible models;
- manual confirmation;
- enforced limits;
- duplicate prevention;
- broker status reconciliation;
- failure-safe behavior.

## Reports

- recommendation evidence;
- portfolio exposure;
- predicted versus realized outcomes;
- factor attribution;
- cost attribution;
- model drift;
- rejected recommendations;
- blocked orders.

Do not add decorative UI fields that are disconnected from actual backend calculations.

---

# 41. Testing Requirements

Add tests covering:

## Unit Tests

- factor formulas;
- lagging;
- neutralization;
- winsorization;
- point-in-time retrieval;
- masks;
- labels;
- cost model;
- allocation;
- risk limits;
- calibration;
- drift detection;
- order transitions.

## Integration Tests

- data → features;
- features → model;
- model → ranking;
- ranking → portfolio;
- portfolio → Paper;
- Paper → reporting;
- portfolio → broker dry-run;
- broker callbacks → reconciliation.

## Leakage Tests

- future financial statements;
- revised financial statements;
- future index membership;
- future industry labels;
- post-close data used pre-close;
- same-event overlap across folds;
- test-set hyperparameter selection.

## Execution Tests

- duplicate click;
- network timeout;
- broker disconnect;
- delayed acknowledgement;
- partial fill;
- rejected order;
- stale session;
- insufficient cash;
- T+1 sale;
- price-limit order;
- restart after submission.

## Browser E2E

Verify that actual backend outputs appear in:

- screener cards;
- research reports;
- watchlist;
- Paper positions;
- order confirmation;
- broker session;
- risk warnings;
- blocked-trade explanations.

No critical E2E failures may remain before completion.

---

# 42. Acceptance Criteria

The upgrade may be declared successful only when all mandatory criteria are satisfied.

## Research

- Real searches executed;
- Search log preserved;
- Full-text sources inspected where accessible;
- Evidence matrix complete;
- Limitations documented;
- Unsupported methods rejected.

## Data

- Point-in-time audit passed;
- No known future leakage;
- Historical universe handled;
- A-share market rules represented;
- Data versions reproducible.

## Algorithms

- Strong baselines retained;
- Candidate methods implemented;
- Ablations completed;
- Incremental value measured;
- Uncertainty or calibration added;
- Risk and return separated;
- Cost-aware selection implemented.

## Validation

- Walk-Forward completed;
- Purged validation completed;
- CPCV completed where feasible;
- Final holdout untouched until final evaluation;
- Costs included;
- Stress tests completed;
- Multiple testing recorded;
- PBO/DSR or suitable equivalents reported.

## Application

- Screener uses upgraded model outputs;
- Paper uses realistic execution;
- Live path respects eligibility;
- Reports expose uncertainty and limitations;
- UI status matches backend truth.

## Safety

- No unconfirmed live orders;
- No credential exposure;
- Broker reconciliation works;
- Duplicate-order protection works;
- Kill switch works;
- Capital limits are enforced server-side.

## Quality

- Unit tests pass;
- Integration tests pass;
- Critical E2E tests pass;
- No production placeholders;
- No fabricated data;
- No unresolved high-severity defects.

---

# 43. Required Output Files

Create or update:

```text
docs/research/
├── 00_CURRENT_SYSTEM_AUDIT.md
├── 00_CURRENT_ALGORITHM_MAP.md
├── 00_BASELINE_LIMITATIONS.md
├── 01_SEARCH_LOG.md
├── 02_RESEARCH_EVIDENCE_MATRIX.md
├── 03_RESEARCH_LIMITATIONS.md
├── 04_REJECTED_METHODS.md
├── 05_DATA_LEAKAGE_AUDIT.md
├── 06_POINT_IN_TIME_DATA_DESIGN.md
├── 07_FACTOR_RESEARCH_REPORT.md
├── 08_MODEL_COMPARISON.md
├── 09_VALIDATION_REPORT.md
├── 10_TRANSACTION_COST_REPORT.md
├── 11_PAPER_TRADING_VALIDATION.md
├── 12_BROKER_EXECUTION_VALIDATION.md
├── 13_APPLICATION_INTEGRATION.md
├── 14_MODEL_CARD.md
├── 15_LIVE_TRADING_GATE.md
└── FINAL_QUANT_UPGRADE_REPORT.md
```

Create machine-readable artifacts:

```text
artifacts/
├── research_registry.json
├── research_search_log.json
├── factor_registry.json
├── dataset_manifest.json
├── feature_manifest.json
├── label_manifest.json
├── experiment_registry.json
├── model_registry.json
├── model_validation.json
├── calibration_report.json
├── cost_model.json
├── portfolio_constraints.json
├── broker_validation.json
└── final_acceptance_result.json
```

---

# 44. Final Feedback Requirement

When execution is complete, return a final feedback message to the owner.

The response must not merely say “completed.”

It must contain:

## A. What Was Researched

- search date;
- databases and sources searched;
- search topics;
- number of sources reviewed;
- number read in full;
- evidence distribution;
- newest research year included.

## B. What Was Learned

- useful findings;
- conflicting findings;
- limitations;
- A-share-specific conclusions;
- findings rejected as unreliable.

## C. What Was Changed

For every material change:

```text
Problem
Research basis
Previous implementation
New implementation
Files changed
Tests added
Measured result
Known limitation
Deployment status
```

## D. Quantitative Before/After Comparison

Report baseline versus upgraded system for:

- net OOS return;
- maximum drawdown;
- Sharpe;
- DSR;
- Rank IC;
- turnover;
- transaction costs;
- calibration;
- worst regime;
- Paper performance;
- execution reliability.

Do not omit negative changes.

## E. Application Demonstration

Report:

- intelligent screener changes;
- recommendation-card changes;
- Paper changes;
- broker changes;
- screenshots or test evidence;
- API evidence;
- E2E evidence.

## F. Deployment Eligibility

Explicitly return one of:

```text
RESEARCH_ONLY
SHADOW_ELIGIBLE
PAPER_ELIGIBLE
SIMULATED_BROKER_ELIGIBLE
MANUAL_LIVE_ELIGIBLE
NOT_ELIGIBLE
```

Include exact reasons.

## G. Remaining Blockers

List:

- missing data;
- missing permissions;
- unavailable broker features;
- unresolved validation issues;
- insufficient observations;
- remaining risks.

## H. Exact Next Action for the Owner

Provide only actions that genuinely require owner participation, such as:

- supplying a data token;
- launching MiniQMT;
- logging into the broker;
- approving a permission;
- reviewing a manual-live gate.

Do not delegate ordinary engineering work back to the owner.

---

# 45. Final Acceptance JSON

Create:

```json
{
  "status": "PASS | PARTIAL | FAIL",
  "research_completed": false,
  "full_text_sources_reviewed": 0,
  "methods_considered": 0,
  "methods_implemented": 0,
  "methods_rejected": 0,
  "point_in_time_audit_passed": false,
  "leakage_audit_passed": false,
  "walk_forward_passed": false,
  "purged_validation_passed": false,
  "cpcv_completed": false,
  "transaction_costs_included": false,
  "a_share_rules_included": false,
  "baseline_comparison_completed": false,
  "ablation_completed": false,
  "paper_validation_passed": false,
  "broker_validation_passed": false,
  "critical_unit_tests_passed": false,
  "critical_integration_tests_passed": false,
  "critical_e2e_tests_passed": false,
  "live_auto_execution_enabled": false,
  "deployment_eligibility": "RESEARCH_ONLY",
  "blocking_issues": [],
  "owner_actions_required": [],
  "generated_at": ""
}
```

A `PASS` result is prohibited when any critical field is falsely reported or unverified.

---

# 46. Execution Order

Execute in this order:

```text
1. Create a dedicated branch and backup
2. Audit the existing platform
3. Freeze and measure the current baseline
4. Search current primary research
5. Build the evidence and limitations registry
6. Map research to actual platform weaknesses
7. Repair point-in-time and leakage issues first
8. Improve factors and labels
9. Add strong baselines
10. Implement candidate return, risk, ranking, and uncertainty models
11. Improve transaction-cost and portfolio construction logic
12. Run Walk-Forward and purged validation
13. Run ablations and robustness tests
14. Retain only validated improvements
15. Integrate results into the screener
16. Upgrade Paper execution realism
17. Validate MiniQMT/broker dry-run and reconciliation
18. Run unit, integration, API, and browser E2E tests
19. Produce model cards and governance artifacts
20. Return the complete final feedback report
```

Do not push to production, merge into the protected main branch, or enable unattended live trading unless separately authorized.

---

# 47. Definition of Real Improvement

A change is a real improvement only when it satisfies all relevant conditions:

- logically correct;
- based on accessible evidence;
- appropriate for A-shares;
- point-in-time valid;
- leakage-safe;
- reproducible;
- better out of sample;
- better after realistic costs;
- robust across market regimes;
- operationally executable;
- explainable enough for governance;
- integrated into the application;
- tested from backend to UI;
- safe for its assigned deployment stage.

A higher backtest return alone is not a real improvement.

A newer model alone is not a real improvement.

A longer research report alone is not a real improvement.

A completed task means the platform’s code, validation, application behavior, and operating controls have materially improved, with evidence.
