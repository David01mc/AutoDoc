"""Generates the DAY SUMMARY block in the AutoDoc activity diary.

Reads today's docs/YYYY-MM-DD.md, parses all entries and appends
a consolidated closing block at the end of the file.

Usage:
    python Claude_Scripts/daily_summary.py
    python Claude_Scripts/daily_summary.py --date 2026-03-28
    python Claude_Scripts/daily_summary.py --print   (preview only, no write)
"""
import sys
import io
import os
import re
import json
import argparse
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── i18n ─────────────────────────────────────────────────────────────────────

STRINGS = {
    "es": {
        "summary_title":    "RESUMEN DEL DÍA",
        "project":          "Proyecto",
        "session":          "Sesión",
        "turns":            "Turnos completados",
        "objectives":       "Objetivos trabajados",
        "files_day":        "Archivos del día",
        "created":          "Creados",
        "modified":         "Modificados",
        "code_changes":     "Cambios en código",
        "more_changes":     "_(y {n} cambios más)_",
        "closing_state":    "Estado al cierre de sesión",
        "next_turn":        "Para el siguiente turno",
        "next_review":      "Revisar los archivos modificados",
        "next_objective":   "Último objetivo en curso",
        "next_continue":    "Continuar desde las {time} (última entrada del diario)",
        "tokens_day":       "Tokens acumulados en la sesión",
        "no_diary":         "[AutoDoc] No existe diario para {date}: {path}",
        "no_entries":       "[AutoDoc] No se encontraron entradas en {path}",
        "written":          "[AutoDoc] Resumen del día escrito en {path}",
        "processed":        "[AutoDoc] {n} entradas procesadas para {date}",
        "parse_error":      "[AutoDoc] Error al parsear el diario.",
    },
    "en": {
        "summary_title":    "DAY SUMMARY",
        "project":          "Project",
        "session":          "Session",
        "turns":            "Completed turns",
        "objectives":       "Objectives worked on",
        "files_day":        "Files of the day",
        "created":          "Created",
        "modified":         "Modified",
        "code_changes":     "Code changes",
        "more_changes":     "_(and {n} more changes)_",
        "closing_state":    "State at session close",
        "next_turn":        "For the next shift",
        "next_review":      "Review modified files",
        "next_objective":   "Last objective in progress",
        "next_continue":    "Continue from {time} (last diary entry)",
        "tokens_day":       "Tokens accumulated in session",
        "no_diary":         "[AutoDoc] No diary found for {date}: {path}",
        "no_entries":       "[AutoDoc] No entries found in {path}",
        "written":          "[AutoDoc] Day summary written to {path}",
        "processed":        "[AutoDoc] {n} entries processed for {date}",
        "parse_error":      "[AutoDoc] Error parsing the diary.",
    },
}


