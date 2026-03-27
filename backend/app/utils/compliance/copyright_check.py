import httpx


async def check_isbn(isbn: str) -> dict:
    if not isbn:
        return {"found": False}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://openlibrary.org/api/books",
                params={"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"},
            )
            data = resp.json()
            key = f"ISBN:{isbn}"
            if key in data:
                entry = data[key]
                return {
                    "found": True,
                    "title": entry.get("title"),
                    "authors": [a["name"] for a in entry.get("authors", [])],
                    "requires_disclaimer": True,
                }
    except Exception:
        pass
    return {"found": False}
