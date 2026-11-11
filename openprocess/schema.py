"""Intermediate process representation.

Everything in OpenProcess flows through ProcessSpec:

    policy document -> ProcessSpec -> BPMN 2.0 XML
                                   -> governance findings
                                   -> Confluence page / Excel register

Keeping one canonical model means the LLM only ever has to produce JSON, and
every downstream artefact is deterministic. That matters for governance: the
same input must always yield the same model and the same score.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any


RACI_ROLES = ("responsible", "accountable", "consulted", "informed")

NODE_KINDS = (
    "startEvent",
    "endEvent",
    "task",
    "userTask",
    "serviceTask",
    "manualTask",
    "exclusiveGateway",
    "parallelGateway",
    "subProcess",
)

GATEWAY_KINDS = ("exclusiveGateway", "parallelGateway")
EVENT_KINDS = ("startEvent", "endEvent")
TASK_KINDS = ("task", "userTask", "serviceTask", "manualTask", "subProcess")


def slug(text: str, prefix: str = "n") -> str:
    """Stable, XML-safe id derived from a label."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    if not cleaned:
        cleaned = "unnamed"
    if cleaned[0].isdigit():
        cleaned = f"x{cleaned}"
    return f"{prefix}_{cleaned[:48]}"


@dataclass
class Raci:
    responsible: str = ""
    accountable: str = ""
    consulted: str = ""
    informed: str = ""

    def missing(self) -> list[str]:
        return [r for r in RACI_ROLES if not getattr(self, r).strip()]


@dataclass
class Node:
    id: str
    name: str
    kind: str = "task"
    lane: str = ""
    raci: Raci = field(default_factory=Raci)
    control: str = ""          # named control point, e.g. "Four-eyes approval"
    system: str = ""           # supporting IT system, e.g. "Jira Service Management"
    description: str = ""

    @property
    def is_gateway(self) -> bool:
        return self.kind in GATEWAY_KINDS

    @property
    def is_event(self) -> bool:
        return self.kind in EVENT_KINDS

    @property
    def is_task(self) -> bool:
        return self.kind in TASK_KINDS


@dataclass
class Flow:
    id: str
    source: str
    target: str
    name: str = ""             # gateway condition, e.g. "Change is standard"


@dataclass
class Lane:
    id: str
    name: str
    owner: str = ""            # accountable role for the whole lane


@dataclass
class ProcessSpec:
    key: str
    name: str
    purpose: str = ""
    scope: str = ""
    trigger: str = ""
    owner: str = ""            # process owner (a role, never a person)
    version: str = "0.1"
    source_document: str = ""
    lanes: list[Lane] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)

    # framework classification, filled in by classify.py
    pcf_id: str = ""
    pcf_name: str = ""
    pcf_confidence: float = 0.0
    itil_practice: str = ""

    # ---------- lookups ----------

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def lane(self, lane_id: str) -> Lane | None:
        return next((l for l in self.lanes if l.id == lane_id), None)

    def outgoing(self, node_id: str) -> list[Flow]:
        return [f for f in self.flows if f.source == node_id]

    def incoming(self, node_id: str) -> list[Flow]:
        return [f for f in self.flows if f.target == node_id]

    def nodes_in_lane(self, lane_id: str) -> list[Node]:
        return [n for n in self.nodes if n.lane == lane_id]

    # ---------- serialisation ----------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessSpec":
        lanes = [Lane(**l) for l in data.get("lanes", [])]
        nodes = []
        for n in data.get("nodes", []):
            n = dict(n)
            raci = n.pop("raci", {}) or {}
            if isinstance(raci, Raci):
                raci = asdict(raci)
            nodes.append(Node(raci=Raci(**{k: raci.get(k, "") for k in RACI_ROLES}), **n))
        flows = [Flow(**f) for f in data.get("flows", [])]
        known = {"lanes", "nodes", "flows"}
        scalars = {k: v for k, v in data.items() if k not in known}
        return cls(lanes=lanes, nodes=nodes, flows=flows, **scalars)

    @classmethod
    def from_json(cls, text: str) -> "ProcessSpec":
        return cls.from_dict(json.loads(text))


# JSON contract handed to the LLM. Kept here so the prompt and the parser can
# never drift apart.
EXTRACTION_SCHEMA = {
    "key": "short_snake_case_identifier",
    "name": "Verb-noun process name, e.g. 'Approve standard change'",
    "purpose": "One sentence: why this process exists",
    "scope": "One sentence: what is in and out of scope",
    "trigger": "The event that starts the process",
    "owner": "Accountable role, never a person's name",
    "lanes": [{"id": "lane_x", "name": "Role or org unit", "owner": "Accountable role"}],
    "nodes": [
        {
            "id": "n_x",
            "name": "Verb-noun label",
            "kind": "|".join(NODE_KINDS),
            "lane": "lane_x",
            "raci": {r: "Role name" for r in RACI_ROLES},
            "control": "Named control point, or empty string",
            "system": "Supporting IT system, or empty string",
            "description": "One sentence, or empty string",
        }
    ],
    "flows": [
        {
            "id": "f_x",
            "source": "n_x",
            "target": "n_y",
            "name": "Condition label — required on flows leaving a gateway",
        }
    ],
}
