"""ITIL 4 practices.

The ITIL 4 framework defines 34 management practices in three groups. The
names below are the practice names as published by AXELOS/PeopleCert; the
keyword lists are OpenProcess's own heuristics for matching a process model
to a practice, not part of ITIL itself.
"""

from __future__ import annotations

GENERAL = "general management"
SERVICE = "service management"
TECHNICAL = "technical management"

ITIL4_PRACTICES: list[dict] = [
    # --- general management practices (14) ---
    {"name": "Architecture management", "group": GENERAL,
     "keywords": ["architecture", "reference model", "target state", "blueprint"]},
    {"name": "Continual improvement", "group": GENERAL,
     "keywords": ["improvement", "optimis", "optimiz", "lessons learned", "kaizen", "retrospective"]},
    {"name": "Information security management", "group": GENERAL,
     "keywords": ["security", "confidential", "encryption", "vulnerabilit", "isms", "iso 27001"]},
    {"name": "Knowledge management", "group": GENERAL,
     "keywords": ["knowledge", "documentation", "wiki", "confluence", "article", "known error"]},
    {"name": "Measurement and reporting", "group": GENERAL,
     "keywords": ["kpi", "metric", "report", "dashboard", "measure"]},
    {"name": "Organizational change management", "group": GENERAL,
     "keywords": ["adoption", "training", "communication plan", "stakeholder buy-in"]},
    {"name": "Portfolio management", "group": GENERAL,
     "keywords": ["portfolio", "investment", "prioritis", "prioritiz", "demand"]},
    {"name": "Project management", "group": GENERAL,
     "keywords": ["project", "milestone", "deliverable", "gantt", "sprint"]},
    {"name": "Relationship management", "group": GENERAL,
     "keywords": ["stakeholder", "customer relationship", "account", "escalation contact"]},
    {"name": "Risk management", "group": GENERAL,
     "keywords": ["risk", "mitigat", "likelihood", "impact assessment", "risk register"]},
    {"name": "Service financial management", "group": GENERAL,
     "keywords": ["budget", "cost", "chargeback", "invoice", "licence cost", "license cost"]},
    {"name": "Strategy management", "group": GENERAL,
     "keywords": ["strategy", "roadmap", "vision", "objective setting"]},
    {"name": "Supplier management", "group": GENERAL,
     "keywords": ["supplier", "vendor", "contract", "third party", "procurement", "sourcing"]},
    {"name": "Workforce and talent management", "group": GENERAL,
     "keywords": ["onboarding", "hiring", "skills", "training plan", "headcount"]},

    # --- service management practices (17) ---
    {"name": "Availability management", "group": SERVICE,
     "keywords": ["availability", "uptime", "sla target", "redundan"]},
    {"name": "Business analysis", "group": SERVICE,
     "keywords": ["requirement", "business case", "as-is", "to-be", "gap analysis"]},
    {"name": "Capacity and performance management", "group": SERVICE,
     "keywords": ["capacity", "performance", "throughput", "load", "scaling", "utilis", "utiliz"]},
    {"name": "Change enablement", "group": SERVICE,
     "keywords": ["change", "cab", "change advisory", "rfc", "standard change",
                  "normal change", "emergency change", "approval", "rollback"]},
    {"name": "Incident management", "group": SERVICE,
     "keywords": ["incident", "outage", "escalat", "priority", "restore service",
                  "major incident", "p1", "downtime"]},
    {"name": "IT asset management", "group": SERVICE,
     "keywords": ["asset", "inventory", "licence", "license", "hardware register", "disposal"]},
    {"name": "Monitoring and event management", "group": SERVICE,
     "keywords": ["monitor", "alert", "event", "threshold", "telemetry", "observability"]},
    {"name": "Problem management", "group": SERVICE,
     "keywords": ["problem", "root cause", "rca", "known error", "workaround",
                  "recurring", "underlying cause"]},
    {"name": "Release management", "group": SERVICE,
     "keywords": ["release", "go-live", "cutover", "release note", "version rollout"]},
    {"name": "Service catalogue management", "group": SERVICE,
     "keywords": ["catalogue", "catalog", "service offering", "service entry"]},
    {"name": "Service configuration management", "group": SERVICE,
     "keywords": ["cmdb", "configuration item", " ci ", "baseline", "configuration record"]},
    {"name": "Service continuity management", "group": SERVICE,
     "keywords": ["continuity", "disaster recovery", "bcp", "failover", "rto", "rpo"]},
    {"name": "Service design", "group": SERVICE,
     "keywords": ["service design", "design authority", "solution design"]},
    {"name": "Service desk", "group": SERVICE,
     "keywords": ["service desk", "help desk", "first line", "ticket intake", "1st level"]},
    {"name": "Service level management", "group": SERVICE,
     "keywords": ["sla", "ola", "service level", "underpinning contract", "breach"]},
    {"name": "Service request management", "group": SERVICE,
     "keywords": ["service request", "request fulfil", "request fulfill", "access request",
                  "provisioning", "self-service", "standard request", "onboarding request"]},
    {"name": "Service validation and testing", "group": SERVICE,
     "keywords": ["test", "validation", "uat", "acceptance criteria", "qa"]},

    # --- technical management practices (3) ---
    {"name": "Deployment management", "group": TECHNICAL,
     "keywords": ["deploy", "pipeline", "ci/cd", "build promotion", "artefact", "artifact"]},
    {"name": "Infrastructure and platform management", "group": TECHNICAL,
     "keywords": ["infrastructure", "server", "network", "cloud platform", "hosting", "datacent"]},
    {"name": "Software development and management", "group": TECHNICAL,
     "keywords": ["development", "code review", "merge request", "pull request", "backlog"]},
]


def practice_names() -> list[str]:
    return [p["name"] for p in ITIL4_PRACTICES]
