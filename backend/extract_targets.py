import re

files = {
    "reader": "tests/unit/test_reader_routes.py",
    "books": "tests/unit/test_books_routes.py",
    "access_control": "tests/integration/test_access_control.py",
}

for name, path in files.items():
    with open(path) as f:
        content = f.read()

    targets = set()
    for m in re.finditer(r'monkeypatch\.setattr\(\s*(\w+),\s*"([^"]+)"', content):
        targets.add(m.group(2))
    for m in re.finditer(r"monkeypatch\.setattr\(\s*(\w+),\s*'([^']+)'", content):
        targets.add(m.group(2))

    print(f"=== {name} monkeypatch targets ({len(targets)}) ===")
    for t in sorted(targets):
        print(f"  {t}")
    print()
