"""Governance rule engine.

Three tiers of checks, mirroring how a real IT governance team reviews a model:

  structural  — is this valid, well-formed BPMN? (mirrors bpmnlint:recommended)
  convention  — does it follow our modelling conventions? (naming, RACI, ownership)
  framework   — is it classified and controlled? (PCF, ITIL, control points)

Each rule returns findings. Findings roll up into a weighted 0-100 scorecard so
a reviewer can triage a hundred models without opening any of them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Callable

from .schema import ProcessSpec, TASK_KINDS, GATEWAY_KINDS

ERROR, WARNING, INFO = "error", "warning", "info"

STRUCTURAL, CONVENTION, FRAMEWORK = "structural", "convention", "framework"

TIER_WEIGHTS = {STRUCTURAL: 0.45, CONVENTION: 0.35, FRAMEWORK: 0.20}
SEVERITY_COST = {ERROR: 1.0, WARNING: 0.5, INFO: 0.15}

# A verb-noun task label starts with an imperative verb. This is a pragmatic
# list, not a linguistic model — it catches the common failure ("Ticket", "SLA
# check", "Approval") without flagging every reasonable label.
NOUNISH_ENDINGS = ("tion", "ment", "ance", "ence", "ing", "al", "ure")

MAX_ACTIVITIES_PER_LEVEL = 15


@dataclass
class Finding:
    rule: str
    tier: str
    severity: str
    message: str
    element_id: str = ""
    element_name: str = ""
    remediation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


Rule = Callable[[ProcessSpec], list[Finding]]
_RULES: list[tuple[str, str, Rule]] = []


def rule(rule_id: str, tier: str):
    def wrap(fn: Rule) -> Rule:
        _RULES.append((rule_id, tier, fn))
        return fn
    return wrap


# --------------------------------------------------------------------------
# structural
# --------------------------------------------------------------------------

@rule("start-event-required", STRUCTURAL)
def _start_event(spec: ProcessSpec) -> list[Finding]:
    if any(n.kind == "startEvent" for n in spec.nodes):
        return []
    return [Finding(
        "start-event-required", STRUCTURAL, ERROR,
        "Process has no start event, so its trigger is undefined.",
        remediation="Add a start event named after the trigger condition.",
    )]


@rule("end-event-required", STRUCTURAL)
def _end_event(spec: ProcessSpec) -> list[Finding]:
    if any(n.kind == "endEvent" for n in spec.nodes):
        return []
    return [Finding(
        "end-event-required", STRUCTURAL, ERROR,
        "Process has no end event, so its completion criteria are undefined.",
        remediation="Add an end event for every distinct outcome.",
    )]


@rule("no-disconnected-node", STRUCTURAL)
def _disconnected(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        if node.kind == "startEvent" and not spec.outgoing(node.id):
            out.append(Finding(
                "no-disconnected-node", STRUCTURAL, ERROR,
                "Start event has no outgoing flow.", node.id, node.name,
                "Connect the start event to the first activity.",
            ))
        elif node.kind == "endEvent" and not spec.incoming(node.id):
            out.append(Finding(
                "no-disconnected-node", STRUCTURAL, ERROR,
                "End event has no incoming flow.", node.id, node.name,
                "Connect the preceding activity to this end event.",
            ))
        elif node.kind not in ("startEvent", "endEvent"):
            if not spec.incoming(node.id) or not spec.outgoing(node.id):
                out.append(Finding(
                    "no-disconnected-node", STRUCTURAL, ERROR,
                    "Element is not connected on both sides.", node.id, node.name,
                    "Every activity needs at least one incoming and one outgoing flow.",
                ))
    return out


@rule("no-dangling-flow", STRUCTURAL)
def _dangling(spec: ProcessSpec) -> list[Finding]:
    ids = {n.id for n in spec.nodes}
    return [
        Finding("no-dangling-flow", STRUCTURAL, ERROR,
                f"Sequence flow references a missing element ({f.source} -> {f.target}).",
                f.id, f.name, "Remove the flow or add the missing element.")
        for f in spec.flows if f.source not in ids or f.target not in ids
    ]


@rule("gateway-branching", STRUCTURAL)
def _gateway_branching(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        if node.kind not in GATEWAY_KINDS:
            continue
        if len(spec.outgoing(node.id)) < 2 and len(spec.incoming(node.id)) < 2:
            out.append(Finding(
                "gateway-branching", STRUCTURAL, WARNING,
                "Gateway neither splits nor merges the flow.", node.id, node.name,
                "Remove the gateway, or give it a second branch.",
            ))
    return out


@rule("no-implicit-join", STRUCTURAL)
def _implicit_join(spec: ProcessSpec) -> list[Finding]:
    """Mirrors bpmnlint's fake-join check.

    An activity with two incoming flows does not say whether it waits for both
    branches or fires on the first. That ambiguity has to be modelled, not left
    to the reader.
    """
    out = []
    for node in spec.nodes:
        if node.kind in GATEWAY_KINDS or node.kind == "startEvent":
            continue
        if len(spec.incoming(node.id)) > 1:
            out.append(Finding(
                "no-implicit-join", STRUCTURAL, WARNING,
                "Element joins several flows implicitly.", node.id, node.name,
                "Route the branches through a converging gateway so the join "
                "semantics are explicit.",
            ))
    return out


@rule("unreachable-element", STRUCTURAL)
def _unreachable(spec: ProcessSpec) -> list[Finding]:
    starts = [n.id for n in spec.nodes if n.kind == "startEvent"]
    seen, queue = set(starts), list(starts)
    while queue:
        current = queue.pop()
        for flow in spec.outgoing(current):
            if flow.target not in seen:
                seen.add(flow.target)
                queue.append(flow.target)
    return [
        Finding("unreachable-element", STRUCTURAL, ERROR,
                "Element cannot be reached from any start event.", n.id, n.name,
                "Connect it to the main flow or delete it.")
        for n in spec.nodes if n.id not in seen
    ]


# --------------------------------------------------------------------------
# convention
# --------------------------------------------------------------------------

@rule("verb-noun-naming", CONVENTION)
def _verb_noun(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        if node.kind not in TASK_KINDS:
            continue
        name = (node.name or "").strip()
        if not name:
            out.append(Finding(
                "verb-noun-naming", CONVENTION, ERROR,
                "Activity has no label.", node.id, node.name,
                "Label every activity in verb-noun form, e.g. 'Approve request'.",
            ))
            continue
        first = name.split()[0].lower().strip(":,")
        if len(name.split()) < 2 or first.endswith(NOUNISH_ENDINGS):
            out.append(Finding(
                "verb-noun-naming", CONVENTION, WARNING,
                f"Label '{name}' does not read as verb-noun.", node.id, node.name,
                "Rewrite as an imperative verb plus an object, e.g. 'Assess change risk'.",
            ))
    return out


@rule("gateway-condition-labelled", CONVENTION)
def _gateway_labels(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        if node.kind != "exclusiveGateway":
            continue
        outgoing = spec.outgoing(node.id)
        if len(outgoing) < 2:
            continue
        if not node.name.strip():
            out.append(Finding(
                "gateway-condition-labelled", CONVENTION, WARNING,
                "Decision gateway has no question label.", node.id, node.name,
                "Phrase the gateway as a question, e.g. 'Risk acceptable?'.",
            ))
        for flow in outgoing:
            if not flow.name.strip():
                out.append(Finding(
                    "gateway-condition-labelled", CONVENTION, ERROR,
                    "Outgoing flow from a decision gateway has no condition.",
                    flow.id, node.name,
                    "Label the flow with the condition under which it is taken.",
                ))
    return out


@rule("lane-owner-defined", CONVENTION)
def _lane_owner(spec: ProcessSpec) -> list[Finding]:
    out = []
    if not spec.lanes:
        out.append(Finding(
            "lane-owner-defined", CONVENTION, ERROR,
            "Model has no lanes, so responsibility is not visible.",
            remediation="Add one lane per role or organisational unit.",
        ))
    for lane in spec.lanes:
        if not lane.owner.strip():
            out.append(Finding(
                "lane-owner-defined", CONVENTION, WARNING,
                f"Lane '{lane.name}' has no accountable owner.", lane.id, lane.name,
                "Name the accountable role for this lane.",
            ))
        if not spec.nodes_in_lane(lane.id):
            out.append(Finding(
                "lane-owner-defined", CONVENTION, WARNING,
                f"Lane '{lane.name}' is empty.", lane.id, lane.name,
                "Assign activities to the lane or remove it.",
            ))
    return out


@rule("raci-complete", CONVENTION)
def _raci(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        if node.kind not in TASK_KINDS:
            continue
        missing = node.raci.missing()
        if "responsible" in missing or "accountable" in missing:
            out.append(Finding(
                "raci-complete", CONVENTION, ERROR,
                f"Activity is missing RACI: {', '.join(missing)}.", node.id, node.name,
                "Every activity needs at least a responsible and an accountable role.",
            ))
        elif missing:
            out.append(Finding(
                "raci-complete", CONVENTION, INFO,
                f"Activity has no consulted/informed roles ({', '.join(missing)}).",
                node.id, node.name,
                "Add consulted and informed roles, or record that none apply.",
            ))
    return out


@rule("single-accountable", CONVENTION)
def _single_accountable(spec: ProcessSpec) -> list[Finding]:
    out = []
    for node in spec.nodes:
        accountable = node.raci.accountable
        if "," in accountable or " and " in accountable.lower():
            out.append(Finding(
                "single-accountable", CONVENTION, WARNING,
                "More than one accountable role named.", node.id, node.name,
                "RACI allows exactly one accountable role per activity.",
            ))
    return out


@rule("model-size", CONVENTION)
def _model_size(spec: ProcessSpec) -> list[Finding]:
    activities = [n for n in spec.nodes if n.kind in TASK_KINDS]
    if len(activities) <= MAX_ACTIVITIES_PER_LEVEL:
        return []
    return [Finding(
        "model-size", CONVENTION, WARNING,
        f"{len(activities)} activities on one level "
        f"(convention allows {MAX_ACTIVITIES_PER_LEVEL}).",
        remediation="Collapse a coherent block into a subprocess and model it separately.",
    )]


@rule("process-metadata", CONVENTION)
def _metadata(spec: ProcessSpec) -> list[Finding]:
    out = []
    for field_name, label in (
        ("purpose", "purpose"), ("scope", "scope"),
        ("trigger", "trigger"), ("owner", "process owner"),
    ):
        if not getattr(spec, field_name, "").strip():
            out.append(Finding(
                "process-metadata", CONVENTION, WARNING,
                f"Process header is missing its {label}.",
                remediation=f"State the {label} in the process documentation header.",
            ))
    if re.search(r"\b(Mr|Ms|Herr|Frau)\b|@", spec.owner):
        out.append(Finding(
            "process-metadata", CONVENTION, ERROR,
            "Process owner looks like a named person rather than a role.",
            remediation="Name the accountable role; people change, roles persist.",
        ))
    return out


# --------------------------------------------------------------------------
# framework
# --------------------------------------------------------------------------

@rule("pcf-classified", FRAMEWORK)
def _pcf(spec: ProcessSpec) -> list[Finding]:
    if not spec.pcf_id:
        return [Finding(
            "pcf-classified", FRAMEWORK, ERROR,
            "Process is not classified against the process framework.",
            remediation="Assign the closest framework element so the process register stays comparable.",
        )]
    if spec.pcf_confidence < 0.35:
        return [Finding(
            "pcf-classified", FRAMEWORK, WARNING,
            f"Framework classification is low-confidence ({spec.pcf_confidence:.0%}).",
            remediation="Confirm the classification manually before publishing.",
        )]
    return []


@rule("itil-practice-mapped", FRAMEWORK)
def _itil(spec: ProcessSpec) -> list[Finding]:
    if spec.itil_practice:
        return []
    return [Finding(
        "itil-practice-mapped", FRAMEWORK, WARNING,
        "No ITIL 4 practice mapped to this process.",
        remediation="Map the process to its ITIL 4 practice so service management reporting lines up.",
    )]


@rule("control-point-present", FRAMEWORK)
def _controls(spec: ProcessSpec) -> list[Finding]:
    has_decision = any(n.kind == "exclusiveGateway" for n in spec.nodes)
    has_control = any(n.control.strip() for n in spec.nodes)
    if has_decision and not has_control:
        return [Finding(
            "control-point-present", FRAMEWORK, WARNING,
            "Process contains decisions but no named control point.",
            remediation="Name the control at each decision, e.g. 'Four-eyes approval'.",
        )]
    return []


@rule("system-of-record", FRAMEWORK)
def _systems(spec: ProcessSpec) -> list[Finding]:
    activities = [n for n in spec.nodes if n.kind in TASK_KINDS]
    unassigned = [n for n in activities if not n.system.strip()]
    if activities and len(unassigned) == len(activities):
        return [Finding(
            "system-of-record", FRAMEWORK, INFO,
            "No supporting IT system recorded on any activity.",
            remediation="Record the system of record per activity to enable application-portfolio analysis.",
        )]
    return []


# --------------------------------------------------------------------------
# runner
# --------------------------------------------------------------------------

def evaluate(spec: ProcessSpec) -> dict:
    findings: list[Finding] = []
    for rule_id, tier, fn in _RULES:
        try:
            findings.extend(fn(spec))
        except Exception as exc:  # a broken rule must not break the review
            findings.append(Finding(
                rule_id, tier, INFO, f"Rule could not be evaluated: {exc}",
            ))

    rules_by_tier: dict[str, set[str]] = {}
    for rule_id, tier, _ in _RULES:
        rules_by_tier.setdefault(tier, set()).add(rule_id)

    tier_scores: dict[str, dict] = {}
    for tier, rule_ids in rules_by_tier.items():
        tier_findings = [f for f in findings if f.tier == tier]
        cost = sum(SEVERITY_COST[f.severity] for f in tier_findings)
        # normalise against the rule count so tiers with more rules aren't
        # penalised twice; cap the per-tier deduction at 100%.
        score = max(0.0, 1.0 - cost / max(1, len(rule_ids)))
        tier_scores[tier] = {
            "score": round(score * 100),
            "weight": TIER_WEIGHTS[tier],
            "rules": len(rule_ids),
            "errors": sum(1 for f in tier_findings if f.severity == ERROR),
            "warnings": sum(1 for f in tier_findings if f.severity == WARNING),
            "info": sum(1 for f in tier_findings if f.severity == INFO),
        }

    overall = round(sum(t["score"] * t["weight"] for t in tier_scores.values()))

    if overall >= 90:
        verdict = "Ready to publish"
    elif overall >= 70:
        verdict = "Publish after fixing errors"
    elif overall >= 50:
        verdict = "Needs rework"
    else:
        verdict = "Not review-ready"

    severity_order = {ERROR: 0, WARNING: 1, INFO: 2}
    findings.sort(key=lambda f: (severity_order[f.severity], f.tier, f.rule))

    return {
        "score": overall,
        "verdict": verdict,
        "tiers": tier_scores,
        "findings": [f.to_dict() for f in findings],
        "counts": {
            "errors": sum(1 for f in findings if f.severity == ERROR),
            "warnings": sum(1 for f in findings if f.severity == WARNING),
            "info": sum(1 for f in findings if f.severity == INFO),
        },
        "rule_count": len(_RULES),
    }


def rule_catalogue() -> list[dict]:
    return [{"rule": r, "tier": t} for r, t, _ in _RULES]
