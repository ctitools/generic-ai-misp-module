from misp_compare import misp_event_diff

BASE = {
    "uuid": "u",
    "info": "x",
    "timestamp": "1780658606",
    "Attribute": [{"type": "text", "value": "v", "to_ids": False}],
}


def test_identical_dicts_have_no_diff() -> None:
    assert misp_event_diff(BASE, BASE) == []


def test_empty_values_and_numeric_strings_and_whitespace_are_ignored() -> None:
    processed = {
        "uuid": "u",
        "info": "  x ",
        "timestamp": 1780658606,
        "Attribute": [{"type": "text", "value": "v", "to_ids": False, "Galaxy": []}],
        "first_seen": None,
        "comment": "",
    }
    assert misp_event_diff(BASE, processed) == []


def test_datetimes_compare_by_value() -> None:
    a = {
        "Attribute": [{"value": "2025-07-08T16:58:05.000000+0000"}],
        "created": "2026-06-01 08:10:24",
    }
    b = {
        "Attribute": [{"value": "2025-07-08T16:58:05+00:00"}],
        "created": "2026-06-01T08:10:24+00:00",
    }
    assert misp_event_diff(a, b) == []
    assert misp_event_diff(a, {"Attribute": [{"value": "2025-07-08T16:58:06+00:00"}]}) != []


def test_allowlisted_paths_are_tolerated() -> None:
    a = {"Galaxy": [{"GalaxyCluster": [{"value": "c", "distribution": "3"}]}]}
    b = {"Galaxy": [{"GalaxyCluster": [{"value": "c", "distribution": "0"}]}]}
    assert misp_event_diff(a, b) == []


def test_real_changes_are_reported() -> None:
    changed = {**BASE, "Attribute": [{"type": "text", "value": "other", "to_ids": False}]}
    assert misp_event_diff(BASE, changed) == ["/Attribute[0]/value: 'v' -> 'other'"]

    dropped = {k: v for k, v in BASE.items() if k != "timestamp"}
    assert misp_event_diff(BASE, dropped) == ["/timestamp: missing after processing"]

    fewer = {**BASE, "Attribute": []}
    assert misp_event_diff(BASE, fewer) == ["/Attribute: missing after processing"]

    added = {**BASE, "Object": [{"name": "file"}]}
    assert misp_event_diff(BASE, added) == ["/Object: added by processing"]
