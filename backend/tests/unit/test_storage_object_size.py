from app.core import storage


def test_remote_storage_client_has_bounded_timeouts_and_retries(monkeypatch) -> None:
    captured = {}

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(storage.boto3, "client", fake_client)

    storage._get_s3_client()

    config = captured["config"]
    assert captured["service_name"] == "s3"
    assert config.connect_timeout == 5
    assert config.read_timeout == 30
    assert config.retries["mode"] == "standard"
    assert config.retries["total_max_attempts"] == 4


def test_get_object_size_uses_local_file_stat(monkeypatch, tmp_path) -> None:
    source = tmp_path / "source.txt"
    source.write_bytes(b"12345")
    monkeypatch.setattr(storage, "is_local_storage", lambda: True)
    monkeypatch.setattr(storage, "_local_path", lambda _key: source)
    assert storage.get_object_size("books/source.txt") == 5


def test_get_object_size_uses_remote_head(monkeypatch) -> None:
    class _Client:
        def head_object(self, **_kwargs):
            return {"ContentLength": 42}

    monkeypatch.setattr(storage, "is_local_storage", lambda: False)
    monkeypatch.setattr(storage, "_get_s3_client", lambda: _Client())
    assert storage.get_object_size("books/source.txt") == 42
