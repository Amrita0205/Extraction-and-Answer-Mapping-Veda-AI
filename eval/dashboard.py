"""Turn eval/out/dataset_sweep.json (and eval/out/summary.json, if present)
into one self-contained HTML report worth showing someone.

    python eval/dashboard.py

Reads:
  eval/out/dataset_sweep.json   from eval/run_dataset_sweep.py   (required)
  eval/out/summary.json         from eval/run_eval.py            (optional —
                                 the hand-labelled ground-truth numbers)

Writes:
  eval/out/dashboard.html

The two inputs answer different questions on purpose. dataset_sweep.json is
breadth: did the pipeline run clean across every real subject, how much of
each paper did it find, how decisively did it resolve the mapping. It needs
no manual labelling, which is why it can cover all thirteen subjects.
summary.json is depth: precision/recall/F1 against ground truth a human
labelled by hand, on however many cases exist under eval/cases/. That is the
number worth calling "accuracy" — the sweep is the number worth calling
"tested across every subject in the syllabus."
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
SWEEP = OUT / "dataset_sweep.json"
SUMMARY = OUT / "summary.json"

STATUS = {"good": "#34ac15", "warn": "#e3600f", "bad": "#c0350a"}
METHOD_COLORS = {
    "label": "#2a78d6",
    "semantic": "#eb6834",
    "sequential": "#1baf7a",
    "none": "#eda100",
}
METHOD_LABEL = {
    "label": "Student's own label",
    "semantic": "Content match",
    "sequential": "Sequential fallback",
    "none": "Unresolved",
}
DISPLAY_NAME = {
    "phychology": "Psychology",
    "english_core": "English (Core)",
    "english_elective": "English (Elective)",
    "hindi_core": "Hindi (Core)",
    "business_studies": "Business Studies",
    "political_science": "Political Science",
}


def name_of(key: str) -> str:
    return DISPLAY_NAME.get(key, key.replace("_", " ").title())


def status_color(value, good=0.9, warn=0.7) -> str:
    if value is None:
        return "#9a9a94"
    if value >= good:
        return STATUS["good"]
    if value >= warn:
        return STATUS["warn"]
    return STATUS["bad"]


def pct(value) -> str:
    return f"{value*100:.0f}%" if value is not None else "—"


def esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def hbar_chart(title: str, subtitle: str, rows: list) -> str:
    ordered = sorted(rows, key=lambda r: (r[1] is None, -(r[1] or 0)))
    row_h = 28
    height = len(ordered) * row_h + 10
    width = 640
    label_w = 150
    track_w = width - label_w - 60
    bars = []
    for i, (label, value) in enumerate(ordered):
        y = i * row_h + 6
        bar_w = max((value or 0) * track_w, 3)
        color = status_color(value)
        bars.append(f'''
        <g>
          <text x="{label_w - 10}" y="{y + 14}" text-anchor="end" class="row-label">{esc(label)}</text>
          <rect x="{label_w}" y="{y + 3}" width="{track_w}" height="13" rx="6.5" class="track"/>
          <rect x="{label_w}" y="{y + 3}" width="{bar_w:.1f}" height="13" rx="6.5" fill="{color}"/>
          <text x="{label_w + track_w + 10}" y="{y + 14}" class="row-value">{pct(value)}</text>
        </g>''')
    return f'''
    <div class="chart-card">
      <h3>{esc(title)}</h3>
      <p class="chart-sub">{esc(subtitle)}</p>
      <svg viewBox="0 0 {width} {height}" width="100%" height="{height}">{''.join(bars)}</svg>
    </div>'''


def method_mix_chart(agg_methods: dict) -> str:
    total = sum(agg_methods.values()) or 1
    order = ["label", "semantic", "sequential", "none"]
    width = 640
    x = 0.0
    segs, legend = [], []
    for key in order:
        n = agg_methods.get(key, 0)
        if not n:
            continue
        w = width * n / total
        segs.append(
            f'<rect x="{x:.1f}" y="0" width="{max(w - 2, 0):.1f}" height="26" '
            f'rx="4" fill="{METHOD_COLORS[key]}"/>'
        )
        legend.append(
            f'<span class="legend-item"><span class="swatch" style="background:{METHOD_COLORS[key]}"></span>'
            f'{esc(METHOD_LABEL[key])} — {n} ({100 * n / total:.0f}%)</span>'
        )
        x += w
    return f'''
    <div class="chart-card">
      <h3>How answers got matched to questions</h3>
      <p class="chart-sub">Across all subjects combined. "Content match" leans on the reconstructed
      question wording, so treat it as the softer signal — the other three key off the student's
      own handwriting, not the question text.</p>
      <svg viewBox="0 0 {width} 26" width="100%" height="26">{''.join(segs)}</svg>
      <div class="legend">{''.join(legend)}</div>
    </div>'''


def build(sweep: dict, summary) -> str:
    subjects = sweep["subjects"]
    ok = {k: v for k, v in subjects.items() if "error" not in v}
    failed = {k: v for k, v in subjects.items() if "error" in v}

    total_q = sum(v["questions"]["extracted"] for v in ok.values())
    coverages = [v["questions"]["coverage_vs_oracle"] for v in ok.values()
                 if v["questions"]["coverage_vs_oracle"] is not None]
    resolutions = [v["mapping"]["resolution_rate"] for v in ok.values()
                   if v["mapping"]["resolution_rate"] is not None]
    mean_coverage = sum(coverages) / len(coverages) if coverages else None
    mean_resolution = sum(resolutions) / len(resolutions) if resolutions else None

    agg_methods: dict = {}
    for v in ok.values():
        for k, n in v["mapping"]["by_method"].items():
            agg_methods[k] = agg_methods.get(k, 0) + n

    tiles = [
        ("Subjects run", f"{len(ok)}/{len(subjects)}", None),
        ("Questions extracted", str(total_q), None),
        ("Mean extraction coverage", pct(mean_coverage), status_color(mean_coverage)),
        ("Mean mapping resolution", pct(mean_resolution), status_color(mean_resolution)),
    ]
    if summary:
        tiles.append(("Ground-truth extraction F1 (labelled sample)",
                       f"{summary['extraction_f1_median'] * 100:.0f}%",
                       status_color(summary["extraction_f1_median"])))
        tiles.append(("Ground-truth highlight IoU (labelled sample)",
                       f"{summary['highlight_iou_median'] * 100:.0f}%",
                       status_color(summary["highlight_iou_median"])))

    tiles_html = "".join(
        f'<div class="tile"><div class="tile-value" style="color:{color or "#1c1c1a"}">{value}</div>'
        f'<div class="tile-label">{esc(label)}</div></div>'
        for label, value, color in tiles
    )

    coverage_chart = hbar_chart(
        "Question extraction coverage",
        "Extracted question numbers vs. an independent count of the paper's own printed markers — "
        "not derived from our own output.",
        [(name_of(k), v["questions"]["coverage_vs_oracle"]) for k, v in ok.items()],
    )
    resolution_chart = hbar_chart(
        "Mapping resolution rate",
        "Share of extracted questions that got matched to a written answer.",
        [(name_of(k), v["mapping"]["resolution_rate"]) for k, v in ok.items()],
    )
    method_chart = method_mix_chart(agg_methods)

    rows_html = "".join(f'''
      <tr>
        <td>{esc(name_of(k))}</td>
        <td>{v["questions"]["extracted"]}</td>
        <td>{pct(v["questions"]["coverage_vs_oracle"])}</td>
        <td>{v["mapping"]["answered"]}</td>
        <td>{v["mapping"]["unanswered"]}</td>
        <td>{v["mapping"]["unmatched"]}</td>
        <td>{pct(v["mapping"]["avg_confidence"])}</td>
        <td>{v["elapsed_s"]}s</td>
      </tr>''' for k, v in sorted(ok.items(), key=lambda kv: name_of(kv[0])))

    failed_html = ""
    if failed:
        items = "".join(f"<li><strong>{esc(name_of(k))}</strong> — {esc(v['error'])}</li>"
                         for k, v in failed.items())
        failed_html = f'<div class="callout bad"><h3>Failed to run</h3><ul>{items}</ul></div>'

    ground_truth_html = ""
    if not summary:
        ground_truth_html = '''
        <div class="callout warn">
          <h3>No hand-labelled ground truth yet</h3>
          <p>Everything above is a breadth/coverage sweep, not an accuracy score. Run
          <code>python eval/run_eval.py</code> against a couple of hand-labelled cases (see
          <code>eval/README.md</code>) to get real precision/recall/F1 numbers — those are the
          ones worth quoting as "accuracy."</p>
        </div>'''

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VedaAI — extraction accuracy report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    --bg-1: #eeeeee; --bg-2: #dadada; --ink: #1c1c1a; --ink-soft: #55554f;
    --card: rgba(255,255,255,0.72); --line: rgba(0,0,0,0.08);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 28px 80px;
    font-family: -apple-system, "Segoe UI", ui-sans-serif, system-ui, sans-serif;
    color: var(--ink);
    background: linear-gradient(160deg, var(--bg-1), var(--bg-2)) fixed;
    min-height: 100vh;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; }}
  h1 {{ font-size: 26px; font-weight: 800; letter-spacing: -0.01em; margin: 0 0 4px; }}
  .meta {{ color: var(--ink-soft); font-size: 13px; margin-bottom: 28px; }}
  .tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap: 12px; margin-bottom: 24px; }}
  .tile {{ background: var(--card); backdrop-filter: blur(12px); border-radius: 16px; padding: 16px 18px; border: 1px solid var(--line); }}
  .tile-value {{ font-size: 24px; font-weight: 800; }}
  .tile-label {{ font-size: 12px; color: var(--ink-soft); margin-top: 4px; }}
  .chart-card {{ background: var(--card); backdrop-filter: blur(12px); border-radius: 18px; padding: 20px 22px; border: 1px solid var(--line); margin-bottom: 16px; }}
  .chart-card h3 {{ margin: 0 0 2px; font-size: 15px; font-weight: 700; }}
  .chart-sub {{ margin: 0 0 12px; font-size: 12px; color: var(--ink-soft); line-height: 1.5; max-width: 640px; }}
  .row-label {{ font-size: 12px; fill: var(--ink); }}
  .row-value {{ font-size: 12px; fill: var(--ink-soft); font-variant-numeric: tabular-nums; }}
  .track {{ fill: rgba(0,0,0,0.06); }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 12px; color: var(--ink-soft); }}
  .legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
  .swatch {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }}
  th {{ color: var(--ink-soft); font-weight: 600; }}
  td {{ font-variant-numeric: tabular-nums; }}
  .callout {{ border-radius: 16px; padding: 16px 20px; margin-bottom: 16px; border: 1px solid var(--line); }}
  .callout.warn {{ background: rgba(227,96,15,0.08); border-color: rgba(227,96,15,0.25); }}
  .callout.bad {{ background: rgba(195,53,10,0.08); border-color: rgba(195,53,10,0.25); }}
  .callout h3 {{ margin: 0 0 6px; font-size: 14px; }}
  .callout p, .callout ul {{ margin: 0; font-size: 12.5px; color: var(--ink-soft); line-height: 1.6; }}
  code {{ background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 5px; font-size: 11.5px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Extraction &amp; answer-mapping — accuracy report</h1>
    <div class="meta">Generated {esc(sweep.get("generated_at", ""))} ·
      provider <strong>{esc(sweep.get("provider", "?"))}</strong> ·
      model <strong>{esc(sweep.get("model", "?"))}</strong></div>

    <div class="tiles">{tiles_html}</div>

    <div class="callout warn">
      <h3>Reading this honestly</h3>
      <p>Every question paper in this dataset is an AI <em>reconstruction</em> from its answer
      booklet (each PDF says so on its own first page) — real handwriting to transcribe, but not
      an independently set exam. The coverage and resolution numbers below are legitimate; the
      "content match" share of the mapping mix leans on question wording derived from the answer
      itself, so read that one slice as a softer signal than the rest.</p>
    </div>

    {ground_truth_html}
    {failed_html}

    {coverage_chart}
    {resolution_chart}
    {method_chart}

    <div class="chart-card">
      <h3>Per-subject detail</h3>
      <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Subject</th><th>Questions</th><th>Coverage</th><th>Answered</th>
        <th>Unanswered</th><th>Unmatched</th><th>Avg confidence</th><th>Time</th></tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      </div>
    </div>
  </div>
</body>
</html>'''


def main() -> int:
    if not SWEEP.exists():
        print(f"No {SWEEP} — run: python eval/run_dataset_sweep.py")
        return 2
    sweep = json.loads(SWEEP.read_text())
    summary = json.loads(SUMMARY.read_text()) if SUMMARY.exists() else None
    (OUT / "dashboard.html").write_text(build(sweep, summary))
    print(f"written to {OUT / 'dashboard.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
