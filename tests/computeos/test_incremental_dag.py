"""v2.2 §4.1 acceptance: unchanged inputs must NOT recompute downstream nodes."""

import pytest

from quant.compute_os.incremental import ComputeNode, IncrementalRunner


def _pipeline(calls, raw_version="v1", score_params=None):
    return [
        ComputeNode("raw", lambda up: {"bars": [1, 2, 3] if raw_version == "v1" else [1, 2, 4]},
                    data_version=raw_version),
        ComputeNode("clean", lambda up: calls.append("clean") or {"clean": up["raw"]["bars"]},
                    deps=["raw"]),
        ComputeNode("features", lambda up: calls.append("features") or {"f": sum(up["clean"]["clean"])},
                    deps=["clean"]),
        ComputeNode("score", lambda up: calls.append("score") or {"s": up["features"]["f"] * 2},
                    deps=["features"], params=score_params or {"w": 1}),
    ]


def test_second_run_skips_everything_when_nothing_changed():
    calls = []
    runner = IncrementalRunner()
    runner.run(_pipeline(calls))
    assert calls == ["clean", "features", "score"]
    results = runner.run(_pipeline(calls))
    assert calls == ["clean", "features", "score"]  # no new calls
    assert all(not r.recomputed for r in results.values())


def test_raw_data_change_recomputes_chain():
    calls = []
    runner = IncrementalRunner()
    runner.run(_pipeline(calls))
    runner.run(_pipeline(calls, raw_version="v2"))
    assert calls == ["clean", "features", "score", "clean", "features", "score"]


def test_params_change_recomputes_only_affected_node():
    calls = []
    runner = IncrementalRunner()
    runner.run(_pipeline(calls))
    runner.run(_pipeline(calls, score_params={"w": 2}))
    assert calls == ["clean", "features", "score", "score"]


def test_unchanged_output_fingerprint_stops_propagation():
    """clean recomputes but yields identical output -> features/score skipped."""
    calls = []
    counter = {"n": 0}

    def make(raw_version):
        def clean_fn(up):
            calls.append("clean")
            return {"clean": [1, 2, 3]}  # same output regardless of raw

        return [
            ComputeNode("raw", lambda up: counter.__setitem__("n", counter["n"] + 1) or {"v": raw_version},
                        data_version=raw_version),
            ComputeNode("clean", clean_fn, deps=["raw"]),
            ComputeNode("features", lambda up: calls.append("features") or {"f": 1}, deps=["clean"]),
        ]

    runner = IncrementalRunner()
    runner.run(make("v1"))
    runner.run(make("v2"))
    assert calls == ["clean", "features", "clean"]  # features skipped on 2nd run


def test_cycle_detection():
    nodes = [
        ComputeNode("a", lambda up: 1, deps=["b"]),
        ComputeNode("b", lambda up: 2, deps=["a"]),
    ]
    with pytest.raises(ValueError, match="cycle"):
        IncrementalRunner().run(nodes)


def test_missing_dependency_raises():
    with pytest.raises(KeyError):
        IncrementalRunner().run([ComputeNode("a", lambda up: 1, deps=["ghost"])])


def test_profiler_flags_over_budget(tmp_path):
    from quant.compute_os.profiling import PerformanceBudget, StepProfiler

    prof = StepProfiler(PerformanceBudget({"tiny_step": 0.0001}), log_path=tmp_path / "perf.jsonl")
    rec = prof.record("tiny_step", elapsed_ms=50.0, cache_hit=False)
    assert rec["over_budget"] is True
    assert rec["slow_step_name"] == "tiny_step"
    assert rec["suggested_optimization"]
    assert (tmp_path / "perf.jsonl").exists()


def test_profiler_within_budget(tmp_path):
    from quant.compute_os.profiling import PerformanceBudget, StepProfiler

    prof = StepProfiler(PerformanceBudget({"fast": 10.0}), log_path=tmp_path / "perf.jsonl")
    with prof.step("fast") as ctx:
        ctx["cache_hit"] = True
    assert prof.summary()["over_budget_count"] == 0
