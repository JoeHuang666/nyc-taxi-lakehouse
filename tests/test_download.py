import hashlib
import io
import pytest
from tools import download_data


def spec(data):
    return {"source_url": "https://d37ci6vzurychx.cloudfront.net/misc/example.csv",
            "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def test_download_verified_and_reused(tmp_path, monkeypatch):
    data = b"id,value\n1,2\n"
    monkeypatch.setattr(download_data, "urlopen", lambda *a, **k: io.BytesIO(data))
    path = download_data.download("example.csv", spec(data), tmp_path)
    assert path.read_bytes() == data
    def no_network(*args, **kwargs):
        raise AssertionError("Valid existing files must not be downloaded again")
    monkeypatch.setattr(download_data, "urlopen", no_network)
    assert download_data.download("example.csv", spec(data), tmp_path) == path
    assert not list(tmp_path.glob("*.part"))


def test_failed_download_never_publishes(tmp_path, monkeypatch):
    monkeypatch.setattr(download_data, "urlopen", lambda *a, **k: io.BytesIO(b"wrong"))
    with pytest.raises(ValueError, match="SHA-256"):
        download_data.download("example.csv", spec(b"right"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_mismatch_preserved(tmp_path):
    path = tmp_path / "example.csv"
    path.write_bytes(b"existing")
    with pytest.raises(ValueError):
        download_data.download(path.name, spec(b"expected"), tmp_path)
    assert path.read_bytes() == b"existing"
