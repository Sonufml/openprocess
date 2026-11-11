# Running OpenProcess on Windows

Open PowerShell in this folder, then:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pytest
```

## 1. Run the tests (expect: 26 passed)

```powershell
python -m pytest -q
```

## 2. Batch run from the command line

```powershell
python cli.py samples\access_request.txt samples\change_approval.txt samples\incident_escalation.txt --no-llm --out out
```

Expected output:

```
   88/100  Fulfil application access request   [rulebased]  0E 4W   Service request management
   86/100  Approve standard change             [rulebased]  0E 5W   Change enablement
   60/100  Escalate major incident             [rulebased]  5E 10W  Incident management
```

Each process gets a `.bpmn`, `.json`, `.md` and `.confluence.xml` file in `out\`, plus one shared
`process_register.xlsx`. The same results are already in `example_output\`.

Open a `.bpmn` file at https://demo.bpmn.io (drag and drop) to see the diagram.

## 3. Web app

```powershell
python app.py
```

Open http://localhost:5000, click a sample (e.g. "incident escalation"), then "Analyse document".
Click a finding to highlight the element in the diagram. The page loads bpmn-js from unpkg.com,
so it needs internet access.

(The `Procfile` uses gunicorn, which is only for Linux hosting such as Railway. On Windows use
`python app.py`.)

## 4. With the LLM (real policy documents)

```powershell
$env:GROQ_API_KEY = "your-key"
python cli.py path\to\policy.txt --out out
```

Without a key, or with `--no-llm`, only the structured format in `samples\` can be parsed.
