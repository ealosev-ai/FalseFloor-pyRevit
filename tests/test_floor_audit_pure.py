# -*- coding: utf-8 -*-
"""Pure tests for floor_audit helper logic."""

from floor_audit import (
    ZONE_SOURCE,
    build_owner_index,
    extract_zone_ids,
    find_conflicting_owners,
    parse_raw_id_string,
    summarize_ids,
    summarize_unowned_instances,
    summarize_zone_membership,
)
from rf_param_schema import RFParams as P


def test_parse_raw_id_string_tracks_invalid_tokens():
    ids, invalid = parse_raw_id_string("1; x ; 2 ; ;bad;3")
    assert ids == [1, 2, 3]
    assert invalid == ["x", "bad"]


def test_summarize_ids_preserves_order_and_duplicates():
    summary = summarize_ids([5, 2, 5, 7, 2, 2])
    assert summary["count"] == 6
    assert summary["unique_ids"] == (5, 2, 7)
    assert summary["duplicate_ids"] == (2, 5)


def test_extract_zone_ids_reports_invalid_values():
    ids, invalid = extract_zone_ids(
        {
            "zones": [
                {"upper_ids": [1, "2"], "lower_ids": ["x"], "support_ids": [3]},
                "bad-zone",
            ]
        }
    )
    assert ids == [1, 2, 3]
    assert "lower_ids=x" in invalid
    assert "'bad-zone'" in invalid


def test_build_owner_index_and_conflicts_include_zone_source():
    records = [
        {
            "floor_id": 10,
            "param_ids": {P.TILES_ID: [1, 2], P.SUPPORTS_ID: [7]},
            "zone_ids": [7, 8],
        },
        {
            "floor_id": 20,
            "param_ids": {P.TILES_ID: [2, 3]},
            "zone_ids": [],
        },
    ]

    owner_index = build_owner_index(records)
    conflicts = find_conflicting_owners(10, P.TILES_ID, [1, 2], owner_index)

    assert owner_index[8] == [{"floor_id": 10, "source": ZONE_SOURCE}]
    assert 2 in conflicts
    assert conflicts[2] == [{"floor_id": 20, "source": P.TILES_ID}]


def test_summarize_unowned_instances():
    owner_index = {
        1: [{"floor_id": 10, "source": P.TILES_ID}],
        2: [{"floor_id": 10, "source": P.STRINGERS_TOP_ID}],
    }
    unowned = summarize_unowned_instances(
        {
            "RF_Tile": [1, 4, 4],
            "RF_Stringer": [2, 3],
            "RF_Support": [],
        },
        owner_index,
    )
    assert unowned == {"RF_Stringer": (3,), "RF_Tile": (4,)}


def test_summarize_zone_membership_flags_untracked_zone_ids():
    untracked = summarize_zone_membership(
        zone_ids=[10, 11, 12],
        top_ids=[10],
        bottom_ids=[11],
        support_ids=[],
    )
    assert untracked == (12,)
