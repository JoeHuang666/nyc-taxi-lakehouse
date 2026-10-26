import json
import numpy as np
import pandas as pd
import pytest
from taxi_project.lakehouse import calendar
from taxi_project.features import reference_features, FEATURES
from taxi_project.model import metrics
from taxi_project.common import dependency_hash, json_write, promote, writer_lock

def history():
    hours = calendar().hour_key.iloc[:400]
    return pd.DataFrame({"zone_id": 1, "hour_key": hours, "trip_count": np.arange(len(hours), dtype=float)})

def test_calendar_dst():
    c = calendar()
    assert len(c) == 2183
    spring = c[c.local_date == "2024-03-10"]
    assert len(spring) == 23 and 2 not in spring.local_hour.values
    assert np.all(np.diff(c.hour_key) == 1)

def test_lags_prefix_and_future():
    h = history()
    x = reference_features(h)
    assert x.iloc[200].lag_1 == 199
    assert x.iloc[200].lag_168 == 32
    assert x.iloc[200].rolling_24 == np.mean(np.arange(176,200))
    target = h.hour_key.iloc[200]
    prefix = h[h.hour_key <= target].copy()
    prefix.loc[prefix.hour_key == target, "trip_count"] = np.nan
    p = reference_features(prefix)
    np.testing.assert_allclose(p.iloc[-1][FEATURES].astype(float), x.iloc[200][FEATURES].astype(float))
    h.loc[h.hour_key >= target, "trip_count"] = 999999
    mutated = reference_features(h)
    pd.testing.assert_frame_equal(x.loc[x.hour_key <= target, FEATURES], mutated.loc[mutated.hour_key <= target, FEATURES])

def test_missing_hour_rejected():
    with pytest.raises(ValueError, match="dense"):
        reference_features(history().drop(index=100))

def test_dst_weekly_fallback():
    c = calendar()
    h = pd.DataFrame({"zone_id": 1, "hour_key": c.hour_key, "trip_count": np.arange(len(c))})
    x = reference_features(h)
    row = x[(x.local_date == "2024-03-17") & (x.local_hour == 2)].iloc[0]
    assert row.dst_fallback == 1 and row.baseline_pred == row.lag_168
    normal = x[(x.local_date == "2024-03-10") & (x.local_hour == 3)].iloc[0]
    assert normal.dst_fallback == 0
    assert normal.baseline_pred == h.loc[h.hour_key == normal.hour_key-167, "trip_count"].iloc[0]

def test_metric_math():
    assert metrics([0, 2], [1, 1])["mae"] == 1
    assert metrics([0, 2], [1, 1])["wape"] == 1
    assert metrics([0, 0], [1, 1])["wape"] is None
    with pytest.raises(ValueError):
        metrics([1], [float("nan")])

def test_release_failure_preserves_pointer(tmp_path):
    pointer = tmp_path / "current_release.json"
    json_write(pointer, {"release_id": "old"})
    release = tmp_path / "new"
    release.mkdir()
    with pytest.raises(ValueError):
        promote(release, tmp_path)
    assert json.loads(pointer.read_text())["release_id"] == "old"
    json_write(release / "release_manifest.json", {"status": "FAILED"})
    with pytest.raises(ValueError):
        promote(release, tmp_path)
    assert json.loads(pointer.read_text())["release_id"] == "old"

def test_lock_excludes_second_writer(tmp_path):
    with writer_lock(tmp_path):
        with pytest.raises(FileExistsError):
            with writer_lock(tmp_path):
                pass
    assert not (tmp_path / ".writer.lock").exists()

def test_dependencies_invalidate():
    sources = {"one": {"sha256": "abc"}}
    first, _ = dependency_hash(sources, {"threshold": 1})
    changed, _ = dependency_hash(sources, {"threshold": 2})
    assert first != changed
    sources["one"]["sha256"] = "def"
    assert dependency_hash(sources, {"threshold": 1})[0] != first
