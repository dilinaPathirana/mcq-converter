"""
Flask app: drag-and-drop web front end for the Sinhala legacy-font MCQ
PDF -> Excel converter, deployable as a Vercel Function.

Two modes, mirroring the desktop tool's two GUI tabs:
  POST /api/convert           - one PDF -> plain Q/Option Excel
  POST /api/convert-template  - Sinhala (required) + English/Tamil (optional)
                                 PDFs -> HTML-wrapped multi-language template

Vercel's Python runtime auto-detects this Flask app because it defines a
top-level `app` variable in an entrypoint file (api/index.py).
"""

import io
from flask import Flask, request, send_file, Response

from mcq_core import (
    extract_questions_from_pdf_bytes,
    build_simple_excel,
    build_template_rows,
    build_template_excel,
)

app = Flask(__name__)

MAX_UPLOAD_MB = 15
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sinhala MCQ PDF to Excel</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    max-width: 720px; margin: 40px auto; padding: 0 20px; color: #1a1a1a;
    background: #fafafa;
  }
  h1 { font-size: 22px; margin-bottom: 4px; }
  p.sub { color: #555; margin-top: 0; }
  .tabs { display: flex; gap: 8px; margin: 20px 0 16px; }
  .tab-btn {
    flex: 1; padding: 10px 14px; border: 1px solid #ccc; border-radius: 8px;
    background: #fff; cursor: pointer; font-size: 14px; font-weight: 600;
    color: #444;
  }
  .tab-btn.active { background: #1F4E78; color: #fff; border-color: #1F4E78; }
  .panel { display: none; }
  .panel.active { display: block; }
  .drop {
    border: 2px dashed #999; border-radius: 10px; padding: 28px; text-align: center;
    background: #fff; cursor: pointer; transition: border-color .15s, background .15s;
    font-size: 14px; color: #444;
  }
  .drop.drag { border-color: #1F4E78; background: #eef4fa; }
  .drop small { display: block; color: #888; margin-top: 6px; }
  .filename { margin-top: 8px; font-size: 13px; color: #1F4E78; font-weight: 600; word-break: break-all; }
  label.field { display: block; margin: 14px 0 4px; font-size: 13px; font-weight: 600; color: #333; }
  input[type=text] {
    width: 100%; padding: 8px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px;
  }
  button.go {
    margin-top: 18px; width: 100%; padding: 11px; border: none; border-radius: 8px;
    background: #1F4E78; color: #fff; font-size: 15px; font-weight: 600; cursor: pointer;
  }
  button.go:disabled { background: #99b3c4; cursor: not-allowed; }
  #status { margin-top: 14px; font-size: 13.5px; white-space: pre-wrap; line-height: 1.5; }
  #status.err { color: #b00020; }
  #status.ok { color: #1a7a33; }
  .hint { font-size: 12px; color: #888; margin-top: 22px; line-height: 1.5; }
</style>
</head>
<body>

<h1>Sinhala MCQ PDF &rarr; Excel</h1>
<p class="sub">Drop in an A/L-style MCQ PDF (FM Abhaya / FM Samantha / FM Ganganee fonts) and get a clean Unicode Excel file back.</p>

<div class="tabs">
  <button class="tab-btn active" data-tab="simple">Simple (one language)</button>
  <button class="tab-btn" data-tab="template">Template (Sinhala/English/Tamil)</button>
</div>

<div class="panel active" id="panel-simple">
  <div class="drop" id="drop-simple">
    Drop PDF here, or click to choose a file
    <small>Only .pdf is accepted &mdash; always more accurate than a .md/.txt export</small>
    <div class="filename" id="fn-simple"></div>
  </div>
  <input type="file" id="file-simple" accept="application/pdf" style="display:none">
  <button class="go" id="go-simple" disabled>Convert to Excel</button>
</div>

<div class="panel" id="panel-template">
  <label class="field">Sinhala PDF (required)</label>
  <div class="drop" id="drop-si">
    Drop Sinhala PDF here, or click to choose
    <div class="filename" id="fn-si"></div>
  </div>
  <input type="file" id="file-si" accept="application/pdf" style="display:none">

  <label class="field">English PDF (optional, same exam)</label>
  <div class="drop" id="drop-en">
    Drop English PDF here, or click to choose
    <div class="filename" id="fn-en"></div>
  </div>
  <input type="file" id="file-en" accept="application/pdf" style="display:none">

  <label class="field">Tamil PDF (optional, same exam)</label>
  <div class="drop" id="drop-ta">
    Drop Tamil PDF here, or click to choose
    <div class="filename" id="fn-ta"></div>
  </div>
  <input type="file" id="file-ta" accept="application/pdf" style="display:none">

  <label class="field">Level (e.g. AL / OL)</label>
  <input type="text" id="level" placeholder="AL">

  <label class="field">Subject</label>
  <input type="text" id="subject" placeholder="Biology">

  <button class="go" id="go-template" disabled>Convert to Excel</button>
</div>

<div id="status"></div>

<div class="hint">
  Nothing you upload is stored &mdash; each file is processed in memory for this
  one request and discarded. Module/sub-module, Tags, Difficulty Level and
  Answer are always left blank for you to fill in by hand (not something a
  script should guess). Anything the parser had to guess about is flagged in
  the Notes column &mdash; search for "NEEDS REVIEW" after each run.
</div>

<script>
function wireDrop(dropId, inputId, fnId, onChange) {
  const drop = document.getElementById(dropId);
  const input = document.getElementById(inputId);
  const fn = document.getElementById(fnId);
  drop.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files[0]) fn.textContent = input.files[0].name;
    onChange();
  });
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); drop.classList.remove('drag');
  }));
  drop.addEventListener('drop', e => {
    if (e.dataTransfer.files[0]) {
      input.files = e.dataTransfer.files;
      fn.textContent = input.files[0].name;
      onChange();
    }
  });
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.tab).classList.add('active');
    setStatus('');
  });
});

