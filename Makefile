ROOT := $(shell pwd)
PY := $(ROOT)/.venv-china-quant/bin/python
PIP := $(ROOT)/.venv-china-quant/bin/pip
GATEWAY_PORT := 8787

.PHONY: bootstrap doctor dev test portal data-status backfill daily-report backtest paper-start paper-stop shadow-start shadow-stop status halt gateway-test gateway-acceptance

bootstrap:
	python3 -m venv .venv-china-quant || true
	$(PIP) install -r docs/ai/requirements-china-quant-pins.txt
	$(PIP) install -r docs/ai/requirements-gateway-pins.txt

doctor:
	$(PY) -c "import gateway; import quant; print('gateway', gateway.__version__, 'quant', quant.__version__)"
	$(PY) scripts/run-all-readiness-tests.py
	$(PY) scripts/run-gateway-tests.py

dev:
	$(PY) apps/gateway-api/main.py

test:
	$(PY) scripts/run-all-readiness-tests.py
	$(PY) scripts/run-gateway-tests.py

portal:
	@echo "Gateway API + portal: http://127.0.0.1:$(GATEWAY_PORT)/portal"
	$(PY) apps/gateway-api/main.py

data-status:
	$(PY) -m quant candidate-readiness

backfill:
	$(PY) -m quant update-indices
	$(PY) -m quant update-daily-bars
	$(PY) -m quant update-sectors
	$(PY) -m quant update-fundamentals
	$(PY) -m quant update-disclosures

daily-report:
	$(PY) scripts/run-daily-quant-pipeline.py

backtest:
	$(PY) -c "from gateway.backtest.event_engine import run_event_backtest; r=run_event_backtest(run_id='cli', as_of_date='2026-06-16', bars=[{'date':'2026-06-16','symbol':'600000.SH','close':10}], signals=[{'date':'2026-06-16','symbol':'600000.SH','side':'BUY','price':10}]); print(r.to_dict())"

paper-start:
	$(PY) -c "from gateway.config import save_runtime_mode; save_runtime_mode('PAPER_TRADING'); print('mode=PAPER_TRADING')"

paper-stop:
	$(PY) -c "from gateway.config import save_runtime_mode; save_runtime_mode('RESEARCH_ONLY'); print('mode=RESEARCH_ONLY')"

shadow-start:
	$(PY) -c "from gateway.config import save_runtime_mode; save_runtime_mode('SHADOW_LIVE'); print('mode=SHADOW_LIVE')"

shadow-stop:
	$(PY) -c "from gateway.config import save_runtime_mode; save_runtime_mode('PAPER_TRADING'); print('mode=PAPER_TRADING')"

status:
	$(PY) -c "from gateway.config import GatewayConfig, load_runtime_state; from gateway.risk.engine import RiskEngine; c=GatewayConfig.load(); r=RiskEngine(c); s=load_runtime_state(); print({'mode':s.get('mode'), 'risk':r.snapshot().to_dict()})"

halt:
	$(PY) -c "from gateway.risk.kill_switch import KillSwitch; from gateway.config import save_runtime_mode; KillSwitch().halt('make_halt','operator'); save_runtime_mode('HALTED'); print('HALTED')"

gateway-test:
	$(PY) scripts/run-gateway-tests.py

gateway-acceptance:
	$(PY) scripts/run-gateway-acceptance.py
