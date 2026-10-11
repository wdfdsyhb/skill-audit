#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill-audit - audit AI agent skill libraries that follow the SKILL.md standard.

Checks frontmatter validity, name/dir consistency, duplicate names,
near-duplicate descriptions, and estimates the always-on metadata token cost
of the whole library. Works with Claude Code / ZCode / Codex-style skill dirs.

Zero third-party dependencies.
"""

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.1.0"

DEFAULT_THRESHOLD = 0.80
MAX_DESC_LEN = 1024
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "archive"}


def parse_frontmatter(text):
    """Minimal YAML frontmatter parser: flat 'key: value' lines only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta = {}
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        key, sep, value = s.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip('"').strip("'")
    if end is None:
        return {}, text
    return meta, "\n".join(lines[end + 1:]).lstrip("\n")


def estimate_tokens(text):
    """~4 chars per token, the usual back-of-envelope heuristic."""
    return len(text or "") // 4


def audit_skill(dir_path, meta, body):
    issues = []
    name = meta.get("name")
    if not name:
        issues.append("missing name in frontmatter")
    elif name != dir_path.name:
        issues.append(f"name mismatch: '{name}' != dir '{dir_path.name}'")
    desc = meta.get("description")
    if not desc:
        issues.append("missing description (this is what the model routes on)")
    elif len(desc) > MAX_DESC_LEN:
        issues.append(f"description too long: {len(desc)} chars (>{MAX_DESC_LEN})")
    if not body.strip():
        issues.append("empty body (metadata-only skill)")
    return issues


def find_skills(root):
    root = Path(root)
    out = []
    for p in sorted(root.rglob("SKILL.md")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return out


def _wordset(text):
    return frozenset(re.findall(r"[a-z0-9]+", (text or "").lower()))


def find_duplicates(skills, threshold=DEFAULT_THRESHOLD):
    dupes = []
    by_name = {}
    for s in skills:
        by_name.setdefault(s["name"], []).append(s)
    for name, group in sorted(by_name.items()):
        if name and name != "(unnamed)" and len(group) > 1:
            dupes.append({"kind": "same-name", "label": name,
                          "paths": sorted(g["path"] for g in group)})
    words = [_wordset(s["description"]) for s in skills]
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            wi, wj = words[i], words[j]
            if not wi or not wj:
                continue
            if len(wi & wj) / max(1, len(wi | wj)) < 0.25:
                continue  # cheap prefilter before the expensive ratio
            ratio = difflib.SequenceMatcher(
                None, skills[i]["description"] or "", skills[j]["description"] or "").ratio()
            if ratio >= threshold:
                dupes.append({"kind": "similar", "label": f"{skills[i]['name']} ~ {skills[j]['name']}",
                              "paths": sorted([skills[i]["path"], skills[j]["path"]]),
                              "ratio": round(ratio, 2)})
    return dupes


def audit_tree(root, threshold=DEFAULT_THRESHOLD):
    skills = []
    for path in find_skills(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        always_on = f"name: {meta.get('name', '')}\ndescription: {meta.get('description', '')}"
        skills.append({
            "name": meta.get("name") or "(unnamed)",
            "dir": path.parent.name,
            "description": meta.get("description", ""),
            "tokens": estimate_tokens(always_on),
            "path": str(path),
            "issues": audit_skill(path.parent, meta, body),
        })
    return {"root": str(root), "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total": len(skills), "total_tokens": sum(s["tokens"] for s in skills),
            "skills": skills, "dupes": find_duplicates(skills, threshold)}


def render_report(report, quiet=False):
    lines = []
    bad = [s for s in report["skills"] if s["issues"]]
    for s in (bad if quiet else report["skills"]):
        flag = " ".join(f"[{i}]" for i in s["issues"]) if s["issues"] else "[ok]"
        lines.append(f"{flag:<60} {s['tokens']:>5} tok  {s['path']}")
    for d in report["dupes"]:
        kind = "SAME NAME" if d["kind"] == "same-name" else f"similar ({d.get('ratio', '?')})"
        lines.append(f"[DUPE {kind}] {d['label']}")
        for p in d["paths"]:
            lines.append(f"    {p}")
    lines.append("")
    lines.append(f"{report['total']} skills | issues on {len(bad)} | "
                 f"{len(report['dupes'])} duplicate groups | "
                 f"always-on metadata ~= {report['total_tokens']} tokens")
    return "\n".join(lines)


def gen_index(report):
    out = ["# Skill Index", "", f"Auto-generated by skill-audit ({report['audited_at']}).",
           "", f"{report['total']} skills, ~{report['total_tokens']} tokens of always-on metadata.", ""]
    for s in sorted(report["skills"], key=lambda x: x["name"].lower()):
        desc = (s["description"][:150] + "...") if len(s["description"]) > 150 else s["description"]
        out.append(f"- **{s['name']}** — {desc or '(no description)'}")
    return "\n".join(out) + "\n"


EXAMPLES = """examples:
  python skill_audit.py C:\\Users\\me\\.zcode\\skills
  python skill_audit.py ./skills --json report.json
  python skill_audit.py ./skills -q          # only skills with issues
  python skill_audit.py ./skills --index INDEX.md
"""


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="skill-audit", description=__doc__.strip().splitlines()[0],
        epilog=EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="skill library root directory (contains <skill>/SKILL.md)")
    ap.add_argument("--json", dest="json_out", help="write full JSON report to file")
    ap.add_argument("--index", dest="index_out", help="write a markdown INDEX of all skills")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help=f"description similarity >= this counts as duplicate (default {DEFAULT_THRESHOLD})")
    ap.add_argument("-q", "--quiet", action="store_true", help="only list skills with issues")
    ap.add_argument("-V", "--version", action="version", version=f"skill-audit {__version__}")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = Path(args.root)
    if not root.is_dir():
        ap.error(f"not a directory: {root}")
    report = audit_tree(root, args.threshold)
    print(render_report(report, args.quiet), flush=True)

    if args.json_out:
        Path(args.json_out).expanduser().write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.index_out:
        Path(args.index_out).expanduser().write_text(gen_index(report), encoding="utf-8")
    n_bad = sum(1 for s in report["skills"] if s["issues"])
    return 1 if (n_bad or report["dupes"]) else 0


if __name__ == "__main__":
    sys.exit(main())
