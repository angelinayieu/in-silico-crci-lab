"""
Chain A: Graph Assembly — ALG-A (§2.6, §2.11, §2.17)

Builds the complete causal DAG from registry CSVs.
Produces a GraphObject consumed by all downstream chains.

Pipeline: A1 → A2 → A3 → A4 → A5

Entry point: run_chain_a()
"""
from .graph_object import GraphObject, run_chain_a

__all__ = ["GraphObject", "run_chain_a"]
