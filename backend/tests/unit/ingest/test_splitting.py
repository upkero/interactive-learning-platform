"""Packing rules for deterministic document parts."""

import random

import pytest

from src.app.ingest.splitting import SplitLimits, Unit, pack_units

pytestmark = pytest.mark.unit
LIMITS = SplitLimits(target=15_000, maximum=22_000)


def units(*spec: tuple[str, int]) -> list[Unit]:
    result, offset = [], 0
    for topic_id, tokens in spec:
        result.append(Unit(topic_id, topic_id.split(".")[0], topic_id, offset, offset + tokens, tokens))
        offset += tokens
    return result


def sizes(parts: list[list[Unit]]) -> list[int]:
    return [sum(unit.tokens for unit in part) for part in parts]


def test_small_selection_is_one_part() -> None:
    assert sizes(pack_units(units(("1.1", 3_000)), LIMITS)) == [3_000]


def test_chapter_boundary_closes_filled_part() -> None:
    parts = pack_units(units(("1.1", 10_000), ("2.1", 3_000), ("2.2", 9_000)), LIMITS)
    assert sizes(parts) == [10_000, 12_000]


def test_scattered_small_topics_share_one_part() -> None:
    parts = pack_units(units(("1.2", 2_000), ("3.1", 2_500), ("5.4", 1_500)), LIMITS)
    assert [[unit.topic_id for unit in part] for part in parts] == [["1.2", "3.1", "5.4"]]


def test_small_tail_is_glued_to_previous_part() -> None:
    assert sizes(pack_units(units(("1.1", 16_000), ("1.2", 3_000)), LIMITS)) == [19_000]


def test_tail_is_not_glued_over_maximum() -> None:
    assert sizes(pack_units(units(("1.1", 20_000), ("1.2", 4_000)), LIMITS)) == [20_000, 4_000]


@pytest.mark.parametrize("seed", range(200))
def test_random_inputs_preserve_order_and_maximum(seed: int) -> None:
    rng = random.Random(seed)
    spec = [(f"{rng.randint(1, 5)}.{index}", rng.randint(200, LIMITS.maximum)) for index in range(rng.randint(1, 30))]
    source = units(*spec)
    parts = pack_units(source, LIMITS)
    assert all(size <= LIMITS.maximum for size in sizes(parts))
    assert [unit for part in parts for unit in part] == source


def test_unit_over_maximum_is_rejected() -> None:
    with pytest.raises(ValueError, match="exceeds maximum"):
        pack_units(units(("1.1", LIMITS.maximum + 1)), LIMITS)


def test_limits_derive_fill_and_tail() -> None:
    assert LIMITS.min_fill == 7_500
    assert LIMITS.tail == 5_000


@pytest.mark.parametrize(("target", "maximum"), [(0, 8), (9, 8), (1, 0)])
def test_invalid_split_limits(target: int, maximum: int) -> None:
    with pytest.raises(ValueError, match="split target <= maximum"):
        SplitLimits(target, maximum)


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ((("1.1", 5), ("2.1", 5)), [5, 5]),  # exact minimum fill closes on a chapter change
        ((("1.1", 5), ("1.2", 5)), [10]),  # exact target
        ((("1.1", 4), ("1.2", 9)), [13]),  # between target and maximum, current below minimum
        ((("1.1", 4), ("1.2", 10)), [14]),  # exact maximum
        ((("1.1", 8), ("1.2", 3)), [8, 3]),  # exact tail threshold
        ((("1.1", 12), ("1.2", 2)), [14]),  # glue to exactly the maximum
    ],
)
def test_packing_boundaries(spec: tuple[tuple[str, int], ...], expected: list[int]) -> None:
    assert sizes(pack_units(units(*spec), SplitLimits(10, 14))) == expected


@pytest.mark.parametrize(("tokens", "expected"), [((4, 4, 4), [8, 4]), ((6, 6, 0), [6, 6])])
def test_packing_checks_assembled_markdown_near_maximum(tokens: tuple[int, ...], expected: list[int]) -> None:
    source = units(*((f"1.{index}", count) for index, count in enumerate(tokens)))

    def measure(part: list[Unit]) -> int:
        return sum(unit.tokens for unit in part) + len(part) - 1

    parts = pack_units(source, SplitLimits(12, 12), measure=measure)
    assert sizes(parts) == expected
    assert all(measure(part) <= 12 for part in parts)
    assert [unit for part in parts for unit in part] == source
