from backend.design.diversity import diversity_report, topology_signature


def model(edges, width=10):
    rooms = [
        {"id": "GF-a", "kind": "majlis", "zone": "guest"},
        {"id": "GF-b", "kind": "corridor", "zone": "family"},
        {"id": "GF-c", "kind": "kitchen", "zone": "service"},
    ]
    return {"footprint": {"width": width}, "floors": [{"id": "GF", "rooms": rooms, "openings": [
        {"kind": "door", "connects": [a, b]} for a, b in edges
    ]}]}


def test_dimension_changes_are_not_new_topologies():
    a = model([("GF-a", "EXTERIOR"), ("GF-b", "GF-c")])
    b = model([("GF-a", "EXTERIOR"), ("GF-b", "GF-c")], width=12)
    assert topology_signature(a) == topology_signature(b)
    assert diversity_report([a, b])["status"] == "REPEATED_TOPOLOGY"


def test_changed_functional_connections_are_distinct():
    a = model([("GF-a", "EXTERIOR"), ("GF-b", "GF-c")])
    b = model([("GF-b", "EXTERIOR"), ("GF-a", "GF-c")])
    assert diversity_report([a, b])["distinct_topology_count"] == 2
