"""APQC Process Classification Framework (PCF) support.

APQC publishes the cross-industry PCF free of charge and licenses it for reuse
with attribution. Category 8.0 of the framework is "Manage Information
Technology (IT)", which is the part OpenProcess classifies against.

IMPORTANT — read before demoing:

    The official PCF requires registration to download, so it is NOT vendored
    into this repository. Until you drop the official Excel export into
    data/apqc_pcf.xlsx, OpenProcess falls back to WORKING_IT_TAXONOMY below.

    That fallback uses OpenProcess's own "OP-IT-*" codes, deliberately NOT
    APQC element IDs. Nothing in this repo will ever show you a number that
    looks like a real PCF ID unless it came out of APQC's own file. Guessing
    at framework IDs is exactly the kind of thing that falls apart in a
    review, so the code refuses to do it.

To load the real thing:
    1. Download "APQC Process Classification Framework (PCF) - Cross-Industry
       - Excel Version 8.0" from apqc.org/pcf
    2. Save it as data/apqc_pcf.xlsx
    3. Restart. The banner in the UI will switch to "APQC PCF v8.0".

Attribution required by APQC when redistributing PCF content:
    APQC's Process Classification Framework (PCF) is an open standard
    developed by APQC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PCF_PATH = Path(__file__).resolve().parents[2] / "data" / "apqc_pcf.xlsx"

IT_CATEGORY = "8.0"
IT_CATEGORY_NAME = "Manage Information Technology (IT)"


@dataclass
class PcfEntry:
    id: str
    name: str
    level: int
    source: str  # "APQC PCF v8.0" or "OpenProcess working taxonomy"

    @property
    def is_official(self) -> bool:
        return self.source.startswith("APQC")


# Working taxonomy used only until the official file is present. The codes are
# namespaced OP-IT-* precisely so they can never be mistaken for PCF IDs.
WORKING_IT_TAXONOMY: list[tuple[str, str]] = [
    ("OP-IT-01", "Manage IT strategy and governance"),
    ("OP-IT-02", "Manage IT policies, standards and guidelines"),
    ("OP-IT-03", "Manage the IT portfolio and demand"),
    ("OP-IT-04", "Develop and maintain IT solutions"),
    ("OP-IT-05", "Deploy IT solutions and manage releases"),
    ("OP-IT-06", "Deliver and support IT services"),
    ("OP-IT-07", "Manage IT service requests and access"),
    ("OP-IT-08", "Manage IT incidents and problems"),
    ("OP-IT-09", "Manage IT changes"),
    ("OP-IT-10", "Manage IT assets and configuration"),
    ("OP-IT-11", "Manage IT resilience, continuity and risk"),
    ("OP-IT-12", "Manage IT security and compliance"),
    ("OP-IT-13", "Manage IT suppliers and contracts"),
    ("OP-IT-14", "Manage IT knowledge and documentation"),
]

SEED_VERIFIED = False


def _looks_like_it_element(element_id: str) -> bool:
    return bool(re.match(r"^8(\.\d+)*$", str(element_id).strip()))


def load_pcf(path: Path | str | None = None) -> tuple[list[PcfEntry], str]:
    """Return (entries, source_label).

    Parses the official APQC Excel export if available. APQC's sheet layout
    has varied between releases, so the parser looks for the first two columns
    that behave like an element ID and a name rather than hard-coding headers.
    """
    path = Path(path) if path else DEFAULT_PCF_PATH
    if not path.exists():
        return (
            [
                PcfEntry(code, name, 2, "OpenProcess working taxonomy")
                for code, name in WORKING_IT_TAXONOMY
            ],
            "OpenProcess working taxonomy (official PCF not loaded)",
        )

    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    entries: list[PcfEntry] = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            cells = [c for c in row if c not in (None, "")]
            if len(cells) < 2:
                continue
            candidate_id = str(cells[0]).strip()
            if not _looks_like_it_element(candidate_id):
                continue
            name = str(cells[1]).strip()
            if not name or name.replace(".", "").isdigit():
                continue
            entries.append(
                PcfEntry(
                    id=candidate_id,
                    name=name,
                    level=candidate_id.count(".") + 1,
                    source="APQC PCF v8.0",
                )
            )
        if entries:
            break
    wb.close()

    if not entries:
        return (
            [
                PcfEntry(code, name, 2, "OpenProcess working taxonomy")
                for code, name in WORKING_IT_TAXONOMY
            ],
            "OpenProcess working taxonomy (PCF file found but not parseable)",
        )

    return entries, "APQC PCF v8.0 — Category 8.0 Manage Information Technology (IT)"
