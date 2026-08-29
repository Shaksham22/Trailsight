from __future__ import annotations

import math
import random

import networkx as nx
import numpy as np
import pytest

from trailsight_v2.data.canonical import account_ref_for
from trailsight_v2.detector.graph import (
    apply_louvain_community_filter,
    build_simple_undirected_graph,
    garg_undirected_reference_measures,
    neighborhood_sets,
    preprocess_and_score,
    score_preprocessed_graph,
)
from trailsight_v2.detector.models import GargMeasures, UnscoredReason
from trailsight_v2.detector.ranking import assign_review_bands


def pinned_upstream_measures(graph: nx.Graph, node: str) -> tuple[object, ...]:
    """Independent transcription of GARG-AML at commit 7ce2a1d."""
    ego = nx.ego_graph(graph, node, radius=2)
    nodes_1 = list(nx.ego_graph(ego, node).nodes)
    nodes_1.remove(node)
    nodes_2 = list(ego.nodes)
    nodes_2.remove(node)
    for neighbor in nodes_1:
        nodes_2.remove(neighbor)
    ordered = [node, *nodes_2, *nodes_1]
    adjacency = nx.to_numpy_array(ego, nodelist=ordered, dtype=np.float64, weight=None)
    second_size = len(nodes_2)
    first_size = len(nodes_1)
    piece_1_dim = second_size + 1

    piece_1 = adjacency[:piece_1_dim, :piece_1_dim]
    size_1 = int(piece_1.size - (3 * piece_1_dim) + 2)
    measure_1 = float(piece_1.sum() / size_1) if size_1 > 0 else 0.0

    piece_2 = adjacency[piece_1_dim : piece_1_dim + first_size, :piece_1_dim]
    size_2 = int(piece_2.size - first_size)
    measure_2 = (
        (float(piece_2.sum()) - first_size) / size_2 if size_2 > 0 else 1.0
    )

    piece_3 = adjacency[piece_1_dim:, piece_1_dim:]
    size_3 = int(piece_3.size - first_size)
    measure_3 = float(piece_3.sum() / size_3) if size_3 > 0 else 0.0
    score = measure_2 - (measure_1 + measure_3) / 2.0
    return (
        frozenset(nodes_1),
        frozenset(nodes_2),
        measure_1,
        measure_2,
        measure_3,
        size_1,
        size_2,
        size_3,
        score,
    )


def graph_fixtures() -> dict[str, nx.Graph]:
    block = nx.complete_bipartite_graph(2, 3)
    block = nx.relabel_nodes(block, {0: "a", 1: "e", 2: "b", 3: "c", 4: "d"})
    disconnected = nx.Graph()
    disconnected.add_edges_from([("a", "b"), ("b", "c"), ("x", "y"), ("y", "z")])
    return {
        "chain": nx.path_graph(["a", "b", "c", "d"]),
        "star": nx.star_graph(["hub", "a", "b", "c", "d"]),
        "clique": nx.complete_graph(["a", "b", "c", "d"]),
        "block": block,
        "disconnected": disconnected,
    }


@pytest.mark.parametrize("fixture_name", sorted(graph_fixtures()))
def test_controlled_fixture_measures_and_scores_match_pinned_upstream(
    fixture_name: str,
) -> None:
    graph = graph_fixtures()[fixture_name]
    for node in graph.nodes:
        expected = pinned_upstream_measures(graph, node)
        actual = garg_undirected_reference_measures(graph, node)
        assert actual.first_order_neighbors == expected[0]
        assert actual.second_order_neighbors == expected[1]
        assert (
            actual.block_measure_1,
            actual.block_measure_2,
            actual.block_measure_3,
            actual.block_size_1,
            actual.block_size_2,
            actual.block_size_3,
            actual.score,
        ) == pytest.approx(expected[2:])


def test_pure_block_smurfing_like_fixture_has_reference_score_one() -> None:
    measures = garg_undirected_reference_measures(graph_fixtures()["block"], "a")
    assert measures.first_order_neighbors == frozenset({"b", "c", "d"})
    assert measures.second_order_neighbors == frozenset({"e"})
    assert measures.score == pytest.approx(1.0)


