"""ProcessSpec -> BPMN 2.0 XML, including BPMN DI layout.

The DI (diagram interchange) part is what makes the output actually useful.
A .bpmn file without DI opens as an unpositioned pile of shapes in ARIS or
Signavio; with DI it opens as a readable, laid-out model. That difference is
the whole point of exporting to an open standard rather than a picture.

Layout is a layered (Sugiyama-style) assignment:
  column = longest-path rank from the start event
  row    = the lane the node belongs to
  slot   = position within the lane when several nodes share a column
"""

from __future__ import annotations

from xml.sax.saxutils import escape, quoteattr

from .schema import ProcessSpec, Node, EVENT_KINDS, GATEWAY_KINDS

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

TARGET_NS = "http://openprocess.dev/schema/bpmn"

# geometry
POOL_X, POOL_Y = 160, 80
POOL_HEADER_W = 30
LANE_LABEL_W = 30
COL_W = 180
SLOT_H = 100
MIN_LANE_H = 140
PAD_LEFT = 60

SIZES = {
    "event": (36, 36),
    "gateway": (50, 50),
    "task": (110, 80),
}


def _size(node: Node) -> tuple[int, int]:
    if node.kind in EVENT_KINDS:
        return SIZES["event"]
    if node.kind in GATEWAY_KINDS:
        return SIZES["gateway"]
    return SIZES["task"]


def _rank(spec: ProcessSpec) -> dict[str, int]:
    """Longest-path rank per node. Cycle-safe via visit budget."""
    ranks = {n.id: 0 for n in spec.nodes}
    order = [n.id for n in spec.nodes if not spec.incoming(n.id)] or [
        n.id for n in spec.nodes if n.kind == "startEvent"
    ] or ([spec.nodes[0].id] if spec.nodes else [])

    budget = max(1, len(spec.nodes) * len(spec.flows) + len(spec.nodes))
    queue = list(order)
    while queue and budget > 0:
        budget -= 1
        current = queue.pop(0)
        for flow in spec.outgoing(current):
            if ranks.get(flow.target, 0) < ranks.get(current, 0) + 1:
                ranks[flow.target] = ranks[current] + 1
                queue.append(flow.target)
    return ranks


def layout(spec: ProcessSpec) -> dict:
    """Compute pool, lane and node geometry. Returns a plain dict of boxes."""
    ranks = _rank(spec)
    lanes = spec.lanes or []
    lane_ids = [l.id for l in lanes] or [""]

    # how many nodes sit in the same (lane, column) cell
    occupancy: dict[tuple[str, int], list[str]] = {}
    for node in spec.nodes:
        lane_id = node.lane if node.lane in lane_ids else lane_ids[0]
        occupancy.setdefault((lane_id, ranks.get(node.id, 0)), []).append(node.id)

    lane_slots = {
        lane_id: max(
            [len(v) for (l, _), v in occupancy.items() if l == lane_id] or [1]
        )
        for lane_id in lane_ids
    }
    lane_heights = {
        lane_id: max(MIN_LANE_H, lane_slots[lane_id] * SLOT_H + 40)
        for lane_id in lane_ids
    }

    lane_tops: dict[str, int] = {}
    y = POOL_Y
    for lane_id in lane_ids:
        lane_tops[lane_id] = y
        y += lane_heights[lane_id]
    pool_h = y - POOL_Y

    max_rank = max(ranks.values(), default=0)
    pool_w = POOL_HEADER_W + LANE_LABEL_W + PAD_LEFT + (max_rank + 1) * COL_W

    boxes: dict[str, dict] = {}
    for (lane_id, column), node_ids in occupancy.items():
        for slot, node_id in enumerate(sorted(node_ids)):
            node = spec.node(node_id)
            w, h = _size(node)
            cell_x = POOL_X + POOL_HEADER_W + LANE_LABEL_W + PAD_LEFT + column * COL_W
            cell_cy = (
                lane_tops[lane_id]
                + (lane_heights[lane_id] / (lane_slots[lane_id] + 1)) * (slot + 1)
            )
            boxes[node_id] = {
                "x": int(cell_x - w / 2),
                "y": int(cell_cy - h / 2),
                "w": w,
                "h": h,
                "cx": int(cell_x),
                "cy": int(cell_cy),
            }

    return {
        "pool": {"x": POOL_X, "y": POOL_Y, "w": pool_w, "h": pool_h},
        "lanes": {
            lane_id: {
                "x": POOL_X + POOL_HEADER_W,
                "y": lane_tops[lane_id],
                "w": pool_w - POOL_HEADER_W,
                "h": lane_heights[lane_id],
            }
            for lane_id in lane_ids
        },
        "nodes": boxes,
        "ranks": ranks,
    }


def _waypoints(src: dict, tgt: dict) -> list[tuple[int, int]]:
    """Right-edge to left-edge, with an orthogonal elbow when lanes differ."""
    if tgt["cx"] <= src["cx"]:
        # backward flow (loop): route under the source
        drop = src["y"] + src["h"] + 30
        return [
            (src["cx"], src["y"] + src["h"]),
            (src["cx"], drop),
            (tgt["cx"], drop),
            (tgt["cx"], tgt["y"] + tgt["h"]),
        ]
    start = (src["x"] + src["w"], src["cy"])
    end = (tgt["x"], tgt["cy"])
    if abs(src["cy"] - tgt["cy"]) < 6:
        return [start, end]
    mid_x = int((start[0] + end[0]) / 2)
    return [start, (mid_x, start[1]), (mid_x, end[1]), end]