const goSimple = document.getElementById('go-simple');
wireDrop('drop-simple', 'file-simple', 'fn-simple', () => {
  goSimple.disabled = !document.getElementById('file-simple').files[0];
});

const goTemplate = document.getElementById('go-template');
wireDrop('drop-si', 'file-si', 'fn-si', updateTemplateBtn);
wireDrop('drop-en', 'file-en', 'fn-en', updateTemplateBtn);
wireDrop('drop-ta', 'file-ta', 'fn-ta', updateTemplateBtn);
function updateTemplateBtn() {
  goTemplate.disabled = !document.getElementById('file-si').files[0];
}

function setStatus(msg, cls) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = cls || '';
}

async function downloadResult(resp, fallbackName) {
  if (!resp.ok) {
    let msg = 'Conversion failed (HTTP ' + resp.status + ').';
    try { const j = await resp.json(); if (j.error) msg = j.error; } catch (e) {}
    throw new Error(msg);
  }
  const blob = await resp.blob();
  const disposition = resp.headers.get('Content-Disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const name = match ? match[1] : fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

goSimple.addEventListener('click', async () => {
  const file = document.getElementById('file-simple').files[0];
  if (!file) return;
  goSimple.disabled = true;
  setStatus('Converting ' + file.name + ' ...');
  try {
    const fd = new FormData();
    fd.append('pdf', file);
    const resp = await fetch('/api/convert', { method: 'POST', body: fd });
    const flaggedHeader = resp.headers.get('X-Flagged-Questions');
    await downloadResult(resp, file.name.replace(/\\.pdf$/i, '') + '.xlsx');
    let msg = 'Done. Excel file downloaded.';
    if (flaggedHeader) msg += '\\nDouble-check these question numbers in the Notes column: ' + flaggedHeader;
    setStatus(msg, 'ok');
  } catch (e) {
    setStatus(e.message, 'err');
  } finally {
    goSimple.disabled = false;
  }
});

goTemplate.addEventListener('click', async () => {
  const si = document.getElementById('file-si').files[0];
  if (!si) return;
  goTemplate.disabled = true;
  setStatus('Converting ...');
  try {
    const fd = new FormData();
    fd.append('si', si);
    const en = document.getElementById('file-en').files[0];
    const ta = document.getElementById('file-ta').files[0];
    if (en) fd.append('en', en);
    if (ta) fd.append('ta', ta);
    fd.append('level', document.getElementById('level').value);
    fd.append('subject', document.getElementById('subject').value);
    const resp = await fetch('/api/convert-template', { method: 'POST', body: fd });
    const flaggedHeader = resp.headers.get('X-Flagged-Rows');
    await downloadResult(resp, si.name.replace(/\\.pdf$/i, '') + '.xlsx');
    let msg = 'Done. Excel file downloaded.';
    if (flaggedHeader) msg += '\\nSee the Notes column for these row numbers: ' + flaggedHeader;
    setStatus(msg, 'ok');
  } catch (e) {
    setStatus(e.message, 'err');
  } finally {
    goTemplate.disabled = false;
  }
});
</script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    return Response(PAGE, mimetype="text/html")


@app.route("/api/convert", methods=["POST"])
def convert_simple():
    f = request.files.get("pdf")
    if f is None or not f.filename:
        return {"error": "No PDF uploaded."}, 400
    if not f.filename.lower().endswith(".pdf"):
        return {"error": "Please upload a .pdf file."}, 400

    try:
        pdf_bytes = f.read()
        questions, order = extract_questions_from_pdf_bytes(pdf_bytes)
        if not order:
            return {"error": "No numbered questions (1., 2., 3. ...) were found in this PDF."}, 422
        xlsx_bytes = build_simple_excel(questions, order)
    except Exception as e:
        return {"error": f"Conversion failed: {e}"}, 500

    flagged = [n for n in order if "[NEEDS REVIEW" in questions[n]["note"] or "[auto-" in questions[n]["note"]]
    out_name = f.filename.rsplit(".", 1)[0] + ".xlsx"
    resp = send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=out_name,
    )
    if flagged:
        resp.headers["X-Flagged-Questions"] = str(flagged)
        resp.headers["Access-Control-Expose-Headers"] = "X-Flagged-Questions, Content-Disposition"
    return resp


@app.route("/api/convert-template", methods=["POST"])
def convert_template():
    si_f = request.files.get("si")
    en_f = request.files.get("en")
    ta_f = request.files.get("ta")
    level = request.form.get("level", "")
    subject = request.form.get("subject", "")

    if si_f is None or not si_f.filename:
        return {"error": "A Sinhala PDF is required."}, 400
    for f, label in ((si_f, "Sinhala"), (en_f, "English"), (ta_f, "Tamil")):
        if f is not None and f.filename and not f.filename.lower().endswith(".pdf"):
            return {"error": f"{label} file must be a .pdf."}, 400

    try:
        si_q, si_order = extract_questions_from_pdf_bytes(si_f.read())
        en_q, _ = extract_questions_from_pdf_bytes(en_f.read()) if (en_f and en_f.filename) else ({}, [])
        ta_q, _ = extract_questions_from_pdf_bytes(ta_f.read()) if (ta_f and ta_f.filename) else ({}, [])
        if not si_order:
            return {"error": "No numbered questions (1., 2., 3. ...) were found in the Sinhala PDF."}, 422
        rows = build_template_rows(si_q, si_order, en_q, ta_q, level, subject)
        xlsx_bytes = build_template_excel(rows)
    except Exception as e:
        return {"error": f"Conversion failed: {e}"}, 500

    flagged = [i + 1 for i, r in enumerate(rows) if r["Notes"]]
    out_name = si_f.filename.rsplit(".", 1)[0] + ".xlsx"
    resp = send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=out_name,
    )
    if flagged:
        resp.headers["X-Flagged-Rows"] = str(flagged)
        resp.headers["Access-Control-Expose-Headers"] = "X-Flagged-Rows, Content-Disposition"
    return resp


if __name__ == "__main__":
    app.run(debug=True, port=5000)