def test_simple_graph_collapses_repeats_removes_self_loops_and_preserves_canonical_collision() -> None:
    bank_1_same = account_ref_for("001", "SAME")
    bank_2_same = account_ref_for("002", "SAME")
    other = account_ref_for("003", "OTHER")
    graph = build_simple_undirected_graph(
        [
            (bank_1_same, other),
            (other, bank_1_same),
            (bank_1_same, other),
            (bank_2_same, bank_2_same),
            (bank_2_same, other),
        ]
    )
    assert bank_1_same != bank_2_same
    assert graph.number_of_edges() == 2
    assert not list(nx.selfloop_edges(graph))
    assert set(graph.nodes) == {bank_1_same, bank_2_same, other}


def test_louvain_preprocessing_matches_pinned_reference_edges() -> None:
    graph = nx.barbell_graph(12, 2)
    graph = nx.relabel_nodes(graph, {node: f"acct_{node:02d}" for node in graph.nodes})
    communities = nx.community.louvain_communities(graph, resolution=10, seed=1997)
    membership = {
        node: index for index, community in enumerate(communities) for node in community
    }
    expected_edges = {
        frozenset((left, right))
        for left, right in graph.edges
        if membership[left] == membership[right]
    }
    actual, _ = apply_louvain_community_filter(graph)
    assert {frozenset(edge) for edge in actual.edges} == expected_edges
    assert set(actual.nodes) == set(graph.nodes)


def realistic_canonical_subset() -> nx.Graph:
    randomizer = random.Random(1997)
    refs = [account_ref_for(f"B{index % 11:02d}", f"A{index:04d}") for index in range(120)]
    edges: list[tuple[str, str]] = []
    for left_index, left in enumerate(refs):
        for right in refs[left_index + 1 :]:
            if randomizer.random() < 0.09:
                edges.append((left, right))
    return build_simple_undirected_graph(edges)


def test_realistic_canonical_subset_matches_reference_and_is_repeatable() -> None:
    graph = realistic_canonical_subset()
    first_filtered, first_scores = preprocess_and_score(graph)
    second_filtered, second_scores = preprocess_and_score(graph)
    assert set(first_filtered.edges) == set(second_filtered.edges)
    assert first_scores == second_scores
    expected_eligible: list[tuple[str, float]] = []
    for result in first_scores:
        expected = pinned_upstream_measures(first_filtered, result.account_ref)
        first, second = neighborhood_sets(first_filtered, result.account_ref)
        assert first == expected[0]
        assert second == expected[1]
        if result.scoring_eligible:
            assert result.network_pattern_score == pytest.approx(expected[-1], abs=1e-12)
            assert math.isfinite(result.network_pattern_score)
            expected_eligible.append((result.account_ref, expected[-1]))
    actual_bands = assign_review_bands(
        (result.account_ref, result.network_pattern_score)
        for result in first_scores
        if result.scoring_eligible and result.network_pattern_score is not None
    )
    assert actual_bands == assign_review_bands(expected_eligible)


def test_eligibility_wrapper_keeps_weak_context_unscored() -> None:
    graph = nx.Graph()
    graph.add_edges_from([("a", "b"), ("b", "c")])
    graph.add_node("isolated")
    communities = {node: 0 for node in graph.nodes}
    scores = {result.account_ref: result for result in score_preprocessed_graph(graph, communities)}
    assert scores["a"].scoring_eligible is True
    assert scores["a"].network_pattern_score == pytest.approx(1.0)
    assert scores["b"].scoring_eligible is False
    assert scores["b"].network_pattern_score is None
    assert scores["b"].unscored_reason is UnscoredReason.NO_SECOND_ORDER_CONTEXT
    assert scores["isolated"].unscored_reason is UnscoredReason.NO_FIRST_ORDER_CONTEXT


def test_non_finite_measure_is_unscored(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = nx.path_graph(["a", "b", "c"])

    def non_finite(_graph, node):
        first, second = neighborhood_sets(graph, node)
        return GargMeasures(first, second, 0.0, float("nan"), 0.0, 0, 1, 0)

    monkeypatch.setattr(
        "trailsight_v2.detector.graph.garg_undirected_reference_measures", non_finite
    )
    result = next(
        value
        for value in score_preprocessed_graph(graph, {node: 0 for node in graph.nodes})
        if value.account_ref == "a"
    )
    assert result.scoring_eligible is False
    assert result.network_pattern_score is None
    assert result.unscored_reason is UnscoredReason.NON_FINITE_SCORE
