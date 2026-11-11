# Escalate major incident

**Version** 0.1 · **Owner** Herr Weber · **Governance score** 60/100 (Needs rework)

**Purpose.** _not stated in source_

**Scope.** _not stated in source_

**Trigger.** Monitoring alert or user-reported outage

**Classification.** OP-IT-07 Manage IT service requests and access · ITIL 4: Incident management

## Roles and responsibilities

| Activity | Lane | R | A | C | I |
| --- | --- | --- | --- | --- | --- |
| Log incident | Service Desk | Service Desk Agent |  |  |  |
| Triage | Service Desk | Service Desk |  |  |  |
| Assign incident to resolver group | Service Desk | Service Desk Agent | Service Desk Lead |  |  |
| Convene major incident bridge | Major Incident Manager | Major Incident Manager |  |  |  |
| Resolve incident in resolver group | Resolver Group | Resolver Group Engineer | Resolver Group Lead, Service Owner |  |  |
| Notification | Service Desk | Service Desk |  |  |  |

## Governance findings

- **error** `process-metadata`: Process owner looks like a named person rather than a role. _Name the accountable role; people change, roles persist._
- **error** `raci-complete` — `Log incident`: Activity is missing RACI: accountable, consulted, informed. _Every activity needs at least a responsible and an accountable role._
- **error** `raci-complete` — `Triage`: Activity is missing RACI: accountable, consulted, informed. _Every activity needs at least a responsible and an accountable role._
- **error** `raci-complete` — `Convene major incident bridge`: Activity is missing RACI: accountable, consulted, informed. _Every activity needs at least a responsible and an accountable role._
- **error** `raci-complete` — `Notification`: Activity is missing RACI: accountable, consulted, informed. _Every activity needs at least a responsible and an accountable role._
- **warning** `lane-owner-defined` — `Service Desk`: Lane 'Service Desk' has no accountable owner. _Name the accountable role for this lane._
- **warning** `lane-owner-defined` — `Major Incident Manager`: Lane 'Major Incident Manager' has no accountable owner. _Name the accountable role for this lane._
- **warning** `lane-owner-defined` — `Resolver Group`: Lane 'Resolver Group' has no accountable owner. _Name the accountable role for this lane._
- **warning** `process-metadata`: Process header is missing its purpose. _State the purpose in the process documentation header._
- **warning** `process-metadata`: Process header is missing its scope. _State the scope in the process documentation header._
- **warning** `single-accountable` — `Resolve incident in resolver group`: More than one accountable role named. _RACI allows exactly one accountable role per activity._
- **warning** `verb-noun-naming` — `Triage`: Label 'Triage' does not read as verb-noun. _Rewrite as an imperative verb plus an object, e.g. 'Assess change risk'._
- **warning** `verb-noun-naming` — `Notification`: Label 'Notification' does not read as verb-noun. _Rewrite as an imperative verb plus an object, e.g. 'Assess change risk'._
- **warning** `control-point-present`: Process contains decisions but no named control point. _Name the control at each decision, e.g. 'Four-eyes approval'._
- **warning** `pcf-classified`: Framework classification is low-confidence (33%). _Confirm the classification manually before publishing._