def to_bpmn_xml(spec: ProcessSpec) -> str:
    geo = layout(spec)
    proc_id = f"Process_{spec.key}"
    collab_id = f"Collaboration_{spec.key}"
    participant_id = f"Participant_{spec.key}"

    out: list[str] = []
    a = out.append

    a('<?xml version="1.0" encoding="UTF-8"?>')
    a(
        "<bpmn:definitions "
        + " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())
        + f' id="Definitions_{spec.key}"'
        + f' targetNamespace="{TARGET_NS}"'
        + ' exporter="OpenProcess" exporterVersion="1.0">'
    )

    # ---- collaboration (gives us the pool) ----
    a(f'  <bpmn:collaboration id="{collab_id}">')
    a(
        f'    <bpmn:participant id="{participant_id}" '
        f"name={quoteattr(spec.name)} processRef=\"{proc_id}\" />"
    )
    a("  </bpmn:collaboration>")

    # ---- process ----
    a(f'  <bpmn:process id="{proc_id}" name={quoteattr(spec.name)} isExecutable="false">')

    if spec.lanes:
        a(f'    <bpmn:laneSet id="LaneSet_{spec.key}">')
        for lane in spec.lanes:
            a(f'      <bpmn:lane id="{lane.id}" name={quoteattr(lane.name)}>')
            for node in spec.nodes_in_lane(lane.id):
                a(f"        <bpmn:flowNodeRef>{escape(node.id)}</bpmn:flowNodeRef>")
            a("      </bpmn:lane>")
        a("    </bpmn:laneSet>")

    for node in spec.nodes:
        tag = f"bpmn:{node.kind}"
        a(f"    <{tag} id=\"{node.id}\" name={quoteattr(node.name)}>")
        for flow in spec.incoming(node.id):
            a(f"      <bpmn:incoming>{flow.id}</bpmn:incoming>")
        for flow in spec.outgoing(node.id):
            a(f"      <bpmn:outgoing>{flow.id}</bpmn:outgoing>")
        a(f"    </{tag}>")

    for flow in spec.flows:
        attrs = f'id="{flow.id}" sourceRef="{flow.source}" targetRef="{flow.target}"'
        if flow.name:
            attrs += f" name={quoteattr(flow.name)}"
        source = spec.node(flow.source)
        if flow.name and source and source.kind == "exclusiveGateway":
            a(f"    <bpmn:sequenceFlow {attrs}>")
            a(
                '      <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">'
                f"{escape(flow.name)}</bpmn:conditionExpression>"
            )
            a("    </bpmn:sequenceFlow>")
        else:
            a(f"    <bpmn:sequenceFlow {attrs} />")

    a("  </bpmn:process>")

    # ---- diagram interchange ----
    a(f'  <bpmndi:BPMNDiagram id="Diagram_{spec.key}">')
    a(f'    <bpmndi:BPMNPlane id="Plane_{spec.key}" bpmnElement="{collab_id}">')

    pool = geo["pool"]
    a(
        f'      <bpmndi:BPMNShape id="Shape_{participant_id}" '
        f'bpmnElement="{participant_id}" isHorizontal="true">'
    )
    a(
        f'        <dc:Bounds x="{pool["x"]}" y="{pool["y"]}" '
        f'width="{pool["w"]}" height="{pool["h"]}" />'
    )
    a("      </bpmndi:BPMNShape>")

    for lane in spec.lanes:
        box = geo["lanes"].get(lane.id)
        if not box:
            continue
        a(
            f'      <bpmndi:BPMNShape id="Shape_{lane.id}" '
            f'bpmnElement="{lane.id}" isHorizontal="true">'
        )
        a(
            f'        <dc:Bounds x="{box["x"]}" y="{box["y"]}" '
            f'width="{box["w"]}" height="{box["h"]}" />'
        )
        a("      </bpmndi:BPMNShape>")

    for node in spec.nodes:
        box = geo["nodes"].get(node.id)
        if not box:
            continue
        a(f'      <bpmndi:BPMNShape id="Shape_{node.id}" bpmnElement="{node.id}">')
        a(
            f'        <dc:Bounds x="{box["x"]}" y="{box["y"]}" '
            f'width="{box["w"]}" height="{box["h"]}" />'
        )
        if node.kind in EVENT_KINDS or node.kind in GATEWAY_KINDS:
            label_y = box["y"] + box["h"] + 6
            a('        <bpmndi:BPMNLabel>')
            a(
                f'          <dc:Bounds x="{box["cx"] - 45}" y="{label_y}" '
                'width="90" height="27" />'
            )
            a("        </bpmndi:BPMNLabel>")
        a("      </bpmndi:BPMNShape>")

    for flow in spec.flows:
        src = geo["nodes"].get(flow.source)
        tgt = geo["nodes"].get(flow.target)
        if not src or not tgt:
            continue
        a(f'      <bpmndi:BPMNEdge id="Edge_{flow.id}" bpmnElement="{flow.id}">')
        for x, y in _waypoints(src, tgt):
            a(f'        <di:waypoint x="{int(x)}" y="{int(y)}" />')
        a("      </bpmndi:BPMNEdge>")

    a("    </bpmndi:BPMNPlane>")
    a("  </bpmndi:BPMNDiagram>")
    a("</bpmn:definitions>")

    return "\n".join(out) + "\n"
