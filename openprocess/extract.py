"""Policy document -> ProcessSpec.

Two paths:

  llm       Groq (Llama 3.3) with a strict JSON contract. Used when GROQ_API_KEY
            is set. This is the path that handles real, messy policy prose.

  rulebased A deterministic parser for structured policy text. It exists so the
            demo runs with no API key and no network, and so the test suite can
            assert on exact output. It is not a replacement for the LLM — it
            only understands the numbered-step convention used in samples/.

Whichever path runs, the output is the same ProcessSpec, so everything
downstream is identical.
"""

from __future__ import annotations

import json
import os
import re

from .schema import ProcessSpec, Node, Flow, Lane, Raci, EXTRACTION_SCHEMA, slug

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """You are a BPM analyst. You convert IT policy and procedure \
documents into a structured process model.

Rules you must follow:
- Reply with ONE JSON object and nothing else. No prose, no markdown fences.
- Label every activity in verb-noun imperative form ("Approve change request"), \
never as a noun ("Approval").
- Every activity belongs to exactly one lane. A lane is a role or organisational \
unit, never a named person.
- Every flow leaving an exclusiveGateway must carry a condition in its "name".
- Phrase exclusiveGateway labels as questions ("Risk acceptable?").
- Use only these node kinds: startEvent, endEvent, task, userTask, serviceTask, \
manualTask, exclusiveGateway, parallelGateway, subProcess.
- Every model needs exactly one startEvent and at least one endEvent.
- Fill raci with role names. If the document does not state a role, use "" \
rather than inventing one.
- Do not invent control points, systems or roles that the document does not \
mention. An empty string is the correct answer when the source is silent.

The JSON must match this shape exactly:
"""


def _extraction_prompt(document: str) -> list[dict]:
    return [
        {"role": "system",
         "content": SYSTEM_PROMPT + json.dumps(EXTRACTION_SCHEMA, indent=2)},
        {"role": "user",
         "content": f"Convert this document into the process model JSON:\n\n{document}"},
    ]


def extract_with_llm(document: str, api_key: str | None = None) -> ProcessSpec:
    import urllib.request

    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    payload = json.dumps({
        "model": GROQ_MODEL,
        "messages": _extraction_prompt(document),
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode()

    request = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read())

    content = body["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.M).strip()
    spec = ProcessSpec.from_dict(json.loads(content))
    return normalise(spec)


# --------------------------------------------------------------------------
# deterministic fallback
# --------------------------------------------------------------------------

HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z ]{2,30}):\s*(.*)$")
STEP_RE = re.compile(
    r"^\s*(\d+)\.\s*\[(?P<lane>[^\]]+)\]\s*(?P<label>[^|]+?)"
    r"(?:\s*\|\s*(?P<meta>.*))?$"
)
DECISION_RE = re.compile(r"^\s*\?\s*(?P<question>[^|]+?)(?:\s*\|\s*(?P<meta>.*))?$")
BRANCH_RE = re.compile(r"^\s*->\s*(?P<condition>[^:]+):\s*(?P<target>.+)$")


