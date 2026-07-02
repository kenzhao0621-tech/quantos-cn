"""Incremental compute DAG (v2.2 §4.1).

Pipeline shape: RawData -> CleanData -> FeatureVector -> ModelPrediction ->
AgentDebate -> Score -> AdvisoryPlan -> Report. Each node declares its
dependencies; a node recomputes only when its input fingerprint (upstream
output fingerprints + own params_hash + declared data_version) changes.

Node outputs must be JSON-serialisable so fingerprints are stable.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from quant.cache_os.cache_key import params_hash


def _fingerprint(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class ComputeNode:
    """A named computation with declared upstream dependencies.

    ``fn`` receives a dict of upstream outputs keyed by node name and must
    return a JSON-serialisable value. ``data_version`` lets source nodes bind
    to external data fingerprints (e.g. warehouse_data_version()).
    """

    name: str
    fn: Callable[[Dict[str, Any]], Any]
    deps: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)
    data_version: str = ""


@dataclass
class NodeResult:
    name: str
    value: Any
    fingerprint: str
    recomputed: bool
    elapsed_ms: float
    input_fingerprint: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "fingerprint": self.fingerprint,
            "recomputed": self.recomputed,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


class IncrementalRunner:
    """Executes a DAG, skipping nodes whose inputs are unchanged since last run.

    State (input fingerprint -> output value/fingerprint per node) lives in
    process memory by default; pass ``state`` to share/persist it.
    """

    def __init__(self, state: Optional[Dict[str, Dict[str, Any]]] = None) -> None:
        # state[node_name] = {"input_fp": ..., "output_fp": ..., "value": ...}
        self.state: Dict[str, Dict[str, Any]] = state if state is not None else {}

    def run(self, nodes: List[ComputeNode]) -> Dict[str, NodeResult]:
        order = self._topo_sort(nodes)
        by_name = {n.name: n for n in nodes}
        results: Dict[str, NodeResult] = {}

        for name in order:
            node = by_name[name]
            upstream = {d: results[d] for d in node.deps}
            input_fp = _fingerprint({
                "deps": {d: r.fingerprint for d, r in upstream.items()},
                "params_hash": params_hash(node.params),
                "data_version": node.data_version,
            })
            cached = self.state.get(name)
            if cached and cached.get("input_fp") == input_fp:
                results[name] = NodeResult(
                    name=name, value=cached["value"], fingerprint=cached["output_fp"],
                    recomputed=False, elapsed_ms=0.0, input_fingerprint=input_fp,
                )
                continue

            started = time.perf_counter()
            value = node.fn({d: r.value for d, r in upstream.items()})
            elapsed = (time.perf_counter() - started) * 1000
            output_fp = _fingerprint(value)
            self.state[name] = {"input_fp": input_fp, "output_fp": output_fp, "value": value}
            results[name] = NodeResult(
                name=name, value=value, fingerprint=output_fp,
                recomputed=True, elapsed_ms=elapsed, input_fingerprint=input_fp,
            )
        return results

    @staticmethod
    def _topo_sort(nodes: List[ComputeNode]) -> List[str]:
        by_name = {n.name: n for n in nodes}
        visited: Dict[str, int] = {}  # 0=visiting, 1=done
        order: List[str] = []

        def visit(name: str) -> None:
            mark = visited.get(name)
            if mark == 1:
                return
            if mark == 0:
                raise ValueError(f"cycle detected at node '{name}'")
            node = by_name.get(name)
            if node is None:
                raise KeyError(f"undeclared dependency '{name}'")
            visited[name] = 0
            for dep in node.deps:
                visit(dep)
            visited[name] = 1
            order.append(name)

        for n in nodes:
            visit(n.name)
        return order