def t(key, lang, **kwargs):
    s = STRINGS.get(lang, STRINGS["en"]).get(key, key)
    return s.format(**kwargs) if kwargs else s


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(project_root):
    defaults = {
        "lang": "es",
        "docs_dir": "docs",
        "max_changes_in_summary": 15,
    }
    config_path = os.path.join(project_root, "Claude_Scripts", "autodoc.config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update({k: v for k, v in user_cfg.items() if not k.startswith("_")})
        except Exception:
            pass
    return defaults


# ── Diary parser ──────────────────────────────────────────────────────────────

def parse_diary(filepath):
    """Parses the markdown diary. Returns (project, entries)."""
    if not os.path.isfile(filepath):
        return None, []

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip existing summary so we can re-generate it cleanly
    for marker in ["## RESUMEN DEL DÍA", "## DAY SUMMARY"]:
        if marker in content:
            content = content[:content.index(marker)]

    # Extract project name from header
    project = "Project"
    header_match = re.search(r"^# .+ — (.+?) —", content, re.MULTILINE)
    if header_match:
        project = header_match.group(1).strip()

    raw_blocks = re.split(r"\n---\n", content)
    entries = []

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        entry = {
            "time": None, "objective": None, "question": None,
            "result": [], "files": [], "changes": [], "actions": [],
            "tools": "", "tokens": "",
        }

        time_match = re.search(r"### (\d{2}:\d{2}:\d{2})", block)
        if time_match:
            entry["time"] = time_match.group(1)

        for field, pattern in [
            ("objective", r"\*\*(?:Objetivo|Objective):\*\* (.+)"),
            ("question",  r"> \*\*(?:Usuario|User):\*\* (.+)"),
        ]:
            m = re.search(pattern, block)
            if m:
                entry[field] = m.group(1).strip()

        for field, pattern in [
            ("result",  r"\*\*(?:Resultado|Result):\*\*\n((?:  - .+\n?)+)"),
            ("files",   r"\*\*(?:Archivos|Files):\*\*\n((?:  - .+\n?)+)"),
            ("changes", r"\*\*(?:Cambios en código|Code changes):\*\*\n((?:  - .+\n?)+)"),
            ("actions", r"\*\*(?:Acciones|Actions):\*\*\n((?:  - .+\n?)+)"),
        ]:
            m = re.search(pattern, block)
            if m:
                entry[field] = [
                    ln.lstrip("  - ").strip()
                    for ln in m.group(1).splitlines()
                    if ln.strip().startswith("- ")
                ]

        foot_match = re.search(r"`([^`]+)`\s*$", block)
        if foot_match:
            foot = foot_match.group(1)
            if "Tokens" in foot or "tokens" in foot.lower():
                parts = re.split(r" \| (?:Sesión total|Session total):", foot, maxsplit=1)
                entry["tools"] = parts[0].strip()
                entry["tokens"] = foot
            else:
                entry["tools"] = foot.strip()

        if entry["time"]:
            entries.append(entry)

    return project, entries


# ── Summary builder ───────────────────────────────────────────────────────────

def collect_all_files(entries):
    created, modified = set(), set()
    for e in entries:
        for f in e["files"]:
            names = re.findall(r"`([^`]+)`", f)
            lower = f.lower()
            if "cread" in lower or "created" in lower:
                created.update(names)
            elif "modif" in lower:
                modified.update(names)
    return created, modified


def extract_session_total(entries):
    for e in reversed(entries):
        if e["tokens"]:
            m = re.search(r"(?:Sesión total|Session total):?\s*([\d.,kKmM]+)", e["tokens"])
            if m:
                return m.group(1)
    return None


def build_summary(project, entries, date_str, lang, max_changes):
    if not entries:
        return ""

    lines = []
    lines.append(f"---\n\n## {t('summary_title', lang)} — {date_str}\n\n")
    lines.append(f"**{t('project', lang)}:** {project}  \n")
    lines.append(f"**{t('session', lang)}:** {entries[0]['time']} → {entries[-1]['time']}  \n")
    lines.append(f"**{t('turns', lang)}:** {len(entries)}\n\n")

    # Objectives
    objectives = [e["objective"] for e in entries if e["objective"]]
    if objectives:
        lines.append(f"### {t('objectives', lang)}\n\n")
        for i, obj in enumerate(objectives, 1):
            lines.append(f"{i}. {obj}\n")
        lines.append("\n")

    # Files
    created, modified = collect_all_files(entries)
    touched = created | modified
    if touched:
        lines.append(f"### {t('files_day', lang)}\n\n")
        if created:
            names = ", ".join(f"`{f}`" for f in sorted(created))
            lines.append(f"- **{t('created', lang)}:** {names}\n")
        only_modified = modified - created
        if only_modified:
            names = ", ".join(f"`{f}`" for f in sorted(only_modified))
            lines.append(f"- **{t('modified', lang)}:** {names}\n")
        lines.append("\n")

    # Code changes (deduplicated)
    all_changes, seen = [], set()
    for e in entries:
        for c in e["changes"]:
            key = c[:60]
            if key not in seen:
                seen.add(key)
                all_changes.append(c)
    if all_changes:
        lines.append(f"### {t('code_changes', lang)}\n\n")
        for c in all_changes[:max_changes]:
            lines.append(f"- {c}\n")
        if len(all_changes) > max_changes:
            lines.append(f"- {t('more_changes', lang, n=len(all_changes) - max_changes)}\n")
        lines.append("\n")

    # Closing state (last non-empty result)
    last_results = next((e["result"] for e in reversed(entries) if e["result"]), [])
    if last_results:
        lines.append(f"### {t('closing_state', lang)}\n\n")
        for r in last_results:
            lines.append(f"- {r}\n")
        lines.append("\n")

    # Handoff block
    lines.append(f"### {t('next_turn', lang)}\n\n")
    if touched:
        names = ", ".join(f"`{f}`" for f in sorted(touched))
        lines.append(f"- {t('next_review', lang)}: {names}\n")
    if objectives:
        lines.append(f"- {t('next_objective', lang)}: _{objectives[-1]}_\n")
    lines.append(f"- {t('next_continue', lang, time=entries[-1]['time'])}\n\n")

    # Token total
    session_total = extract_session_total(entries)
    if session_total:
        lines.append(f"_{t('tokens_day', lang)}: **{session_total}**_\n\n")

    return "".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AutoDoc — generate day summary")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--print", action="store_true", dest="print_only",
                        help="Preview only — do not write to file")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    cfg = load_config(project_root)
    lang = cfg["lang"]

    docs_dir = os.path.join(project_root, cfg["docs_dir"])
    filepath = os.path.join(docs_dir, f"{date_str}.md")

    if not os.path.isfile(filepath):
        print(t("no_diary", lang, date=date_str, path=filepath))
        sys.exit(1)

    project, entries = parse_diary(filepath)

    if project is None:
        print(t("parse_error", lang))
        sys.exit(1)

    if not entries:
        print(t("no_entries", lang, path=filepath))
        sys.exit(0)

    summary = build_summary(project, entries, date_str, lang, cfg["max_changes_in_summary"])

    if args.print_only:
        print(summary)
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    for marker in ["## RESUMEN DEL DÍA", "## DAY SUMMARY"]:
        if marker in content:
            content = content[:content.index(marker)].rstrip() + "\n\n"
            break
    else:
        content = content.rstrip() + "\n\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content + summary)

    print(t("written", lang, path=filepath))
    print(t("processed", lang, n=len(entries), date=date_str))


if __name__ == "__main__":
    main()
