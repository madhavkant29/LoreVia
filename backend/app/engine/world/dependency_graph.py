from __future__ import annotations


def build_dependency_graph(elements: list[dict]) -> list[dict]:
    graph: list[dict] = []
    for element in elements:
        dependencies = element.get("dependencies") or []
        graph.append(
            {
                "id": str(element.get("id") or element.get("name") or ""),
                "name": str(element.get("name") or ""),
                "element_type": str(element.get("element_type") or "culture"),
                "dependencies": dependencies if isinstance(dependencies, list) else [],
            }
        )
    return graph
