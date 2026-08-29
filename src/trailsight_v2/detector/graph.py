"""Canonical graph construction and pinned GARG-AML reference semantics."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator

import networkx as nx
import numpy as np

from trailsight_v2.detector.constants import COMMUNITY_RESOLUTION, COMMUNITY_SEED
from trailsight_v2.detector.models import AccountScore, GargMeasures, UnscoredReason
from trailsight_v2.detector.provenance import assert_supported_networkx

CanonicalEdge = tuple[str, str]


def canonical_undirected_edge(left: str, right: str) -> CanonicalEdge | None:
    """Return one canonical simple edge, excluding self-loops."""
    if left == right:
        return None
    return (left, right) if left < right else (right, left)


def build_simple_undirected_graph(edges: Iterable[tuple[str, str]]) -> nx.Graph:
    """Build the frozen simple, unweighted, undirected account graph."""
    graph = nx.Graph()
    canonical_edges = {
        edge
        for left, right in edges
        if (edge := canonical_undirected_edge(left, right)) is not None
    }
    graph.add_edges_from(sorted(canonical_edges))
    return graph


def add_canonical_edges(graph: nx.Graph, edges: Iterable[tuple[str, str]]) -> None:
    canonical_edges = {
        edge
        for left, right in edges
        if (edge := canonical_undirected_edge(left, right)) is not None
    }
    graph.add_edges_from(sorted(canonical_edges))


def _stable_communities(communities: Iterable[set[str]]) -> list[tuple[str, ...]]:
    normalized = [tuple(sorted(community)) for community in communities]
    return sorted(normalized, key=lambda members: (members[0], len(members), members))


def apply_louvain_community_filter(graph: nx.Graph) -> tuple[nx.Graph, dict[str, int]]:
    """Apply the exact upstream Louvain membership and retain intra-community edges."""
    assert_supported_networkx()
    if graph.is_directed():
        raise ValueError("GARG undirected-basic requires an undirected graph")
    if graph.number_of_nodes() == 0:
        return nx.Graph(), {}
    if graph.number_of_edges() == 0:
        stable = [(node,) for node in sorted(graph.nodes)]
    else:
        detected = nx.community.louvain_communities(
            graph,
            resolution=COMMUNITY_RESOLUTION,
            seed=COMMUNITY_SEED,
        )
        stable = _stable_communities(detected)

    community_by_node = {
        node: community_index
        for community_index, members in enumerate(stable)
        for node in members
    }
    filtered = nx.Graph()
    filtered.add_nodes_from(graph.nodes(data=True))
    filtered.add_edges_from(
        (left, right)
        for left, right in graph.edges
        if community_by_node[left] == community_by_node[right]
    )
    return filtered, community_by_node


def neighborhood_sets(graph: nx.Graph, node: str) -> tuple[frozenset[str], frozenset[str]]:
    lengths = nx.single_source_shortest_path_length(graph, node, cutoff=2)
    first = frozenset(candidate for candidate, distance in lengths.items() if distance == 1)
    second = frozenset(candidate for candidate, distance in lengths.items() if distance == 2)
    return first, second


def garg_undirected_reference_measures(graph: nx.Graph, node: str) -> GargMeasures:
    """Port the pinned upstream dense-adjacency undirected measure implementation.

    Source parity target:
    ``src/methods/GARGAML.py::GARG_AML_node_undirected_measures`` and
    ``src/methods/utils/measure_functions_undirected.py`` at the pinned commit.
    """
    first, second = neighborhood_sets(graph, node)
    ordered = [node, *sorted(second), *sorted(first)]
    ego = graph.subgraph(ordered)
    adjacency = nx.to_numpy_array(
        ego,
        nodelist=ordered,
        dtype=np.float64,
        weight=None,
    )

    second_root_size = len(second) + 1
    first_size = len(first)

    piece_1 = adjacency[:second_root_size, :second_root_size]
    block_size_1 = int(piece_1.size - (3 * second_root_size) + 2)
    block_measure_1 = float(piece_1.sum() / block_size_1) if block_size_1 > 0 else 0.0

    piece_2 = adjacency[
        second_root_size : second_root_size + first_size,
        :second_root_size,
    ]
    block_size_2 = int(piece_2.size - first_size)
    reduced_sum_2 = float(piece_2.sum()) - first_size
    block_measure_2 = reduced_sum_2 / block_size_2 if block_size_2 > 0 else 1.0

    piece_3 = adjacency[second_root_size:, second_root_size:]
    block_size_3 = int(piece_3.size - first_size)
    block_measure_3 = float(piece_3.sum() / block_size_3) if block_size_3 > 0 else 0.0

    return GargMeasures(
        first_order_neighbors=first,
        second_order_neighbors=second,
        block_measure_1=block_measure_1,
        block_measure_2=block_measure_2,
        block_measure_3=block_measure_3,
        block_size_1=block_size_1,
        block_size_2=block_size_2,
        block_size_3=block_size_3,
    )


def score_preprocessed_graph(
    graph: nx.Graph,
    community_by_node: dict[str, int],
) -> Iterator[AccountScore]:
    """Score every observed graph node and apply eligibility separately."""
    for node in sorted(graph.nodes):
        measures = garg_undirected_reference_measures(graph, node)
        first_count = len(measures.first_order_neighbors)
        second_count = len(measures.second_order_neighbors)
        score = measures.score
        finite = all(
            math.isfinite(value)
            for value in (
                measures.block_measure_1,
                measures.block_measure_2,
                measures.block_measure_3,
                score,
            )
        )
        if first_count == 0:
            reason = UnscoredReason.NO_FIRST_ORDER_CONTEXT
        elif second_count == 0:
            reason = UnscoredReason.NO_SECOND_ORDER_CONTEXT
        elif not finite:
            reason = UnscoredReason.NON_FINITE_SCORE
        else:
            reason = None

        eligible = reason is None
        yield AccountScore(
            account_ref=node,
            scoring_eligible=eligible,
            network_pattern_score=score if eligible else None,
            unscored_reason=reason,
            first_order_neighbor_count=first_count,
            second_order_neighbor_count=second_count,
            community_index=community_by_node[node],
            block_measure_1=measures.block_measure_1 if eligible else None,
            block_measure_2=measures.block_measure_2 if eligible else None,
            block_measure_3=measures.block_measure_3 if eligible else None,
        )


def preprocess_and_score(graph: nx.Graph) -> tuple[nx.Graph, list[AccountScore]]:
    filtered, communities = apply_louvain_community_filter(graph)
    return filtered, list(score_preprocessed_graph(filtered, communities))

