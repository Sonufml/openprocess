#!/usr/bin/env python3
"""OpenProcess web application."""

from __future__ import annotations

import io
import os
import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from openprocess import extract, to_bpmn_xml, evaluate, classify, rule_catalogue
from openprocess.exporters import to_confluence_storage, to_markdown, write_register
from openprocess.frameworks import load_pcf

BASE = Path(__file__).resolve().parent
SAMPLES = BASE / "samples"
MAX_UPLOAD_MB = 8

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# analysed models, keyed by process key, so downloads don't re-run extraction
_CACHE: dict[str, tuple] = {}


def read_upload(file_storage) -> str:
    name = (file_storage.filename or "").lower()
    data = file_storage.read()
    if name.endswith(".pdf"):
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError(
                "PDF support needs pdfplumber. Install it, or paste the text instead."
            )
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if name.endswith(".docx"):
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError(
                "Word support needs python-docx. Install it, or paste the text instead."
            )
        document = Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    return data.decode("utf-8", errors="replace")


@app.get("/")
def index():
    _, pcf_source = load_pcf()
    return render_template(
        "index.html",
        samples=sorted(p.name for p in SAMPLES.glob("*.txt")),
        pcf_source=pcf_source,
        llm_ready=bool(os.environ.get("GROQ_API_KEY")),
        rule_count=len(rule_catalogue()),
    )


@app.get("/api/sample/<name>")
def sample(name: str):
    path = SAMPLES / Path(name).name
    if not path.exists():
        return jsonify({"error": f"No sample named {name}."}), 404
    return jsonify({"text": path.read_text(encoding="utf-8")})


@app.post("/api/analyse")
def analyse():
    try:
        source_name = "pasted text"
        if "file" in request.files and request.files["file"].filename:
            upload = request.files["file"]
            source_name = upload.filename
            document = read_upload(upload)
        else:
            payload = request.get_json(silent=True) or {}
            document = (request.form.get("text") or payload.get("text") or "").strip()

        if not document:
            return jsonify({
                "error": "Nothing to analyse. Paste a policy document or upload a file."
            }), 400

        spec, method = extract(document, prefer_llm=True)
        spec.source_document = source_name
        classification = classify(spec)
        report = evaluate(spec)
        bpmn_xml = to_bpmn_xml(spec)

        _CACHE[spec.key] = (spec, report, bpmn_xml)

        return jsonify({
            "key": spec.key,
            "method": method,
            "spec": spec.to_dict(),
            "classification": classification,
            "report": report,
            "bpmn": bpmn_xml,
        })
    except Exception as exc:
        app.logger.error(traceback.format_exc())
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


@app.get("/download/<key>.<kind>")
def download(key: str, kind: str):
    if key not in _CACHE:
        return jsonify({"error": "Analyse the document again — this result expired."}), 404
    spec, report, bpmn_xml = _CACHE[key]

    if kind == "bpmn":
        payload, mimetype = bpmn_xml, "application/xml"
    elif kind == "md":
        payload, mimetype = to_markdown(spec, report), "text/markdown"
    elif kind == "xml":
        payload, mimetype = (
            to_confluence_storage(spec, report, f"{spec.key}.bpmn"),
            "application/xml",
        )
    elif kind == "json":
        payload, mimetype = spec.to_json(), "application/json"
    elif kind == "xlsx":
        target = BASE / "out" / f"{spec.key}_register.xlsx"
        write_register([(spec, report)], target)
        return send_file(target, as_attachment=True,
                         download_name=f"{spec.key}_register.xlsx")
    else:
        return jsonify({"error": f"Unknown format '{kind}'."}), 400

    return send_file(
        io.BytesIO(payload.encode("utf-8")),
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"{spec.key}.{kind}",
    )


@app.get("/api/rules")
def rules():
    return jsonify({"rules": rule_catalogue()})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": f"File is larger than {MAX_UPLOAD_MB} MB."}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
