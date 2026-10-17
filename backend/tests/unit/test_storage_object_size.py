import io

from app.core import storage


def test_remote_storage_client_has_bounded_timeouts_and_retries(monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(storage, "_S3_CLIENT", None)
    monkeypatch.setattr(storage, "_S3_CLIENT_CACHE_KEY", None)

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


def test_remote_storage_client_is_reused_per_process_and_config(monkeypatch) -> None:
    clients = [object(), object()]
    calls = 0
    monkeypatch.setattr(storage, "_S3_CLIENT", None)
    monkeypatch.setattr(storage, "_S3_CLIENT_CACHE_KEY", None)

    def fake_client(_service_name, **_kwargs):
        nonlocal calls
        client = clients[calls]
        calls += 1
        return client

    monkeypatch.setattr(storage.boto3, "client", fake_client)

    first = storage._get_s3_client()
    second = storage._get_s3_client()
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", "https://changed.example")
    third = storage._get_s3_client()

    assert first is second
    assert third is clients[1]
    assert calls == 2


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


def test_upload_fileobj_and_iter_chunks_do_not_require_whole_object_read(monkeypatch, tmp_path):
    destination = tmp_path / "artifact.bin"
    monkeypatch.setattr(storage, "is_local_storage", lambda: True)
    monkeypatch.setattr(storage, "_local_path", lambda _key: destination)

    source = io.BytesIO(b"abcdefghij")
    assert storage.upload_fileobj("exports/artifact.bin", source) == "exports/artifact.bin"
    assert list(storage.iter_object_chunks("exports/artifact.bin", chunk_size=64 * 1024)) == [
        b"abcdefghij"
    ]


def test_public_text_upload_rejects_non_public_prefix():
    try:
        storage.upload_public_text_asset("books/private.txt", "no")
    except ValueError as exc:
        assert "public-assets" in str(exc)
    else:
        raise AssertionError("private prefix must not be accepted for direct public assets")
