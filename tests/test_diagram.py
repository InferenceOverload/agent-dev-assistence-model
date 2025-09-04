from src.tools.diagram import mermaid_repo_tree

def test_mermaid_has_graph_and_nodes():
    paths = ["client/src/App.jsx","client/src/index.js","server/index.js","README.md"]
    m = mermaid_repo_tree(paths)
    assert "graph TD" in m
    assert "client/src/App.jsx" in m
    assert m.strip().endswith(";")