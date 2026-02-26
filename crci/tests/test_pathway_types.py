"""Tests for crci.shared.models.pathway_types — PathwayDef invariants.

Covers:
    - True immutability (frozen + tuple fields)
    - Safe hashability (dict keys / set members)
    - Computed component_nodes property
    - validate() enforcement (fail-fast on bad data)
    - Default sentinels (is_complete=None, activation_threshold=None)
    - dataclasses.replace() functional update pattern
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from crci.shared.models.pathway_types import PathwayDef


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


def _good_pathway(**overrides) -> PathwayDef:
    """Create a valid PathwayDef with sensible defaults."""
    defaults = dict(
        pathway_id="PW_TEST",
        pathway_label="Test Pathway",
        tier="mechanistic_model_implied",
        entry_node_ids=("NODE_A",),
        exit_node_ids=("NODE_D",),
        intermediate_node_ids=("NODE_B", "NODE_C"),
        edge_ids=("E1", "E2", "E3"),
        is_complete=True,
        activation_threshold=0.5,
        se_multiplier=1.0,
        expected_edge_count=3,
        status="connected",
    )
    defaults.update(overrides)
    return PathwayDef(**defaults)


# ═══════════════════════════════════════════════════════════════
#  True Immutability
# ═══════════════════════════════════════════════════════════════


class TestImmutability:
    """Verify frozen dataclass + tuple fields = truly immutable."""

    def test_cannot_rebind_attribute(self) -> None:
        """Frozen dataclass prevents attribute reassignment."""
        pw = _good_pathway()
        with pytest.raises(FrozenInstanceError):
            pw.pathway_id = "PW_HACKED"  # type: ignore[misc]

    def test_cannot_mutate_edge_ids(self) -> None:
        """Tuple fields cannot be mutated in-place (no .append)."""
        pw = _good_pathway()
        assert not hasattr(pw.edge_ids, "append")
        with pytest.raises(TypeError):
            pw.edge_ids[0] = "EVIL"  # type: ignore[index]

    def test_cannot_mutate_entry_node_ids(self) -> None:
        pw = _good_pathway()
        with pytest.raises(TypeError):
            pw.entry_node_ids[0] = "EVIL"  # type: ignore[index]

    def test_cannot_mutate_exit_node_ids(self) -> None:
        pw = _good_pathway()
        with pytest.raises(TypeError):
            pw.exit_node_ids[0] = "EVIL"  # type: ignore[index]

    def test_cannot_mutate_intermediate_node_ids(self) -> None:
        pw = _good_pathway()
        with pytest.raises(TypeError):
            pw.intermediate_node_ids[0] = "EVIL"  # type: ignore[index]


# ═══════════════════════════════════════════════════════════════
#  Hashability
# ═══════════════════════════════════════════════════════════════


class TestHashability:
    """Verify frozen + tuple → safe hash for dict keys / set members."""

    def test_hashable(self) -> None:
        pw = _good_pathway()
        h = hash(pw)
        assert isinstance(h, int)

    def test_usable_as_dict_key(self) -> None:
        pw = _good_pathway()
        d = {pw: "value"}
        assert d[pw] == "value"

    def test_usable_in_set(self) -> None:
        pw1 = _good_pathway(pathway_id="PW_1")
        pw2 = _good_pathway(pathway_id="PW_2")
        s = {pw1, pw2}
        assert len(s) == 2

    def test_equal_objects_same_hash(self) -> None:
        pw1 = _good_pathway()
        pw2 = _good_pathway()
        assert pw1 == pw2
        assert hash(pw1) == hash(pw2)


# ═══════════════════════════════════════════════════════════════
#  Computed component_nodes
# ═══════════════════════════════════════════════════════════════


class TestComponentNodes:
    """Verify component_nodes is computed union, deduplicated, ordered."""

    def test_union_of_node_lists(self) -> None:
        pw = _good_pathway(
            entry_node_ids=("A",),
            intermediate_node_ids=("B", "C"),
            exit_node_ids=("D",),
        )
        assert pw.component_nodes == ("A", "B", "C", "D")

    def test_deduplication(self) -> None:
        """If a node appears in both entry and intermediate, keep first."""
        pw = _good_pathway(
            entry_node_ids=("A", "B"),
            intermediate_node_ids=("B", "C"),
            exit_node_ids=("C", "D"),
        )
        assert pw.component_nodes == ("A", "B", "C", "D")

    def test_empty_lists(self) -> None:
        pw = _good_pathway(
            entry_node_ids=(),
            intermediate_node_ids=(),
            exit_node_ids=(),
        )
        assert pw.component_nodes == ()

    def test_order_preserved(self) -> None:
        """entry first, then intermediate, then exit — deduplicated."""
        pw = _good_pathway(
            entry_node_ids=("Z", "A"),
            intermediate_node_ids=("M",),
            exit_node_ids=("B",),
        )
        assert pw.component_nodes == ("Z", "A", "M", "B")

    def test_cannot_assign_component_nodes(self) -> None:
        """component_nodes is a property, not a stored field."""
        pw = _good_pathway()
        with pytest.raises(AttributeError):
            pw.component_nodes = ("EVIL",)  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════
#  Default Sentinels
# ═══════════════════════════════════════════════════════════════


class TestDefaults:
    """Verify safe defaults prevent silent misuse."""

    def test_is_complete_defaults_to_none(self) -> None:
        """Not computed yet → None, not True."""
        pw = PathwayDef(
            pathway_id="PW_X",
            pathway_label="X",
            tier="mechanistic_model_implied",
        )
        assert pw.is_complete is None

    def test_activation_threshold_defaults_to_none(self) -> None:
        """Not set from registry yet → None, not 0.5."""
        pw = PathwayDef(
            pathway_id="PW_X",
            pathway_label="X",
            tier="mechanistic_model_implied",
        )
        assert pw.activation_threshold is None

    def test_edge_ids_default_empty_tuple(self) -> None:
        pw = PathwayDef(
            pathway_id="PW_X",
            pathway_label="X",
            tier="mechanistic_model_implied",
        )
        assert pw.edge_ids == ()
        assert isinstance(pw.edge_ids, tuple)


# ═══════════════════════════════════════════════════════════════
#  validate() — Happy Path
# ═══════════════════════════════════════════════════════════════


class TestValidateHappy:
    """Validate passes for well-formed PathwayDef."""

    def test_good_pathway_validates(self) -> None:
        pw = _good_pathway()
        pw.validate()  # Should not raise

    def test_minimal_pathway_validates(self) -> None:
        pw = PathwayDef(
            pathway_id="PW_MIN",
            pathway_label="Minimal",
            tier="clinical_mediator",
        )
        pw.validate()


# ═══════════════════════════════════════════════════════════════
#  validate() — Failure Cases
# ═══════════════════════════════════════════════════════════════


class TestValidateFailures:
    """Validate raises ValueError on bad data."""

    def test_empty_pathway_id(self) -> None:
        pw = _good_pathway(pathway_id="")
        with pytest.raises(ValueError, match="pathway_id must be non-empty"):
            pw.validate()

    def test_whitespace_only_pathway_id(self) -> None:
        pw = _good_pathway(pathway_id="   ")
        with pytest.raises(ValueError, match="pathway_id must be non-empty"):
            pw.validate()

    def test_duplicate_entry_nodes(self) -> None:
        pw = _good_pathway(entry_node_ids=("A", "A"))
        with pytest.raises(ValueError, match="duplicate nodes in entry_node_ids"):
            pw.validate()

    def test_duplicate_exit_nodes(self) -> None:
        pw = _good_pathway(exit_node_ids=("X", "X", "Y"))
        with pytest.raises(ValueError, match="duplicate nodes in exit_node_ids"):
            pw.validate()

    def test_duplicate_intermediate_nodes(self) -> None:
        pw = _good_pathway(intermediate_node_ids=("B", "B"))
        with pytest.raises(ValueError, match="duplicate nodes in intermediate_node_ids"):
            pw.validate()

    def test_negative_expected_edge_count(self) -> None:
        pw = _good_pathway(expected_edge_count=-1)
        with pytest.raises(ValueError, match="expected_edge_count"):
            pw.validate()

    def test_zero_se_multiplier(self) -> None:
        pw = _good_pathway(se_multiplier=0.0)
        with pytest.raises(ValueError, match="se_multiplier"):
            pw.validate()

    def test_negative_se_multiplier(self) -> None:
        pw = _good_pathway(se_multiplier=-0.5)
        with pytest.raises(ValueError, match="se_multiplier"):
            pw.validate()

    def test_activation_threshold_zero(self) -> None:
        pw = _good_pathway(activation_threshold=0.0)
        with pytest.raises(ValueError, match="activation_threshold"):
            pw.validate()

    def test_activation_threshold_above_one(self) -> None:
        pw = _good_pathway(activation_threshold=1.5)
        with pytest.raises(ValueError, match="activation_threshold"):
            pw.validate()

    def test_activation_threshold_none_is_ok(self) -> None:
        """None = not set yet → should pass validation."""
        pw = _good_pathway(activation_threshold=None)
        pw.validate()  # Should not raise


# ═══════════════════════════════════════════════════════════════
#  Functional Update Pattern (dataclasses.replace)
# ═══════════════════════════════════════════════════════════════


class TestFunctionalUpdate:
    """Verify dataclasses.replace() works for frozen type updates."""

    def test_replace_edge_ids(self) -> None:
        pw = _good_pathway(edge_ids=())
        pw2 = replace(pw, edge_ids=("E1", "E2"), is_complete=True)
        assert pw2.edge_ids == ("E1", "E2")
        assert pw2.is_complete is True
        # Original unchanged
        assert pw.edge_ids == ()
        assert pw.is_complete is True

    def test_replace_preserves_other_fields(self) -> None:
        pw = _good_pathway()
        pw2 = replace(pw, pathway_label="Updated Label")
        assert pw2.pathway_label == "Updated Label"
        assert pw2.pathway_id == pw.pathway_id
        assert pw2.tier == pw.tier
        assert pw2.entry_node_ids == pw.entry_node_ids

    def test_replaced_object_is_independent(self) -> None:
        pw = _good_pathway()
        pw2 = replace(pw, pathway_id="PW_NEW")
        assert pw.pathway_id == "PW_TEST"
        assert pw2.pathway_id == "PW_NEW"