def _meta(raw: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            out[key.strip().lower()] = value.strip()
    return out


def extract_rulebased(document: str) -> ProcessSpec:
    """Parse the structured policy convention used in samples/."""
    header: dict[str, str] = {}
    lanes: dict[str, Lane] = {}
    nodes: list[Node] = []
    flows: list[Flow] = []
    pending_branches: list[tuple[str, str, str]] = []  # (gateway_id, condition, label)
    last_id: str | None = None
    counter = 0

    lines = [l.rstrip() for l in document.splitlines()]
    for line in lines:
        if not line.strip():
            continue

        branch = BRANCH_RE.match(line)
        if branch and last_id:
            pending_branches.append(
                (last_id, branch.group("condition").strip(), branch.group("target").strip())
            )
            continue

        step = STEP_RE.match(line)
        if step:
            counter += 1
            lane_name = step.group("lane").strip()
            lane_id = slug(lane_name, "lane")
            if lane_id not in lanes:
                lanes[lane_id] = Lane(lane_id, lane_name)
            label = step.group("label").strip()
            meta = _meta(step.group("meta"))
            node_id = slug(f"{counter}_{label}", "n")
            kind = meta.get("kind", "userTask")
            node = Node(
                id=node_id, name=label, kind=kind, lane=lane_id,
                raci=Raci(
                    responsible=meta.get("r", lane_name),
                    accountable=meta.get("a", ""),
                    consulted=meta.get("c", ""),
                    informed=meta.get("i", ""),
                ),
                control=meta.get("control", ""),
                system=meta.get("system", ""),
                description=meta.get("desc", ""),
            )
            nodes.append(node)
            if last_id:
                flows.append(Flow(slug(f"{last_id}_{node_id}", "f"), last_id, node_id))
            last_id = node_id
            continue

        decision = DECISION_RE.match(line)
        if decision:
            counter += 1
            question = decision.group("question").strip()
            meta = _meta(decision.group("meta"))
            node_id = slug(f"{counter}_{question}", "g")
            lane_name = meta.get("lane", "")
            lane_id = slug(lane_name, "lane") if lane_name else (
                nodes[-1].lane if nodes else ""
            )
            if lane_name and lane_id not in lanes:
                lanes[lane_id] = Lane(lane_id, lane_name)
            nodes.append(Node(
                id=node_id, name=question, kind="exclusiveGateway", lane=lane_id,
                control=meta.get("control", ""),
            ))
            if last_id:
                flows.append(Flow(slug(f"{last_id}_{node_id}", "f"), last_id, node_id))
            last_id = node_id
            continue

        head = HEADER_RE.match(line)
        if head:
            header[head.group(1).strip().lower()] = head.group(2).strip()

    name = header.get("process", "Untitled process")
    key = header.get("key") or slug(name, "p").lower().replace("p_", "")

    first_lane = next(iter(lanes), "")
    start = Node(slug("start", "n"), header.get("trigger", "Process triggered"),
                 "startEvent", first_lane)
    end = Node(slug("end", "n"), header.get("outcome", "Process complete"),
               "endEvent", nodes[-1].lane if nodes else first_lane)
    if nodes:
        flows.insert(0, Flow(slug(f"start_{nodes[0].id}", "f"), start.id, nodes[0].id))
        if last_id:
            flows.append(Flow(slug(f"{last_id}_end", "f"), last_id, end.id))
    nodes = [start] + nodes + [end]

    # attach declared branch conditions to the flow leaving each gateway
    by_label = {n.name.strip().lower(): n.id for n in nodes}
    for gateway_id, condition, target_label in pending_branches:
        target_id = by_label.get(target_label.strip().lower())
        if not target_id:
            continue
        existing = next(
            (f for f in flows if f.source == gateway_id and f.target == target_id), None
        )
        if existing:
            existing.name = condition
        else:
            flows.append(
                Flow(slug(f"{gateway_id}_{target_id}", "f"), gateway_id, target_id, condition)
            )

    spec = ProcessSpec(
        key=key,
        name=name,
        purpose=header.get("purpose", ""),
        scope=header.get("scope", ""),
        trigger=header.get("trigger", ""),
        owner=header.get("owner", ""),
        version=header.get("version", "0.1"),
        lanes=list(lanes.values()),
        nodes=nodes,
        flows=flows,
    )
    return normalise(spec)


def normalise(spec: ProcessSpec) -> ProcessSpec:
    """Repair whatever the extractor got structurally wrong.

    Governance findings should describe the *document*, not the extractor. So
    anything that is unambiguously a serialisation defect (duplicate ids,
    missing flow ids) is fixed here, while anything that reflects a genuine gap
    in the source (no owner, no RACI) is left alone for govern.py to report.
    """
    seen: set[str] = set()
    for index, node in enumerate(spec.nodes):
        if not node.id or node.id in seen:
            node.id = slug(f"{index}_{node.name}", "n")
        seen.add(node.id)

    valid = {n.id for n in spec.nodes}
    spec.flows = [f for f in spec.flows if f.source in valid and f.target in valid]

    seen_flows: set[str] = set()
    for index, flow in enumerate(spec.flows):
        if not flow.id or flow.id in seen_flows:
            flow.id = slug(f"{index}_{flow.source}_{flow.target}", "f")
        seen_flows.add(flow.id)

    lane_ids = {l.id for l in spec.lanes}
    for node in spec.nodes:
        if node.lane not in lane_ids:
            node.lane = next(iter(lane_ids), "")

    _insert_joins(spec)

    if not spec.key:
        spec.key = slug(spec.name, "p").lower()
    spec.key = re.sub(r"[^a-z0-9_]", "", spec.key.lower()) or "process"
    return spec


def _insert_joins(spec: ProcessSpec) -> None:
    """Replace implicit joins with explicit converging gateways.

    When two branches of a decision both flow straight into the same activity,
    BPMN calls that an implicit join. It parses, but it hides whether the
    activity waits for both branches or runs on the first arrival — which is
    exactly the kind of ambiguity a governance model must not contain. So the
    branches are routed through a converging exclusive gateway instead.
    """
    for node in list(spec.nodes):
        if node.is_gateway or node.kind == "startEvent":
            continue
        incoming = spec.incoming(node.id)
        if len(incoming) < 2:
            continue
        gateway = Node(
            id=slug(f"join_{node.id}", "g"),
            name="",
            kind="exclusiveGateway",
            lane=node.lane,
        )
        spec.nodes.insert(spec.nodes.index(node), gateway)
        for flow in incoming:
            flow.target = gateway.id
        spec.flows.append(
            Flow(slug(f"{gateway.id}_{node.id}", "f"), gateway.id, node.id)
        )


def extract(document: str, prefer_llm: bool = True) -> tuple[ProcessSpec, str]:
    """Returns (spec, method_used)."""
    if prefer_llm and os.environ.get("GROQ_API_KEY"):
        try:
            return extract_with_llm(document), "llm"
        except Exception:
            pass
    return extract_rulebased(document), "rulebased"
