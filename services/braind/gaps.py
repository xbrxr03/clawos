# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna — Gap Detection.
Finds isolated nodes and clusters that could be connected.
"""
import logging

log = logging.getLogger("braind.gaps")


def find_gaps(graph_builder) -> list[dict]:
    """
    Return gap analysis from the graph.
    Types: isolated_node, isolated_cluster, cross_community_opportunity
    """
    base_gaps = graph_builder.find_gaps()

    # Try to identify cross-community connection opportunities
    g = graph_builder.g
    if g is None or g.number_of_nodes() < 4:
        return base_gaps

    try:
        import networkx as nx
        community_map = graph_builder._community_map

        # Find communities that share many keywords but no edges
        community_labels: dict[int, list[str]] = {}
        for node_id, data in g.nodes(data=True):
            c = community_map.get(str(node_id), 0)
            label = data.get("label", "").lower()
            community_labels.setdefault(c, []).append(label)

        # Look for word overlap between isolated communities
        communities = list(community_labels.keys())
        for i in range(len(communities)):
            for j in range(i + 1, len(communities)):
                c1, c2 = communities[i], communities[j]
                words1 = set(' '.join(community_labels[c1]).split())
                words2 = set(' '.join(community_labels[c2]).split())
                overlap = words1 & words2 - {'the', 'a', 'an', 'is', 'are', 'of', 'to', 'in'}
                if len(overlap) >= 2:
                    base_gaps.append({
                        "type": "cross_community_opportunity",
                        "communities": [c1, c2],
                        "shared_concepts": list(overlap)[:5],
                        "message": (
                            f"Communities {c1} and {c2} share concepts "
                            f"({', '.join(list(overlap)[:3])}) but are not connected"
                        ),
                    })
    except Exception as e:
        log.debug(f"Cross-community analysis failed: {e}")

    return base_gaps[:25]
