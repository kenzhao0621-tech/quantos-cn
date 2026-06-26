ROOT := $(CURDIR)
PYTHON := $(ROOT)/.venv-china-quant/bin/python
PIP := $(ROOT)/.venv-china-quant/bin/pip
UVICORN_APP := gateway.api.app:app
GATEWAY_PORT := 8787
GATEWAY_HOST := 127.0.0.1

.PHONY: v6-test v6-e2e bootstrap install-editable doctor dev portal portal-stop portal-status \
        app app-stop app-status app-reset-demo \
        test test-core test-gateway test-quantos test-e2e \
        data-status backfill daily-report backtest \
        paper-start paper-stop shadow-start shadow-stop status halt \
        gateway-test gateway-acceptance quantos-test quantos-acceptance \
        vnpy-doctor qlib-doctor research-baseline reconcile native-status \
        vnpy-native-install-dry-run qlib-native-install-dry-run \
        vnpy-native-start vnpy-native-stop qlib-native-baseline \
        research-agents data-update risk-reset native-acceptance final-test

bootstrap:
	python3 -m venv .venv-china-quant || true
	$(PIP) install -r requirements/requirements-china-quant-pins.txt
	$(PIP) install -r requirements/requirements-gateway-pins.txt
	$(PIP) install -r requirements/requirements-quantos-pins.txt
	$(MAKE) install-editable

install-editable:
	$(PIP) install -e .

doctor:
	$(PYTHON) -c "import gateway; import quant; print('gateway', gateway.__version__, 'quant', quant.__version__)"
	$(PYTHON) scripts/run-all-readiness-tests.py
	$(PYTHON) scripts/run-gateway-tests.py

dev: portal

portal:
	cd "$(ROOT)" && \
	"$(PYTHON)" -m uvicorn "$(UVICORN_APP)" \
		--app-dir "$(ROOT)" \
		--host $(GATEWAY_HOST) \
		--port $(GATEWAY_PORT)

portal-stop:
	bash "$(ROOT)/scripts/stop-portal.sh"

portal-status:
	bash "$(ROOT)/scripts/portal-status.sh"

app:
	bash "$(ROOT)/scripts/start-app.sh"

app-stop:
	bash "$(ROOT)/scripts/stop-portal.sh"

app-status:
	bash "$(ROOT)/scripts/portal-status.sh"

app-reset-demo:
	rm -f "$(ROOT)/data/gateway/kill_switch.json" "$(ROOT)/data/gateway/runtime_state.json"
	$(PYTHON) -c "from gateway.config import save_runtime_mode; save_runtime_mode('RESEARCH_ONLY'); print('demo reset ok')"

test: test-e2e

test-core:
	"$(PYTHON)" scripts/run-all-readiness-tests.py

test-gateway:
	"$(PYTHON)" scripts/run-gateway-tests.py

test-quantos:
	"$(PYTHON)" scripts/run-quantos-tests.py

test-e2e:
	"$(PYTHON)" scripts/run-app-e2e-tests.py

data-status:
	$(PYTHON) -m quant candidate-readiness

backfill:
	$(PYTHON) -m quant update-indices
	$(PYTHON) -m quant update-daily-bars
	$(PYTHON) -m quant update-sectors
	$(PYTHON) -m quant update-fundamentals
	$(PYTHON) -m quant update-disclosures

daily-report:
	$(PYTHON) scripts/run-daily-quant-pipeline.py

backtest:
	$(PYTHON) -c "from gateway.backtest.event_engine import run_event_backtest; r=run_event_backtest(run_id='cli', as_of_date='2026-06-16', bars=[{'date':'2026-06-16','symbol':'600000.SH','close':10}], signals=[{'date':'2026-06-16','symbol':'600000.SH','side':'BUY','price':10}]); print(r.to_dict())"

paper-start:
	$(PYTHON) -c "from gateway.config import save_runtime_mode; save_runtime_mode('PAPER_TRADING'); print('mode=PAPER_TRADING')"

paper-stop:
	$(PYTHON) -c "from gateway.config import save_runtime_mode; save_runtime_mode('RESEARCH_ONLY'); print('mode=RESEARCH_ONLY')"

shadow-start:
	$(PYTHON) -c "from gateway.config import save_runtime_mode; save_runtime_mode('SHADOW_LIVE'); print('mode=SHADOW_LIVE')"

shadow-stop:
	$(PYTHON) -c "from gateway.config import save_runtime_mode; save_runtime_mode('PAPER_TRADING'); print('mode=PAPER_TRADING')"

status:
	$(PYTHON) -c "from gateway.config import GatewayConfig, load_runtime_state; from gateway.risk.engine import RiskEngine; from services.vnpy_runtime.main import get_runtime; from integrations.qlib.provider import CNMarketProvider; c=GatewayConfig.load(); r=RiskEngine(c); s=load_runtime_state(); print({'mode':s.get('mode'), 'risk':r.snapshot().to_dict(), 'vnpy':get_runtime().status(), 'qlib':CNMarketProvider().health()})"

