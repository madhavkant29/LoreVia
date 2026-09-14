from scripts.repo_hygiene_report import _iter_source_files, _skip_directory


def test_skip_directory_rejects_generated_e2e_builds_and_dependency_trees() -> None:
    assert _skip_directory("node_modules")
    assert _skip_directory(".next-e2e-3024")
    assert _skip_directory(".docker-config")
    assert not _skip_directory("frontend")


def test_iter_source_files_prunes_generated_directories(tmp_path) -> None:
    source = tmp_path / "frontend" / "src" / "page.tsx"
    dependency = tmp_path / "frontend" / "node_modules" / "package" / "index.js"
    e2e_build = tmp_path / "frontend" / ".next-e2e-3001" / "server.js"
    source.parent.mkdir(parents=True)
    dependency.parent.mkdir(parents=True)
    e2e_build.parent.mkdir(parents=True)
    source.write_text("export default null\n", encoding="utf-8")
    dependency.write_text("generated\n", encoding="utf-8")
    e2e_build.write_text("generated\n", encoding="utf-8")

    discovered = {path.relative_to(tmp_path).as_posix() for path in _iter_source_files(tmp_path)}

    assert discovered == {"frontend/src/page.tsx"}
