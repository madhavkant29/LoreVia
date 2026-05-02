from pathlib import Path

from app.core import storage


def test_ensure_local_storage_permissions_relabels_existing_tree(monkeypatch, tmp_path):
    storage_root = tmp_path / "storage"
    nested_dir = storage_root / "local-dev" / "covers" / "existing"
    nested_dir.mkdir(parents=True)
    nested_file = nested_dir / "cover.png"
    nested_file.write_bytes(b"cover-bytes")

    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", f"file://{storage_root.as_posix()}", raising=False)
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "local-dev", raising=False)
    monkeypatch.setattr(storage.os, "geteuid", lambda: 0)
    monkeypatch.setattr(storage, "_storage_owner_ids", lambda: (10001, 10001))

    chowned: list[Path] = []
    chmodded: list[tuple[Path, int]] = []

    def _fake_chown(path, uid, gid):
        chowned.append(Path(path))

    def _fake_chmod(path, mode):
        chmodded.append((Path(path), mode))

    monkeypatch.setattr(storage.os, "chown", _fake_chown)
    monkeypatch.setattr(storage.os, "chmod", _fake_chmod)

    storage.ensure_local_storage_permissions()

    assert storage_root in chowned
    assert storage_root / "local-dev" in chowned
    assert storage_root / "local-dev" / "covers" in chowned
    assert nested_dir in chowned
    assert nested_file in chowned
    assert (storage_root, 0o775) in chmodded
    assert (storage_root / "local-dev", 0o775) in chmodded
    assert (storage_root / "local-dev" / "covers", 0o775) in chmodded
    assert (nested_dir, 0o775) in chmodded
    assert (nested_file, 0o664) in chmodded


def test_ensure_local_storage_permissions_is_noop_for_non_root(monkeypatch, tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", f"file://{storage_root.as_posix()}", raising=False)
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "local-dev", raising=False)
    monkeypatch.setattr(storage.os, "geteuid", lambda: 10001)

    called = False

    def _fake_chown(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(storage.os, "chown", _fake_chown)

    storage.ensure_local_storage_permissions()

    assert called is False