halt:
	$(PYTHON) -c "from gateway.risk.kill_switch import KillSwitch; from gateway.config import save_runtime_mode; KillSwitch().halt('make_halt','operator'); save_runtime_mode('HALTED'); print('HALTED')"

gateway-test:
	$(PYTHON) scripts/run-gateway-tests.py

gateway-acceptance:
	$(PYTHON) scripts/run-gateway-acceptance.py

quantos-test:
	$(PYTHON) scripts/run-quantos-tests.py

quantos-acceptance:
	$(PYTHON) scripts/run-quantos-acceptance.py

vnpy-doctor:
	$(PYTHON) -c "from services.vnpy_runtime.main import get_runtime; import json; print(json.dumps(get_runtime().doctor(), indent=2))"

qlib-doctor:
	$(PYTHON) -c "from integrations.qlib.provider import CNMarketProvider; import json; print(json.dumps(CNMarketProvider().health(), indent=2))"

research-baseline:
	$(PYTHON) -c "from integrations.qlib.workflow import run_baseline_workflow; import json; print(json.dumps(run_baseline_workflow(as_of='2026-06-16'), indent=2))"

alpha158-cache:
	$(PYTHON) scripts/build_alpha158_cache.py --mode sample --sample-size 300

alpha158-cache-full:
	$(PYTHON) scripts/build_alpha158_cache.py --mode full --force

train-lgbm-sample:
	$(PYTHON) scripts/train_lgbm_sample.py

quant-upgrade:
	$(PYTHON) scripts/run_quant_upgrade_pipeline.py

quantos-closed-loop:
	$(PYTHON) scripts/run_quantos_closed_loop.py

audit: quantos-audit
quantos-audit:
	$(PYTHON) scripts/run_quantos_audit.py

validate: quantos-validate
quantos-validate:
	$(PYTHON) scripts/run_quant_upgrade_pipeline.py
	$(PYTHON) -c "from quant.validation.leakage_detector import persist_leakage_report; persist_leakage_report()"

report: quantos-report
quantos-report:
	$(PYTHON) scripts/generate_final_quantos_report.py

prelaunch:
	$(PYTHON) scripts/run_prelaunch_maintenance.py

test:
	$(PYTHON) -m pytest tests/ -q

reconcile:
	$(PYTHON) -c "from services.vnpy_runtime.main import get_runtime; from integrations.vnpy.reconciliation import reconcile; import json; print(json.dumps(reconcile(get_runtime().paper.positions()).to_dict(), indent=2))"

native-status:
	$(PYTHON) -c "from services.vnpy_runtime.main import get_runtime; from integrations.qlib.provider import CNMarketProvider; import json; print(json.dumps({'vnpy': get_runtime().doctor(), 'qlib': CNMarketProvider().health()}, indent=2))"

vnpy-native-install-dry-run:
	@echo "Would run: pip install vnpy (not executed — shim mode default)"
	$(PYTHON) -c "print({'dry_run': True, 'package': 'vnpy', 'executed': False})"

qlib-native-install-dry-run:
	@echo "Would run: scripts/setup-native-venvs.sh (qlib only)"
	$(PYTHON) -c "print({'dry_run': True, 'script': 'setup-native-venvs.sh'})"

setup-native-venvs:
	bash "$(ROOT)/scripts/setup-native-venvs.sh"

vnpy-native-start:
	$(PYTHON) -c "from gateway.native.bridge import run_native_script; import json; print(json.dumps(run_native_script('vnpy','vnpy_acceptance.py'), indent=2))"

vnpy-native-stop:
	$(PYTHON) -c "from services.vnpy_runtime.main import get_runtime; import json; print(json.dumps(get_runtime().stop(), indent=2))"

qlib-native-baseline:
	$(PYTHON) -c "from gateway.native.bridge import run_native_script; import json; print(json.dumps(run_native_script('qlib','qlib_acceptance.py', timeout=600), indent=2))"

research-agents:
	$(PYTHON) -c "from gateway.agents.cn_research.workflow import run_agent_research; import json; print(json.dumps(run_agent_research(as_of='2026-06-16').to_dict(), indent=2, ensure_ascii=False))"

data-update:
	$(PYTHON) -c "import subprocess,sys; r=subprocess.run([sys.executable,'-m','quant','update-indices']); sys.exit(r.returncode)"

risk-reset:
	$(PYTHON) -c "from gateway.risk.kill_switch import KillSwitch; ks=KillSwitch(); print(ks.manual_reset('make').to_dict())"

native-acceptance: setup-native-venvs
	$(ROOT)/.venv-vnpy-native/bin/python scripts/native/vnpy_acceptance.py
	$(ROOT)/.venv-qlib-native/bin/python scripts/native/qlib_acceptance.py

final-test:
	$(PYTHON) scripts/run-final-acceptance.py

fresh-ui-test:
	$(PYTHON) scripts/run-fresh-browser-ui-e2e.py

v6-test:
	$(PYTHON) scripts/run-v6-contract-tests.py

v6-e2e:
	$(PYTHON) scripts/run-v6-fresh-browser-e2e.py
