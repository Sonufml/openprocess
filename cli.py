#!/usr/bin/env python3
"""OpenProcess command line.

    python cli.py samples/*.txt --out out

Reads policy documents, produces for each one:
    <key>.bpmn              standards-compliant BPMN 2.0, opens in ARIS
    <key>.confluence.xml    Confluence storage format, paste into a page
    <key>.md                Markdown documentation
    <key>.json              the intermediate process model
and one process_register.xlsx across all of them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openprocess import extract, to_bpmn_xml, evaluate, classify
from openprocess.exporters import to_confluence_storage, to_markdown, write_register


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            sys.exit("Reading PDFs needs pdfplumber: pip install pdfplumber")
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenProcess batch runner")
    parser.add_argument("documents", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--no-llm", action="store_true",
                        help="Force the deterministic parser even if GROQ_API_KEY is set")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    results = []

    for path in args.documents:
        if not path.exists():
            print(f"  skip  {path} (not found)")
            continue

        spec, method = extract(read_document(path), prefer_llm=not args.no_llm)
        spec.source_document = path.name
        classify(spec)
        report = evaluate(spec)
        results.append((spec, report))

        stem = args.out / spec.key
        stem.with_suffix(".bpmn").write_text(to_bpmn_xml(spec), encoding="utf-8")
        stem.with_suffix(".json").write_text(spec.to_json(), encoding="utf-8")
        stem.with_suffix(".md").write_text(to_markdown(spec, report), encoding="utf-8")
        (args.out / f"{spec.key}.confluence.xml").write_text(
            to_confluence_storage(spec, report, f"{spec.key}.bpmn"), encoding="utf-8"
        )

        counts = report["counts"]
        print(
            f"  {report['score']:>3}/100  {spec.name:<38} "
            f"[{method}]  {counts['errors']}E {counts['warnings']}W  "
            f"{spec.itil_practice or '—'}"
        )

    if results:
        register = write_register(results, args.out / "process_register.xlsx")
        print(f"\nRegister: {register}")
        print(f"Artefacts: {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
