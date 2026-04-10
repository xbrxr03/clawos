# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna — Graph Builder.
Extracts entities and relationships from text chunks → builds NetworkX DiGraph.
Runs community detection (Leiden) → assigns color clusters.
Runs PageRank → assigns importance scores (drives node size in 3D view).
"""
import hashlib
import json
import logging
import re
from typing import Optional

log = logging.getLogger("braind.graph")

# Community color palette — 15 distinct colors for node clusters
COMMUNITY_COLORS = [
    "#7c6af5",  # violet
    "#f97316",  # orange
    "#06b6d4",  # cyan
    "#84cc16",  # lime
    "#f43f5e",  # rose
    "#8b5cf6",  # purple
    "#14b8a6",  # teal
    "#f59e0b",  # amber
    "#3b82f6",  # blue
    "#10b981",  # emerald
    "#ec4899",  # pink
    "#64748b",  # slate
    "#dc2626",  # red
    "#0891b2",  # sky
    "#7c3aed",  # indigo
]


def _node_id(label: str) -> str:
    """Stable ID from label string."""
    return hashlib.md5(label.strip().lower().encode()).hexdigest()[:12]


def extract_triples_heuristic(text: str, source_file: str = "") -> list[dict]:
    """
    Fast heuristic triple extraction — no LLM required.
    Extracts Subject → Predicate → Object patterns from text.
    Used as fallback when Ollama is unavailable.
    """
    triples = []
    sentences = re.split(r'[.!?\n]+', text)

    # Relationship keywords → predicate labels
    PREDICATES = {
        r'\bis\s+a\b': "is_a",
        r'\bare\s+a\b': "is_a",
        r'\bcontains?\b': "contains",
        r'\binclude[sd]?\b': "includes",
        r'\buse[sd]?\b': "uses",
        r'\bdepends?\s+on\b': "depends_on",
        r'\bextends?\b': "extends",
        r'\bimplements?\b': "implements",
        r'\bcall[sd]?\b': "calls",
        r'\bcreates?\b': "creates",
        r'\breturns?\b': "returns",
        r'\bconnects?\s+to\b': "connects_to",
        r'\brelates?\s+to\b': "relates_to",
        r'\bcauses?\b': "causes",
        r'\benables?\b': "enables",
        r'\brequires?\b': "requires",
    }

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue

        for pattern, predicate in PREDICATES.items():
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                # Split on the predicate
                parts = re.split(pattern, sentence, maxsplit=1, flags=re.IGNORECASE)
                if len(parts) == 2:
                    subj = _clean_entity(parts[0])
                    obj = _clean_entity(parts[1])
                    if subj and obj and subj != obj:
                        triples.append({
                            "subject": subj,
                            "predicate": predicate,
                            "object": obj,
                            "source": source_file,
                            "method": "heuristic",
                        })

    return triples[:20]  # Cap per chunk to avoid noise


def extract_triples_llm(text: str, source_file: str = "") -> list[dict]:
    """
    LLM-based triple extraction using Ollama.
    Falls back to heuristic on failure.
    Returns list of {subject, predicate, object, source} dicts.
    """
    try:
        import requests
        from clawos_core.config import get

        model = get("model.chat", "qwen2.5:7b")
        host = get("model.host", "http://localhost:11434")

        prompt = (
            "Extract knowledge graph triples from this text. "
            "Output JSON array only. Each item: {\"s\": \"subject\", \"p\": \"predicate\", \"o\": \"object\"}\n"
            "Rules: use short noun phrases. Max 15 triples. Relationships must be meaningful.\n"
            "Text:\n" + text[:600] + "\n\nJSON:"
        )

        response = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 400, "temperature": 0.1}
            },
            timeout=20,
        )

        if response.status_code == 200:
            raw = response.json().get("response", "[]").strip()
            # Find JSON array in response
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                try:
                    from clawos_core.jsonx import safe_loads
                    items = safe_loads(match.group())
                    if isinstance(items, list):
                        triples = []
                        for item in items[:15]:
                            if isinstance(item, dict):
                                s = _clean_entity(str(item.get("s", "")))
                                p = _clean_entity(str(item.get("p", "")))
                                o = _clean_entity(str(item.get("o", "")))
                                if s and p and o and s != o:
                                    triples.append({
                                        "subject": s, "predicate": p, "object": o,
                                        "source": source_file, "method": "llm",
                                    })
                        return triples
                except Exception:
                    pass
    except Exception as e:
        log.debug(f"LLM triple extraction failed: {e}")

    return extract_triples_heuristic(text, source_file)


def _clean_entity(text: str) -> str:
    """Normalize entity text — strip punctuation, limit length."""
    text = re.sub(r'[^\w\s\-/]', '', text.strip())
    text = re.sub(r'\s+', ' ', text).strip()
    # Take first meaningful chunk if too long
    words = text.split()
    if len(words) > 6:
        text = ' '.join(words[:6])
    return text[:60] if len(text) > 2 else ""


class BrainGraph:
    """
    In-memory NetworkX DiGraph with community detection and PageRank.
    Thread-safe via a simple lock.
    """

    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._graph = None
        self._community_map: dict[str, int] = {}  # node_id → community_id
        self._pagerank: dict[str, float] = {}
        self._dirty = False
        self._init_graph()

    def _init_graph(self):
        try:
            import networkx as nx
            self._graph = nx.DiGraph()
        except ImportError:
            log.warning("networkx not installed — Kizuna graph features limited. pip install networkx")
            self._graph = None

    @property
    def g(self):
        return self._graph

    def add_triple(self, subject: str, predicate: str, obj: str,
                   source: str = "", agent_added: bool = False):
        """Add a subject→object edge with predicate label."""
        if self._graph is None:
            return

        s_id = _node_id(subject)
        o_id = _node_id(obj)

        with self._lock:
            if not self._graph.has_node(s_id):
                self._graph.add_node(s_id, label=subject, sources=[source],
                                     agent_added=agent_added, mention_count=1)
            else:
                node = self._graph.nodes[s_id]
                node["mention_count"] = node.get("mention_count", 1) + 1
                if source and source not in node.get("sources", []):
                    node.setdefault("sources", []).append(source)

            if not self._graph.has_node(o_id):
                self._graph.add_node(o_id, label=obj, sources=[source],
                                     agent_added=agent_added, mention_count=1)
            else:
                node = self._graph.nodes[o_id]
                node["mention_count"] = node.get("mention_count", 1) + 1

            self._graph.add_edge(s_id, o_id, predicate=predicate,
                                  source=source, agent_added=agent_added)
            self._dirty = True

    def add_triples(self, triples: list[dict], agent_added: bool = False):
        """Bulk add triples."""
        for t in triples:
            self.add_triple(
                t["subject"], t["predicate"], t["object"],
                source=t.get("source", ""),
                agent_added=agent_added,
            )

    def compute_communities(self):
        """Run Leiden community detection. Falls back to greedy modularity."""
        if self._graph is None or len(self._graph.nodes) < 2:
            return

        try:
            import networkx.algorithms.community as nxc
            import networkx as nx
            # Use undirected version for community detection
            ug = self._graph.to_undirected()

            try:
                # Leiden via cdlib
                from cdlib import algorithms
                result = algorithms.leiden(ug)
                communities = result.communities
            except (ImportError, Exception):
                # Fallback: Louvain/greedy modularity
                try:
                    communities = list(nxc.greedy_modularity_communities(ug))
                except Exception:
                    communities = [list(self._graph.nodes)]

            self._community_map = {}
            for i, community in enumerate(communities):
                for node_id in community:
                    self._community_map[str(node_id)] = i % len(COMMUNITY_COLORS)

            log.debug(f"Community detection: {len(communities)} communities, {len(self._graph.nodes)} nodes")

        except Exception as e:
            log.debug(f"Community detection failed: {e}")
            # Assign all to community 0
            self._community_map = {n: 0 for n in self._graph.nodes}

    def compute_pagerank(self):
        """Run PageRank to score node importance."""
        if self._graph is None or len(self._graph.nodes) < 1:
            return
        try:
            import networkx as nx
            if self._graph.number_of_edges() > 0:
                self._pagerank = nx.pagerank(self._graph, alpha=0.85)
            else:
                self._pagerank = {n: 1.0 / len(self._graph.nodes)
                                  for n in self._graph.nodes}
        except Exception as e:
            log.debug(f"PageRank failed: {e}")
            self._pagerank = {}

    def recompute(self):
        """Recompute communities and PageRank after batch adds."""
        self.compute_communities()
        self.compute_pagerank()
        self._dirty = False

    def to_render_dict(self) -> dict:
        """
        Export graph as {nodes, links} for react-force-graph-3d.
        Nodes include: id, label, color, size, community, agent_added, sources
        Links include: source, target, predicate
        """
        if self._graph is None:
            return {"nodes": [], "links": []}

        nodes = []
        for node_id, data in self._graph.nodes(data=True):
            community_idx = self._community_map.get(str(node_id), 0)
            color = COMMUNITY_COLORS[community_idx % len(COMMUNITY_COLORS)]

            # PageRank → node size (4–20px range)
            pr = self._pagerank.get(node_id, 0.01)
            max_pr = max(self._pagerank.values()) if self._pagerank else 1.0
            normalized = pr / max_pr if max_pr > 0 else 0.01
            size = 4 + int(normalized * 16)  # 4–20

            nodes.append({
                "id": node_id,
                "label": data.get("label", node_id),
                "color": color,
                "size": size,
                "community": community_idx,
                "agent_added": data.get("agent_added", False),
                "sources": data.get("sources", []),
                "mention_count": data.get("mention_count", 1),
                "pagerank": round(pr, 6),
            })

        links = []
        for src, tgt, data in self._graph.edges(data=True):
            links.append({
                "source": src,
                "target": tgt,
                "predicate": data.get("predicate", "relates_to"),
                "agent_added": data.get("agent_added", False),
            })

        return {"nodes": nodes, "links": links}

    def node_detail(self, node_id: str) -> Optional[dict]:
        """Full detail for a single node including neighbors."""
        if self._graph is None or not self._graph.has_node(node_id):
            return None

        data = self._graph.nodes[node_id]
        neighbors_out = list(self._graph.successors(node_id))
        neighbors_in = list(self._graph.predecessors(node_id))

        related = []
        for n in neighbors_out[:10]:
            nd = self._graph.nodes.get(n, {})
            edge = self._graph.edges.get((node_id, n), {})
            related.append({
                "id": n, "label": nd.get("label", n),
                "direction": "out", "predicate": edge.get("predicate", ""),
            })
        for n in neighbors_in[:10]:
            nd = self._graph.nodes.get(n, {})
            edge = self._graph.edges.get((n, node_id), {})
            related.append({
                "id": n, "label": nd.get("label", n),
                "direction": "in", "predicate": edge.get("predicate", ""),
            })

        return {
            "id": node_id,
            "label": data.get("label", node_id),
            "sources": data.get("sources", []),
            "agent_added": data.get("agent_added", False),
            "mention_count": data.get("mention_count", 1),
            "community": self._community_map.get(str(node_id), 0),
            "color": COMMUNITY_COLORS[self._community_map.get(str(node_id), 0) % len(COMMUNITY_COLORS)],
            "pagerank": round(self._pagerank.get(node_id, 0.0), 6),
            "related": related,
            "degree": self._graph.degree(node_id),
        }

    def find_gaps(self) -> list[dict]:
        """Find nodes and clusters with no cross-community connections."""
        if self._graph is None:
            return []

        gaps = []
        # Isolated nodes (degree 0 or 1)
        for node_id, data in self._graph.nodes(data=True):
            if self._graph.degree(node_id) <= 1:
                gaps.append({
                    "type": "isolated_node",
                    "node_id": node_id,
                    "label": data.get("label", node_id),
                    "message": f"'{data.get('label', node_id)}' has no connections",
                })

        # Small isolated subgraphs
        try:
            import networkx as nx
            ug = self._graph.to_undirected()
            for component in nx.connected_components(ug):
                if len(component) <= 3:
                    labels = [self._graph.nodes[n].get("label", n) for n in component]
                    gaps.append({
                        "type": "isolated_cluster",
                        "nodes": list(component),
                        "labels": labels,
                        "message": f"Isolated cluster: {', '.join(labels[:3])}",
                    })
        except Exception:
            pass

        return gaps[:20]

    def graph_rag_context(self, node_ids: list[str], hops: int = 2) -> list[str]:
        """
        Return labels of nodes within `hops` of the given node_ids.
        Used for GraphRAG context assembly.
        """
        if self._graph is None:
            return []

        import networkx as nx
        context_nodes = set(node_ids)
        frontier = set(node_ids)

        for _ in range(hops):
            next_frontier = set()
            for nid in frontier:
                if self._graph.has_node(nid):
                    next_frontier.update(self._graph.successors(nid))
                    next_frontier.update(self._graph.predecessors(nid))
            frontier = next_frontier - context_nodes
            context_nodes.update(frontier)

        labels = []
        for nid in context_nodes:
            if self._graph.has_node(nid):
                labels.append(self._graph.nodes[nid].get("label", nid))
        return labels[:30]

    def stats(self) -> dict:
        if self._graph is None:
            return {"node_count": 0, "edge_count": 0, "community_count": 0}
        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "community_count": len(set(self._community_map.values())),
        }
