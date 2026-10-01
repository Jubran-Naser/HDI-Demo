"""The results report: one self-contained HTML page built from saved runs. The AI model doesn't run again.

Run from the repo root:
    python -m eval.report 2026-10-01 baseline date-as-written better-prompt
(the run names in the order the runs were made; the last one is shown in detail)

Writes <date>_report.html next to the run files, and <date>_report.pdf when WeasyPrint is installed
(GitHub shows the PDF directly; it shows an HTML file only as source). Charts are plain SVG drawn here.
"""

import json
import sys
from collections import Counter
from html import escape
from pathlib import Path

import yaml

from app.core.escalation import FIELDS
from app.core.text_matching import amounts_in_text, dates_in_text

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"

# grade → (colour, ink on that colour, plain words), in bar order: automatic first, then to a person
GRADES = {
    "correct automatic": ("#3a9a5b", "#ffffff", "automatic, correct"),
    "wrong automatic": ("#d1453b", "#ffffff", "automatic, wrong"),
    "rightly escalated": ("#7d7d7d", "#ffffff", "to a person, rightly"),
    "needlessly escalated": ("#c9c9c9", "#333333", "to a person, needlessly"),
}
KIND_NAMES = {
    "clean": "clean (no trap)",
    "two_dates": "two dates",
    "two_amounts": "two amounts",
    "two_plates": "two plates",
    "correction": "a correction in the text",
    "missing_field": "a missing field",
    "unusual_date": "unusual date form",
    "forwarded_thread": "forwarded thread",
    "informal_messy": "informal, messy text",
}
FIELD_NAMES = {"policy_number": "policy number", "incident_date": "incident date",
               "amount_claimed": "amount", "licence_plate": "licence plate"}
SECTIONS = {"grades": "What happened to the 50 claims, per run", "fields": "Per field, per run",
            "kinds": "Per kind of claim", "choosing": "Where the AI model is needed: choosing between candidates",
            "missed": "Every claim the AI model got wrong", "runs": "Runs and limits"}
LIMITS = (
    "50 mock claims, written for this demo: 10 clean, and 8 kinds of messiness with 5 claims each. "
    "For each kind, the results show whether the approach handles it. Kinds not in the set remain untested. "
    "The set is too small and too artificial to promise an error rate on real claims; that would need real "
    "(anonymized) claims at a much larger scale. The prompt of the last run was revised after seeing the "
    "first run's results on this same set (see README)."
)


# --- loading and small helpers --------------------------------------------------------------

def load_run(run_date: str, label: str) -> tuple[dict, list[dict]]:
    lines = (RESULTS_DIR / f"{run_date}_{label}.jsonl").read_text().splitlines()
    header, *graded = [json.loads(line) for line in lines]
    return header, graded


def run_name(position: int, label: str) -> str:
    return f"{position} · {label.replace('-', ' ')}"


def shown(field: str, value: object) -> str:
    if value is None:
        return "(nothing)"
    return f"{value:.2f}" if field == "amount_claimed" else str(value)


def what_it_tests(mock_claim: dict) -> str:
    return f"{KIND_NAMES[mock_claim['kind']].capitalize()}: {mock_claim['trap']}"


def pill(grade: str) -> str:
    colour, ink, words = GRADES[grade]
    return f'<span class="pill" style="background:{colour};color:{ink}">{escape(words)}</span>'


