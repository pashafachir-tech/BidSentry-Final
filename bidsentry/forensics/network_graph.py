"""Deterministic shared-entity graph construction for bid review.

Entity matches are leads for verification, not proof of common control or
collusion. Sensitive values are hashed for identity and masked in node labels.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
from collections import defaultdict
from typing import Any

try:
    import networkx as nx
except ImportError:  # Keep local deployments usable without the optional graph package.
    nx = None


ENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "NPWP": ("npwp", "tax_id", "tax_number"),
    "BANK_GUARANTEE_SERIAL": ("bank_guarantee_serial", "bank_guarantee_serials", "guarantee_serial", "guarantee_serials"),
    "BANK_BRANCH": ("bank_branch", "issuing_branch", "guarantee_issuing_branch"),
    "DIRECTOR_NAME": ("director", "directors", "director_names"),
    "SHAREHOLDER_NAME": ("shareholder", "shareholders", "shareholder_names"),
    "PHONE": ("phone", "phones", "phone_number", "phone_numbers"),
    "ADDRESS": ("address", "addresses", "physical_address", "registered_address"),
    "IP_ADDRESS": ("ip", "ips", "ip_address", "ip_addresses", "submission_ip"),
    "MAC_ADDRESS": ("mac", "mac_addresses", "submission_mac"),
    "NOTARY_REGISTRATION": ("notary_registration", "notary_registrations"),
    "VIRTUAL_OFFICE": ("virtual_office", "virtual_offices", "office_address"),
}
ENTITY_WEIGHT = {
    "NPWP": 1.0, "BANK_GUARANTEE_SERIAL": 1.0, "DIRECTOR_NAME": 1.0,
    "SHAREHOLDER_NAME": 0.9, "PHONE": 0.7, "ADDRESS": 0.55,
    "BANK_BRANCH": 0.35, "IP_ADDRESS": 0.7, "MAC_ADDRESS": 0.8,
    "NOTARY_REGISTRATION": 0.85, "VIRTUAL_OFFICE": 0.65,
}
_ALIASES = {alias: kind for kind, aliases in ENTITY_FIELDS.items() for alias in aliases}


def build_entity_graph(vendors: list[dict[str, Any]]) -> dict[str, Any]:
    """Return Cytoscape/D3-ready nodes, edges, alerts, and cluster weights."""
    nodes: dict[str, dict[str, Any]] = {}
    vendors_by_entity: dict[str, set[str]] = defaultdict(set)
    vendor_names: dict[str, str] = {}
    entity_values: dict[str, tuple[str, str]] = {}
    evidence_sources: dict[str, set[str]] = defaultdict(set)
    for vendor in vendors:
        vendor_id = str(vendor.get("vendor_id") or vendor.get("vendor_name") or "vendor-unknown")
        vendor_name = str(vendor.get("vendor_name") or vendor_id)
        vendor_names[vendor_id] = vendor_name
        vendor_node_id = f"vendor:{vendor_id}"
        nodes[vendor_node_id] = {"data": {"id": vendor_node_id, "label": vendor_name, "kind": "vendor", "vendor_id": vendor_id}}
        entities = _extract_entities(vendor)
        for entity_type, value, source in entities:
            normalized = _normalize(entity_type, value)
            if not normalized:
                continue
            value_hash = hashlib.sha256(f"{entity_type}|{normalized}".encode("utf-8")).hexdigest()
            entity_id = f"entity:{entity_type.casefold()}:{value_hash[:16]}"
            entity_values[entity_id] = (entity_type, normalized)
            vendors_by_entity[entity_id].add(vendor_id)
            evidence_sources[entity_id].add(source)
            nodes.setdefault(entity_id, {"data": {
                "id": entity_id,
                "label": _masked_label(entity_type, normalized),
                "kind": "shared_entity",
                "entity_type": entity_type,
                "match_hash": value_hash,
                "weight": ENTITY_WEIGHT.get(entity_type, 0.5),
            }})

    edges: list[dict[str, Any]] = []
    edge_ids: set[tuple[str, str]] = set()
    for entity_id, linked_vendors in sorted(vendors_by_entity.items()):
        for vendor_id in sorted(linked_vendors):
            source_id = f"vendor:{vendor_id}"
            pair = (source_id, entity_id)
            if pair not in edge_ids:
                edge_ids.add(pair)
                edges.append({"data": {"id": f"edge:{len(edges) + 1}", "source": source_id, "target": entity_id, "kind": "shares_entity", "evidence_sources": sorted(evidence_sources[entity_id])}})

    vendor_links: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entity_id, linked in vendors_by_entity.items():
        if len(linked) < 2:
            continue
        ordered = sorted(linked)
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                vendor_links[(first, second)].append(entity_id)

    graph = None
    if nx is not None:
        graph = nx.Graph()
        graph.add_nodes_from(vendor_names)
        graph.add_edges_from(vendor_links)
        clusters = [sorted(component) for component in nx.connected_components(graph)]
    else:
        clusters = _components(sorted(vendor_names), vendor_links)
    clusters.sort(key=lambda group: (group[0] if group else "", len(group)))
    cluster_weights: list[dict[str, Any]] = []
    vendor_cluster: dict[str, int] = {}
    for index, members in enumerate(clusters, 1):
        weight = sum(
            ENTITY_WEIGHT.get(entity_values[entity_id][0], 0.5)
            for entity_id, linked in vendors_by_entity.items()
            if len(linked) > 1 and set(members).intersection(linked)
        )
        normalized_weight = round(weight / max(1, len(members) - 1), 4) if len(members) > 1 else 0.0
        cluster = {"cluster_id": f"cluster-{index:03d}", "vendor_ids": members, "vendor_names": [vendor_names[item] for item in members], "cluster_weight": normalized_weight, "shared_entity_count": sum(1 for linked in vendors_by_entity.values() if len(linked) > 1 and set(members).intersection(linked))}
        cluster_weights.append(cluster)
        for vendor_id in members:
            vendor_cluster[vendor_id] = index
            node_id = f"vendor:{vendor_id}"
            nodes[node_id]["data"]["cluster_id"] = cluster["cluster_id"]
            nodes[node_id]["data"]["cluster_weight"] = normalized_weight

    alerts = []
    for (first, second), shared in sorted(vendor_links.items()):
        alerts.append({
            "signal": "SHARED_ENTITY_NETWORK",
            "vendors": [vendor_names[first], vendor_names[second]],
            "vendor_ids": [first, second],
            "shared_entities": [
                {"entity_type": entity_values[entity_id][0], "label": nodes[entity_id]["data"]["label"], "match_hash": nodes[entity_id]["data"]["match_hash"], "weight": ENTITY_WEIGHT.get(entity_values[entity_id][0], 0.5)}
                for entity_id in sorted(shared)
            ],
            "signal_weight": round(sum(ENTITY_WEIGHT.get(entity_values[item][0], 0.5) for item in shared), 4),
            "interpretation": "Kecocokan identitas bersama perlu diperiksa ke sumber primer dan tidak membuktikan persekongkolan.",
        })
    return {
        "status": "screened" if len(vendor_names) > 1 else "insufficient_comparison_data",
        "graph": {"nodes": list(nodes.values()), "edges": edges},
        "clusters": cluster_weights,
        "cluster_weights": {item["cluster_id"]: item["cluster_weight"] for item in cluster_weights},
        "alerts": alerts,
        "entity_resolution_method": "Exact match after type-specific deterministic normalization; no fuzzy name/address inference is applied.",
        "networkx_available": nx is not None,
    }


def _extract_entities(vendor: dict[str, Any]) -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    sources = [("entities", vendor.get("entities")), ("vendor_record", vendor)]
    metadata = vendor.get("document_metadata")
    if isinstance(metadata, dict):
        sources.append(("document_metadata", metadata))
    submission_log = vendor.get("submission_log")
    if isinstance(submission_log, dict):
        sources.append(("submission_log", submission_log))
    submission_logs = vendor.get("submission_logs")
    if isinstance(submission_logs, list):
        sources.extend(("submission_log", value) for value in submission_logs if isinstance(value, dict))
    for source, values in sources:
        if not isinstance(values, dict):
            continue
        for key, raw in values.items():
            entity_type = _ALIASES.get(str(key).casefold())
            if not entity_type:
                continue
            for value in _flatten(raw):
                if value.strip():
                    found.append((entity_type, value.strip(), source))
    # A shared feature is one node even if the same vendor supplied it twice.
    return list(dict.fromkeys(found))


def _flatten(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for child in value for item in _flatten(child)]
    if isinstance(value, dict):
        return [str(value.get("name") or value.get("value") or "")] if value.get("name") or value.get("value") else []
    return []


def _normalize(kind: str, value: str) -> str | None:
    text = value.strip()
    if kind in {"NPWP", "PHONE"}:
        digits = re.sub(r"\D", "", text)
        return digits if len(digits) >= (10 if kind == "NPWP" else 7) else None
    if kind == "MAC_ADDRESS":
        compact = re.sub(r"[^0-9a-f]", "", text.casefold())
        return ":".join(compact[index:index + 2] for index in range(0, len(compact), 2)) if len(compact) == 12 else None
    if kind == "IP_ADDRESS":
        try:
            return ipaddress.ip_address(text).compressed
        except ValueError:
            return None
    normalized = " ".join(re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).split())
    return normalized or None


def _masked_label(kind: str, value: str) -> str:
    if kind in {"NPWP", "PHONE"}:
        return f"{kind} ••••{value[-4:]}"
    if kind == "BANK_GUARANTEE_SERIAL":
        return f"{kind} ••••{value[-4:]}"
    if kind == "IP_ADDRESS":
        return f"{kind} {value.rsplit('.', 1)[0]}.•••" if "." in value else f"{kind} •••"
    if kind == "MAC_ADDRESS":
        return f"{kind} ••••{value[-5:]}"
    if kind in {"DIRECTOR_NAME", "SHAREHOLDER_NAME"}:
        return f"{kind} #{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"
    return f"{kind} #{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _components(vendor_ids: list[str], links: dict[tuple[str, str], list[str]]) -> list[list[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for first, second in links:
        adjacency[first].add(second)
        adjacency[second].add(first)
    remaining = set(vendor_ids)
    result: list[list[str]] = []
    while remaining:
        start = min(remaining)
        stack, component = [start], set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        remaining -= component
        result.append(sorted(component))
    return result
