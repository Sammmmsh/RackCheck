"""Static escaped reports and conservative recovery comparisons."""
from datetime import datetime
from html import escape
import json


def markdown(report):
    def text(value):
        return escape(str(value)).replace("|", r"\|").replace("\n", " ")
    lines = [f"# RackCheck report: {report.status}", "",
             f"Host: {text(report.snapshot.hostname)} | Context: **{report.snapshot.context}**",
             f"Collected: {text(report.snapshot.collected_at)}", ""]
    if report.snapshot.context != "live":
        lines += ["**Lab/fixture evidence: not production or physical-hardware validation.**", ""]
    lines += ["| Status | Check | Finding |", "| --- | --- | --- |"]
    lines += [f"| {f.status} | {text(f.check_id)} | {text(f.summary)} |" for f in report.findings]
    lines += ["", "## Recovery and evidence", ""]
    for f in report.findings:
        lines += [f"### {text(f.check_id)}", "", text(f.summary), ""]
        lines += ["- " + text(step) for step in f.recovery]
        lines += ["- Evidence: " + ", ".join(text(k) for k in f.evidence), ""]
    lines += ["## Observation details", "", "Review identifiers and log messages before sharing.", ""]
    lines += ["    " + line for line in json.dumps(report.snapshot.to_dict(), indent=2).splitlines()]
    return "\n".join(lines) + "\n"


def html(report):
    rows = []
    for f in report.findings:
        steps = "".join("<li>" + escape(step) + "</li>" for step in f.recovery)
        rows.append(f'<section><div class="label {f.status}">{f.status}</div><h2>{escape(f.check_id)}</h2>'
                    f'<p>{escape(f.summary)}</p><ul>{steps}</ul><p class="meta">Evidence: {escape(", ".join(f.evidence))}</p></section>')
    evidence = "".join(f"<details><summary>{escape(o.key)} · {o.status}</summary>"
                       f"<pre>{escape(json.dumps(o.__dict__, indent=2))}</pre></details>" for o in report.snapshot.observations)
    banner = "" if report.snapshot.context == "live" else "<aside>Lab/fixture evidence. Not production or physical-hardware validation.</aside>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>RackCheck · {escape(report.snapshot.hostname)}</title><style>
body{{font:16px/1.55 system-ui,sans-serif;background:#f5f7fa;color:#162235;margin:0}}
main{{max-width:1000px;margin:auto;padding:32px 20px}}h1{{font-size:32px;margin:8px 0}}
h2{{font-size:18px;margin:0 0 8px;overflow-wrap:anywhere}}section{{background:white;border:1px solid #d8e0eb;border-radius:8px;margin:12px 0;padding:18px}}
p,li{{overflow-wrap:anywhere}}.meta{{font-size:13px;color:#536176}}.label{{float:right;font-weight:700;font-size:13px;padding:3px 9px;border-radius:5px;margin-left:12px}}
.PASS{{color:#145c35;background:#e6f5eb}}.FAIL{{color:#9b1820;background:#ffe8e8}}.WARN{{color:#735000;background:#fff2cc}}.UNKNOWN{{color:#374c73;background:#e9eef9}}
aside{{background:#fff2cc;padding:14px;border-left:4px solid #aa7800;margin:16px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}
details{{background:white;padding:12px;margin:8px 0}}summary{{cursor:pointer;overflow-wrap:anywhere}}footer{{margin-top:24px;color:#536176;font-size:13px}}
@media print{{body{{background:white}}main{{padding:0}}section{{break-inside:avoid}}}}
</style></head><body><main><div>RACKCHECK / SERVER DIAGNOSTICS</div>
<h1>{escape(report.snapshot.hostname)} <span class="label {report.status}">{report.status}</span></h1>
<p class="meta">Context: {report.snapshot.context} · Collected {escape(report.snapshot.collected_at)}</p>
{banner}{''.join(rows)}<h2>Observation details</h2>{evidence}
<footer>Read-only diagnosis. Findings do not authorize repairs. Review logs and identifiers before sharing.</footer>
</main></body></html>"""


def render(report, format_name):
    if format_name == "json":
        return json.dumps(report.to_dict(), indent=2, allow_nan=False) + "\n"
    if format_name == "markdown":
        return markdown(report)
    if format_name == "html":
        return html(report)
    raise ValueError("Unknown report format")


def compare(before, after):
    b, a = before.snapshot, after.snapshot
    if (b.hostname, b.platform, b.context) != (a.hostname, a.platform, a.context):
        raise ValueError("Comparison requires matching host, platform, and provenance")
    if datetime.fromisoformat(a.collected_at) < datetime.fromisoformat(b.collected_at):
        raise ValueError("After snapshot is older than before")
    old, new = {f.check_id: f for f in before.findings}, {f.check_id: f for f in after.findings}
    changes = []
    for key in sorted(old.keys() | new.keys()):
        prior, current = old.get(key), new.get(key)
        p, c = prior.status if prior else None, current.status if current else None
        if c in (None, "UNKNOWN"):
            state = "UNVERIFIED"
        elif p in ("FAIL", "WARN") and c == "PASS":
            state = "RECOVERED"
        elif p in (None, "UNKNOWN"):
            state = "NOW_OBSERVED"
        elif p == c:
            state = "UNCHANGED"
        elif c == "FAIL":
            state = "REGRESSED"
        else:
            state = "CHANGED"
        changes.append({"check_id": key, "before": p, "after": c, "change": state})
    return {"schema_version": 1, "hostname": a.hostname, "context": a.context,
            "before_status": before.status, "after_status": after.status, "changes": changes}
