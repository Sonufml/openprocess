# OpenProcess

**AI-assisted IT governance process studio.** Turns an IT policy document into a
standards-compliant BPMN 2.0 model, a governance compliance scorecard, and a
publishable process documentation page.

The output is not a picture of a process. It is a `.bpmn` file that imports
directly into ARIS, Signavio or Camunda — because a process model that cannot
leave the tool that drew it is not an asset, it is a screenshot.

```
policy document  ──▶  extraction  ──▶  ProcessSpec  ──▶  BPMN 2.0 + DI
   PDF / DOCX / TXT      LLM or          canonical         governance scorecard
                       parser             model            Confluence page
                                                           Excel register
```

---

## Why it exists

IT governance teams have the same bottleneck everywhere: process knowledge lives
in prose — policies, work instructions, wiki pages — and turning that prose into
a modelled, classified, reviewable process is slow manual work. The modelling
itself is not the hard part. The hard part is doing it *consistently* across
hundreds of processes so the register stays comparable.

OpenProcess automates the first draft and, more importantly, automates the
**review**. Every generated model is checked against 18 rules across three
tiers, scored, and handed back with a prioritised remediation list.

---

## The governance engine

| Tier | Weight | What it checks |
| --- | --- | --- |
| Structural | 45% | Valid, well-formed BPMN. Start and end events, connectivity, reachability, no implicit joins. Mirrors `bpmnlint:recommended`. |
| Convention | 35% | House modelling standards. Verb-noun labels, labelled gateway conditions, lane ownership, RACI completeness, single accountable role, model size, process header metadata. |
| Framework | 20% | Classification and control. Process framework element, ITIL 4 practice, named control points, system of record. |

Scores roll up to 0–100 with a verdict: *Ready to publish* / *Publish after
fixing errors* / *Needs rework* / *Not review-ready*.

The scoring is deliberately boring and deterministic. A reviewer has to be able
to see why a model scored what it scored and overrule it, or nobody will trust
the register.

**Sample results:**

```
  88/100  Fulfil application access request      0 errors   4 warnings   Service request management
  86/100  Approve standard change                0 errors   5 warnings   Change enablement
  60/100  Escalate major incident                6 errors   9 warnings   Incident management
```

The third sample is deliberately non-compliant — nouny task labels, a named
person as process owner, missing RACI, two accountable roles on one activity.
It is the "before" in the demo.

---

## Interoperability: the claim and the evidence

The whole project rests on one claim: *the generated BPMN is real BPMN.* So it
is tested against the reference implementation rather than asserted.

```bash
node check.mjs out/*.bpmn
```

```
=== out/change_approval.bpmn
  parse warnings : 0
  roundtrip      : ok (13783 bytes)
  bpmnlint       : clean
```

Every generated model parses through `bpmn-moddle` with zero warnings,
re-serialises cleanly, and passes `bpmnlint:recommended`. The BPMN DI (diagram
interchange) layout is generated too — without it, a `.bpmn` file opens in ARIS
as an unpositioned pile of shapes rather than a readable model.

The Python test suite independently asserts that every node has DI bounds, that
no two shapes overlap, and that lane membership survives serialisation.

---

## Framework data — read this before demoing

APQC publishes the Process Classification Framework free of charge and licenses
it for reuse with attribution. Category 8.0 is *Manage Information Technology
(IT)*, which is what OpenProcess classifies against.

**The PCF is not vendored into this repository** — APQC requires registration to
download it. Until you place the official Excel export at `data/apqc_pcf.xlsx`,
OpenProcess falls back to its own working taxonomy using `OP-IT-*` codes and
says so in the UI banner.

This is deliberate. The tool will never display a number that looks like a real
PCF element ID unless that number came out of APQC's own file. Guessing at
framework identifiers is exactly the kind of thing that falls apart in a review.

ITIL 4 practice names are the 34 published practices. The keyword lists used to
match a process to a practice are OpenProcess's own heuristics, not part of ITIL.

---

## Running it

```bash
pip install -r requirements.txt

# web app
python app.py                      # http://localhost:5000

# batch
python cli.py samples/*.txt --out out

# tests
python -m pytest test_openprocess.py -q
```

**Extraction modes.** With `GROQ_API_KEY` set, extraction runs through Llama 3.3
with a strict JSON contract. Without it, a deterministic parser handles the
structured policy convention used in `samples/`. Both produce the same
`ProcessSpec`, so everything downstream is identical — which is what makes the
test suite possible.

```bash
export GROQ_API_KEY=...            # optional
export GROQ_MODEL=llama-3.3-70b-versatile
```

---

## Layout

```
app.py                      Flask routes
cli.py                      batch runner
openprocess/
  schema.py                 ProcessSpec — the canonical model
  extract.py                LLM + deterministic extraction, structural repair
  bpmn.py                   BPMN 2.0 XML + DI layout
  govern.py                 18 rules, three tiers, weighted scorecard
  classify.py               PCF and ITIL 4 classification
  frameworks/
    pcf.py                  APQC PCF loader + working taxonomy fallback
    itil4.py                34 ITIL 4 practices
  exporters/
    confluence.py           Confluence storage format + Markdown
    register.py             Excel register (Dashboard/Register/RACI/Findings)
templates/, static/         UI — bpmn-js canvas, scorecard, findings
samples/                    three policy documents, one deliberately bad
test_openprocess.py         26 tests
```

---

## Scope and limits

- Generated models are **drafts for human review**, never authorised processes.
  The UI says so and the Confluence export carries the warning at the top.
- The deterministic parser only understands the numbered-step convention in
  `samples/`. Real messy prose needs the LLM path.
- Layout handles the common case (sequential flow with branches). Deeply nested
  subprocesses and multi-pool collaborations are not laid out intelligently yet.
- ITIL and framework mapping are suggestions with a stated confidence, not
  authoritative classifications.

---

## Attribution

APQC's Process Classification Framework (PCF) is an open standard developed by
APQC. BPMN 2.0 is a standard maintained by the Object Management Group.
`bpmn-js`, `bpmn-moddle` and `bpmnlint` are open-source projects by bpmn.io /
Camunda.
