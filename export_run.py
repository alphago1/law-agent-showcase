"""Export a verified fictional dsh run to the static replay and a Word redline."""
import argparse
from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
from pathlib import Path
import shutil

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
AUTHOR = "DeepSeek Flash"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_changes(before, after):
    stable = [block for block in SequenceMatcher(None, before, after, autojunk=False).get_matching_blocks()
              if block.size >= 12 or block.size == 0]
    i = j = 0
    for start_old, start_new, length in stable:
        if start_old > i:
            yield "del", before[i:start_old]
        if start_new > j:
            yield "ins", after[j:start_new]
        if length:
            yield "same", before[start_old:start_old + length]
        i, j = start_old + length, start_new + length


def tracked_run(paragraph, operation, text, revision, captured):
    element = OxmlElement("w:" + operation)
    element.set(qn("w:id"), str(revision))
    element.set(qn("w:author"), AUTHOR)
    element.set(qn("w:date"), captured)
    run = OxmlElement("w:r")
    for index, line in enumerate(text.split("\n")):
        if index:
            run.append(OxmlElement("w:br"))
        content = OxmlElement("w:delText" if operation == "del" else "w:t")
        content.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        content.text = line
        run.append(content)
    element.append(run)
    paragraph._p.append(element)


def make_docx(path, contract, submission, captured):
    doc = Document()
    doc.core_properties.title = contract["title"] + "修订稿"
    doc.core_properties.author = AUTHOR
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.92)
    for name, size in (("Normal", 11), ("Title", 20), ("Heading 1", 13)):
        style = doc.styles[name]
        style.font.name = "Microsoft YaHei"
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        fonts = style.element.get_or_add_rPr().rFonts
        fonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    title_properties = doc.styles["Title"].element.get_or_add_pPr()
    title_border = title_properties.find(qn("w:pBdr"))
    if title_border is not None:
        title_properties.remove(title_border)
    heading_format = doc.styles["Heading 1"].paragraph_format
    heading_format.space_before = Pt(13)
    heading_format.space_after = Pt(5)
    normal = doc.styles["Normal"].paragraph_format
    normal.line_spacing = 1.12
    normal.space_after = Pt(7)
    doc.add_paragraph(contract["title"] + "修订稿", style="Title")
    doc.add_paragraph("本合同按乙方立场修订，供主办律师复核。")
    edits = {edit["clause"]: edit for edit in submission["edits"]}
    revision = 100
    for clause in contract["clauses"]:
        heading = doc.add_heading(clause["heading"], level=1)
        edit = edits.get(clause["id"])
        if edit is None:
            doc.add_paragraph(clause["text"])
            continue
        doc.add_comment(heading.runs, text=f'{edit["severity"]}风险。{edit["comment"]}\n证据：' +
                        "、".join(edit["evidenceIds"]), author=AUTHOR, initials="DS")
        position = doc.add_paragraph()
        body = edit["replacement"].removeprefix(clause["heading"] + "\n")
        for operation, text in text_changes(clause["text"], body):
            if operation == "same":
                position.add_run(text)
            else:
                tracked_run(position, operation, text, revision, captured)
                revision += 1
    doc.save(path)


def export(run):
    workspace = run / "workspace"
    browser_events = read_events(workspace / "trace/browser.jsonl")
    dsh_events = read_events(run / "dsh.jsonl")
    submission = read_json(workspace / "submission.json")
    contract = read_json(workspace / "contract.json")
    submitted = {item["callId"] for item in dsh_events
                 if item["type"] == "tool_call" and item["tool"] == "mcp__c06__submit"
                 and item["input"] == submission}
    if not any(item["type"] == "tool_result" and item["status"] == "completed" and
               item["callId"] in submitted for item in dsh_events):
        raise ValueError("No matching successful dsh submission.")
    ids = {clause["id"] for clause in contract["clauses"]}
    edited = [edit["clause"] for edit in submission["edits"]]
    if len(edited) != len(ids) or set(edited) != ids:
        raise ValueError("The run did not cover the four requested clauses.")
    observed = {event["record"] for event in browser_events if event["action"] == "open"}
    if ({ref for edit in submission["edits"] for ref in edit["evidenceIds"]} - observed
            or not any(event["action"] == "search" for event in browser_events)):
        raise ValueError("Required browser evidence is missing.")
    assets = SITE / "assets"
    frames = assets / "replay"
    frames.mkdir(parents=True, exist_ok=True)
    for event in browser_events:
        name = Path(event["screenshot"]).name
        shutil.copyfile(workspace / "trace" / name, frames / name)
    payload = {"harness": "dsh", "model": "deepseek-flash",
               "contract": contract, "browser": browser_events, "submission": submission}
    captured = datetime.fromisoformat(browser_events[-1]["capturedAt"]).astimezone(timezone.utc)
    make_docx(assets / "c06-contract-redline.docx", contract, submission,
              captured.strftime("%Y-%m-%dT%H:%M:%SZ"))
    (SITE / "run-data.js").write_text("window.C06_RUN = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
                                    encoding="utf-8")
    print(f"Exported {len(browser_events)} captured browser steps and {len(edited)} clause revisions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    export(parser.parse_args().run_dir)

