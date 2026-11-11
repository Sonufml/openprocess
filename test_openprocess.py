"""Test suite.

    python -m pytest test_openprocess.py -q

The governance-score tests are the important ones: a scoring engine nobody
trusts is worse than no scoring engine, so the scores have to be stable and
have to move in the right direction when a model gets worse.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from openprocess import extract_rulebased, to_bpmn_xml, evaluate, classify
from openprocess.schema import ProcessSpec, Node, Flow, Lane, Raci
from openprocess.exporters import to_confluence_storage, to_markdown, write_register

SAMPLES = Path(__file__).parent / "samples"
NS = {
    "b": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "di": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
}


@pytest.fixture
def clean_spec() -> ProcessSpec:
    return extract_rulebased((SAMPLES / "change_approval.txt").read_text())


@pytest.fixture
def messy_spec() -> ProcessSpec:
    return extract_rulebased((SAMPLES / "incident_escalation.txt").read_text())


# ---------------------------------------------------------------- extraction

def test_extracts_header_metadata(clean_spec):
    assert clean_spec.name == "Approve standard change"
    assert clean_spec.owner == "IT Change Manager"
    assert clean_spec.key == "change_approval"
    assert clean_spec.purpose.startswith("Ensure changes")


def test_extracts_lanes_and_activities(clean_spec):
    lane_names = {l.name for l in clean_spec.lanes}
    assert {"Requester", "Change Manager", "Change Advisory Board"} <= lane_names
    assert any(n.name == "Classify change risk" for n in clean_spec.nodes)


def test_start_and_end_events_are_added(clean_spec):
    assert sum(1 for n in clean_spec.nodes if n.kind == "startEvent") == 1
    assert sum(1 for n in clean_spec.nodes if n.kind == "endEvent") == 1


def test_gateway_branches_carry_conditions(clean_spec):
    gateway = next(n for n in clean_spec.nodes if n.kind == "exclusiveGateway" and n.name)
    branches = clean_spec.outgoing(gateway.id)
    assert len(branches) >= 2
    assert all(f.name for f in branches)


def test_raci_and_controls_are_parsed(clean_spec):
    node = next(n for n in clean_spec.nodes if n.name == "Present change to change advisory board")
    assert node.raci.accountable == "CAB Chair"
    assert node.control == "Four-eyes approval"
    assert node.system == "Confluence"


def test_implicit_joins_are_replaced(clean_spec):
    for node in clean_spec.nodes:
        if node.is_gateway or node.kind == "startEvent":
            continue
        assert len(clean_spec.incoming(node.id)) <= 1, f"{node.name} joins implicitly"


# --------------------------------------------------------------------- bpmn

def test_bpmn_is_well_formed(clean_spec):
    root = etree.fromstring(to_bpmn_xml(clean_spec).encode())
    assert root.tag.endswith("definitions")
    assert root.find(".//b:process", NS) is not None
    assert root.find(".//b:collaboration", NS) is not None


def test_every_node_has_diagram_interchange(clean_spec):
    """Without DI the file opens as an unpositioned pile in ARIS."""
    root = etree.fromstring(to_bpmn_xml(clean_spec).encode())
    shaped = {s.get("bpmnElement") for s in root.findall(".//di:BPMNShape", NS)}
    for node in clean_spec.nodes:
        assert node.id in shaped
    edged = {e.get("bpmnElement") for e in root.findall(".//di:BPMNEdge", NS)}
    for flow in clean_spec.flows:
        assert flow.id in edged


def test_shapes_do_not_overlap(clean_spec):
    root = etree.fromstring(to_bpmn_xml(clean_spec).encode())
    boxes = []
    for shape in root.findall(".//di:BPMNShape", NS):
        element = shape.get("bpmnElement")
        if element.startswith(("Participant", "lane_")):
            continue
        bounds = shape.find("dc:Bounds", NS)
        boxes.append(tuple(float(bounds.get(k)) for k in ("x", "y", "width", "height")))
    for index, (ax, ay, aw, ah) in enumerate(boxes):
        for bx, by, bw, bh in boxes[index + 1:]:
            overlaps = ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
            assert not overlaps


def test_lane_membership_is_serialised(clean_spec):
    root = etree.fromstring(to_bpmn_xml(clean_spec).encode())
    refs = {e.text for e in root.findall(".//b:flowNodeRef", NS)}
    assert refs == {n.id for n in clean_spec.nodes}


def test_names_with_special_characters_survive():
    spec = ProcessSpec(
        key="quoting", name='Handle "urgent" & <critical> requests',
        lanes=[Lane("lane_a", "Team & Co")],
        nodes=[
            Node("n_s", "Start", "startEvent", "lane_a"),
            Node("n_t", 'Assess "risk" & impact', "userTask", "lane_a"),
            Node("n_e", "Done", "endEvent", "lane_a"),
        ],
        flows=[Flow("f1", "n_s", "n_t"), Flow("f2", "n_t", "n_e")],
    )
    root = etree.fromstring(to_bpmn_xml(spec).encode())
    task = root.find('.//b:userTask[@id="n_t"]', NS)
    assert task.get("name") == 'Assess "risk" & impact'


# --------------------------------------------------------------- governance

def test_clean_model_scores_higher_than_messy(clean_spec, messy_spec):
    classify(clean_spec)
    classify(messy_spec)
    assert evaluate(clean_spec)["score"] > evaluate(messy_spec)["score"]


def test_messy_model_is_not_review_ready(messy_spec):
    classify(messy_spec)
    report = evaluate(messy_spec)
    assert report["counts"]["errors"] > 0
    assert report["verdict"] != "Ready to publish"


def test_named_person_as_owner_is_an_error(messy_spec):
    rules = {f["rule"] for f in evaluate(messy_spec)["findings"] if f["severity"] == "error"}
    assert "process-metadata" in rules


def test_nouny_labels_are_flagged(messy_spec):
    flagged = {
        f["element_name"] for f in evaluate(messy_spec)["findings"]
        if f["rule"] == "verb-noun-naming"
    }
    assert "Triage" in flagged and "Notification" in flagged


def test_multiple_accountable_roles_are_flagged(messy_spec):
    rules = {f["rule"] for f in evaluate(messy_spec)["findings"]}
    assert "single-accountable" in rules


def test_missing_start_event_is_an_error():
    spec = ProcessSpec(
        key="broken", name="Broken process",
        nodes=[Node("n_a", "Do work", "userTask")],
        flows=[],
    )
    rules = {f["rule"] for f in evaluate(spec)["findings"] if f["severity"] == "error"}
    assert {"start-event-required", "end-event-required"} <= rules


def test_unreachable_element_is_detected():
    spec = ProcessSpec(
        key="orphan", name="Orphan process",
        lanes=[Lane("lane_a", "Team", "Team Lead")],
        nodes=[
            Node("n_s", "Start", "startEvent", "lane_a"),
            Node("n_a", "Do work", "userTask", "lane_a",
                 Raci("Team", "Team Lead", "QA", "Ops")),
            Node("n_e", "End", "endEvent", "lane_a"),
            Node("n_x", "Do orphaned work", "userTask", "lane_a"),
        ],
        flows=[Flow("f1", "n_s", "n_a"), Flow("f2", "n_a", "n_e")],
    )
    rules = {f["rule"] for f in evaluate(spec)["findings"]}
    assert "unreachable-element" in rules


def test_score_is_deterministic(clean_spec):
    classify(clean_spec)
    assert len({evaluate(clean_spec)["score"] for _ in range(5)}) == 1


def test_score_stays_in_range(clean_spec, messy_spec):
    for spec in (clean_spec, messy_spec):
        classify(spec)
        assert 0 <= evaluate(spec)["score"] <= 100


# ------------------------------------------------------------ classification

def test_itil_practice_mapping(clean_spec, messy_spec):
    assert classify(clean_spec)["itil_practice"] == "Change enablement"
    assert classify(messy_spec)["itil_practice"] == "Incident management"


def test_access_request_maps_to_request_management():
    spec = extract_rulebased((SAMPLES / "access_request.txt").read_text())
    assert classify(spec)["itil_practice"] == "Service request management"


def test_working_taxonomy_ids_are_namespaced(clean_spec):
    """Framework IDs must never be mistaken for real APQC element numbers."""
    result = classify(clean_spec)
    if not result["pcf_official"]:
        assert result["pcf_id"].startswith("OP-IT-")


# ----------------------------------------------------------------- exporters

def test_confluence_export_is_well_formed_xml(clean_spec):
    classify(clean_spec)
    report = evaluate(clean_spec)
    storage = to_confluence_storage(clean_spec, report, "change_approval.bpmn")
    wrapped = (
        '<root xmlns:ac="http://atlassian.com/content" '
        'xmlns:ri="http://atlassian.com/resource/identifier">' + storage + "</root>"
    )
    etree.fromstring(wrapped.encode())


def test_markdown_export_contains_raci(clean_spec):
    classify(clean_spec)
    markdown = to_markdown(clean_spec, evaluate(clean_spec))
    assert "Roles and responsibilities" in markdown
    assert "CAB Chair" in markdown


def test_register_writes_all_sheets(clean_spec, messy_spec, tmp_path):
    from openpyxl import load_workbook

    for spec in (clean_spec, messy_spec):
        classify(spec)
    results = [(spec, evaluate(spec)) for spec in (clean_spec, messy_spec)]
    path = write_register(results, tmp_path / "register.xlsx")
    wb = load_workbook(path)
    assert wb.sheetnames == ["Dashboard", "Register", "RACI", "Findings"]
    assert wb["Register"].max_row == 3
