"""ComputeOS — incremental computation DAG with fingerprint-based skip (v2.2 §4).

Rule: if a node's inputs (upstream fingerprints + params_hash) have not changed,
its cached output is reused and the compute function is NOT re-run. Profiling
records every step against the performance budget and logs slow steps honestly.
"""

from quant.compute_os.incremental import ComputeNode, IncrementalRunner, NodeResult
from quant.compute_os.profiling import PerformanceBudget, StepProfiler, get_profiler

__all__ = [
    "ComputeNode",
    "IncrementalRunner",
    "NodeResult",
    "PerformanceBudget",
    "StepProfiler",
    "get_profiler",
]