def html_table(columns: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


# --- the two charts (SVG, drawn inside the page) --------------------------------------------

def svg(width: float, height: float, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
            f'width="{width:.0f}" height="{height:.0f}" font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif" role="img" aria-label="{escape(title)}">{body}</svg>')


def legend(x: float, y: float) -> tuple[str, float]:
    parts = []
    for colour, _, words in GRADES.values():
        parts.append(f'<rect x="{x:.0f}" y="{y - 10}" width="12" height="12" rx="2" fill="{colour}"/>'
                     f'<text x="{x + 17:.0f}" y="{y}" font-size="12" fill="#333">{escape(words)}</text>')
        x += 34 + 6.6 * len(words)
    return "".join(parts), x


def grades_chart(runs: dict[str, list[dict]]) -> str:
    """One stacked bar per run: what happened to the claims."""
    label_w, bar_w, bar_h, gap, top = 150, 560, 30, 16, 50
    legend_svg, legend_end = legend(12, 22)
    body = [legend_svg]
    for i, (label, graded) in enumerate(runs.items()):
        y = top + i * (bar_h + gap)
        counts = Counter(line["grade"] for line in graded)
        body.append(f'<text x="{label_w - 10}" y="{y + bar_h / 2 + 4}" font-size="13" text-anchor="end" '
                    f'fill="#222">{escape(run_name(i + 1, label))}</text>')
        x = label_w
        for grade, (colour, ink, _) in GRADES.items():
            width = bar_w * counts[grade] / len(graded)
            if width:
                body.append(f'<rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="{bar_h}" fill="{colour}" '
                            f'stroke="#fff" stroke-width="1"/>'
                            f'<text x="{x + width / 2:.1f}" y="{y + bar_h / 2 + 4}" font-size="12" font-weight="600" '
                            f'text-anchor="middle" fill="{ink}">{counts[grade]}</text>')
            x += width
    axis_y = top + len(runs) * (bar_h + gap) - 4
    total = len(next(iter(runs.values())))
    body.append(f'<text x="{label_w}" y="{axis_y + 10}" font-size="11" fill="#666">0</text>'
                f'<text x="{label_w + bar_w}" y="{axis_y + 10}" font-size="11" text-anchor="end" '
                f'fill="#666">{total} mock claims</text>')
    return svg(max(label_w + bar_w + 20, legend_end), axis_y + 20, "".join(body), SECTIONS["grades"])


def kinds_chart(runs: dict[str, list[dict]]) -> str:
    """Per kind of claim, one grid per run: one square per claim, in the same position in every run."""
    label_w, square, gap, panel_gap, top = 170, 13, 3, 28, 62
    panel_w = 10 * (square + gap)
    legend_svg, legend_end = legend(12, 22)
    body = [legend_svg]
    for p, (label, graded) in enumerate(runs.items()):
        panel_x = label_w + p * (panel_w + panel_gap)
        body.append(f'<text x="{panel_x}" y="{top - 10}" font-size="12" font-weight="600" '
                    f'fill="#222">{escape(run_name(p + 1, label))}</text>')
        for row, (kind, name) in enumerate(KIND_NAMES.items()):
            y = top + row * (square + gap + 4)
            if p == 0:
                body.append(f'<text x="{label_w - 10}" y="{y + square - 2}" font-size="12" text-anchor="end" '
                            f'fill="#222">{escape(name)}</text>')
            for column, line in enumerate(line for line in graded if line["kind"] == kind):
                body.append(f'<rect x="{panel_x + column * (square + gap)}" y="{y}" width="{square}" '
                            f'height="{square}" rx="2" fill="{GRADES[line["grade"]][0]}"/>')
    height = top + len(KIND_NAMES) * (square + gap + 4) + 10
    return svg(max(label_w + len(runs) * (panel_w + panel_gap), legend_end), height, "".join(body), SECTIONS["kinds"])


# --- page parts -----------------------------------------------------------------------------

def headline(runs: dict[str, list[dict]]) -> str:
    names = [run_name(i + 1, label) for i, label in enumerate(runs)]
    first, latest = Counter(l["grade"] for l in runs[next(iter(runs))]), Counter(l["grade"] for l in list(runs.values())[-1])
    total = len(list(runs.values())[-1])
    tiles = "".join(f'<div class="tile" style="background:{colour};color:{ink}"><b>{latest[grade]}</b>'
                    f'<span>{escape(words)}</span></div>' for grade, (colour, ink, words) in GRADES.items())
    return f"""
<p><b>What we measured:</b> {total} mock claims (10 clean, 40 with a known trap) sent through the service.
Each claim either goes through automatically or goes to a person, and each result is checked against the answer key.</p>
<p><b>Latest run ({escape(names[-1])}):</b></p>
<div class="tiles">{tiles}</div>
<p><b>Since the baseline:</b> automatic and correct went from {first['correct automatic']} to
{latest['correct automatic']}. Automatic but wrong went from {first['wrong automatic']} to {latest['wrong automatic']}.</p>"""


def contents() -> str:
    items = "".join(f'<li><a href="#{key}">{escape(title)}</a></li>' for key, title in SECTIONS.items())
    return f'<nav><ol>{items}<li><a href="#appendix">Appendix: full texts of the missed claims</a></li></ol></nav>'


def fields_table(runs: dict[str, list[dict]]) -> str:
    rows = [[escape(FIELD_NAMES[field]), *(f"{sum(l['fields_right'][field] for l in graded)} of {len(graded)}"
                                           for graded in runs.values())] for field in FIELDS]
    return html_table(["field the AI model got right", *(run_name(i + 1, l) for i, l in enumerate(runs))], rows)


def choosing_block(graded: list[dict], mock_claims: dict[str, dict]) -> str:
    """Pattern search finds every date and amount; with more than one, only the AI model can choose."""
    items = []
    for field, name, find in (("incident_date", "date", dates_in_text), ("amount_claimed", "amount", amounts_in_text)):
        several = [l for l in graded if len(set(find(mock_claims[l["id"]]["claim_text"]))) > 1]
        right = sum(l["fields_right"][field] for l in several)
        items.append(f"<li>{name.capitalize()}s: {len(several)} claims had more than one {name}, "
                     f"and the AI model chose right in {right}.</li>")
    return ("<p>Plain pattern search finds every date and amount in a claim. When a claim contains more than one, "
            "only the AI model can choose the right one.</p><ul>" + "".join(items) + "</ul>")


def missed_table(missed: list[dict], mock_claims: dict[str, dict]) -> str:
    rows = []
    for line in missed:
        wrong = [field for field in FIELDS if not line["fields_right"][field]]
        rows.append([
            f'<a href="#claim-{line["id"]}">{escape(what_it_tests(mock_claims[line["id"]]))}</a>',
            escape(", ".join(FIELD_NAMES[f] for f in wrong)),
            escape("; ".join(shown(f, line["ai_model_answer"][f]) for f in wrong)),
            escape("; ".join(shown(f, line["correct"][f]) for f in wrong)),
            pill(line["grade"]),
        ])
    return ("<p>The mistake isn't always in the field the claim was built to test.</p>"
            + html_table(["What the claim tests", "Field wrong", "AI model said", "Answer key", "What happened"], rows))


def appendix(missed: list[dict], mock_claims: dict[str, dict]) -> str:
    parts = []
    for line in missed:
        mock_claim = mock_claims[line["id"]]
        rows = [[escape(FIELD_NAMES[f]), escape(shown(f, line["ai_model_answer"][f])), escape(shown(f, line["correct"][f])),
                 '<span class="ok">✓</span>' if line["fields_right"][f] else '<span class="bad">✗</span>'] for f in FIELDS]
        flags = [f"{FIELD_NAMES[r['field']]}: {r['detail']}" for r in line["proxy_check_results"] if not r["passed"]]
        parts.append(f"""
<article id="claim-{line['id']}">
  <h3>{escape(what_it_tests(mock_claim))}</h3>
  <p class="meta">{pill(line['grade'])} claim {line['id']} in <code>eval/mock_claims.yaml</code></p>
  <pre>{escape(mock_claim['claim_text'].rstrip())}</pre>
  {html_table(["field", "AI model", "answer key", ""], rows)}
  <p class="meta">Proxy checks that flagged: {escape("; ".join(flags) or "none")}</p>
</article>""")
    return "".join(parts)


def runs_table(loaded: dict[str, tuple[dict, list[dict]]]) -> str:
    notes = {run["label"]: run for run in yaml.safe_load((EVAL_DIR / "runs.yaml").read_text())}
    rows = [[escape(run_name(i + 1, label)), escape(notes[label]["what_changed"]), f"<code>{notes[label]['code']}</code>",
             escape(header["ai_model"]), str(header["mock_claims"])]
            for i, (label, (header, _)) in enumerate(loaded.items())]
    return html_table(["run", "what changed in this run", "code (commit)", "AI model", "mock claims"], rows)


CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font: 14px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1d1d1b; margin: 0; background: #fff; }
main { max-width: 860px; margin: 0 auto; padding: 24px 16px; }
h1 { font-size: 24px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 32px 0 10px; border-bottom: 1px solid #e3e3e3; padding-bottom: 4px; }
h3 { font-size: 15px; margin: 18px 0 4px; }
.sub { color: #666; margin: 0 0 16px; }
nav ol { margin: 8px 0 0; padding-left: 20px; } nav a { color: #1d1d1b; }
.tiles { margin: 6px 0 10px; font-size: 0; }
.tile { display: inline-block; vertical-align: top; box-sizing: border-box; width: 23.5%; margin-right: 2%;
        border-radius: 6px; padding: 8px 12px; font-size: 14px; }
.tile:last-child { margin-right: 0; }
.tile b { display: block; font-size: 24px; line-height: 1.1; } .tile span { font-size: 12px; }
svg { max-width: 100%; height: auto; display: block; margin: 8px 0; }
table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 8px 0; }
tr { page-break-inside: avoid; }
th, td { text-align: left; vertical-align: top; padding: 5px 8px; border-bottom: 1px solid #e3e3e3; }
th { font-weight: 600; background: #f6f6f4; }
td a { color: #1d1d1b; }
.pill { display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 12px; white-space: nowrap; }
.ok { color: #3a9a5b; font-weight: 700; } .bad { color: #d1453b; font-weight: 700; }
.meta { color: #555; font-size: 12px; margin: 4px 0; }
pre { white-space: pre-wrap; background: #f6f6f4; border-radius: 6px; padding: 10px 12px; font-size: 12px; }
article { page-break-inside: avoid; }
#appendix { page-break-before: always; }
"""


def main() -> None:
    run_date, *labels = sys.argv[1:]
    loaded = {label: load_run(run_date, label) for label in labels}
    runs = {label: graded for label, (_, graded) in loaded.items()}
    latest_name = run_name(len(labels), labels[-1])
    latest = runs[labels[-1]]
    mock_claims = {c["id"]: c for c in yaml.safe_load((EVAL_DIR / "mock_claims.yaml").read_text())}
    missed = [line for line in latest if not all(line["fields_right"].values())]

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offline measuring · results {run_date}</title><style>{CSS}</style></head><body><main>
<h1>Offline measuring · results</h1>
<p class="sub">local-claim-intake · {run_date} · {len(labels)} runs</p>
{headline(runs)}
{contents()}
<h2 id="grades">1 · {SECTIONS["grades"]}</h2>
{grades_chart(runs)}
<h2 id="fields">2 · {SECTIONS["fields"]}</h2>
{fields_table(runs)}
<h2 id="kinds">3 · {SECTIONS["kinds"]}</h2>
<p>One row per kind of claim, one square per claim. A claim keeps its position in every run.</p>
{kinds_chart(runs)}
<h2 id="choosing">4 · {escape(SECTIONS["choosing"])} ({escape(latest_name)})</h2>
{choosing_block(latest, mock_claims)}
<h2 id="missed">5 · {SECTIONS["missed"]} ({escape(latest_name)}: {len(missed)})</h2>
{missed_table(missed, mock_claims)}
<h2 id="runs">6 · {SECTIONS["runs"]}</h2>
{runs_table(loaded)}
<p>{escape(LIMITS)}</p>
<h2 id="appendix">Appendix · full texts of the missed claims ({escape(latest_name)})</h2>
{appendix(missed, mock_claims)}
</main></body></html>
"""
    report_file = RESULTS_DIR / f"{run_date}_report.html"
    report_file.write_text(page)
    print(f"saved: {report_file}")
    try:
        from weasyprint import HTML
    except ImportError:
        print("PDF skipped: WeasyPrint isn't installed (pip install weasyprint)")
        return
    HTML(filename=str(report_file)).write_pdf(str(report_file.with_suffix(".pdf")))
    print(f"saved: {report_file.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
