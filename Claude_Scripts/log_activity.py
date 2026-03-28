"""Hook Stop: generates a synthesized activity diary for Claude Code.

Reads the JSONL transcript to extract what was done in the last response
and appends a concise entry to docs/YYYY-MM-DD.md.

Config: autodoc.config.json at project root.
"""
import sys
import io
import json
import os
from datetime import datetime
import re
import ast
from collections import Counter

# Force UTF-8 on Windows
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── i18n ─────────────────────────────────────────────────────────────────────

STRINGS = {
    "es": {
        "diary_title":    "Diario de actividad",
        "objective":      "Objetivo",
        "user":           "Usuario",
        "result":         "Resultado",
        "files":          "Archivos",
        "code_changes":   "Cambios en código",
        "actions":        "Acciones",
        "created":        "Creados",
        "modified":       "Modificados",
        "consulted":      "Consultados",
        "consulted_n":    "{n} archivos",
        "tokens_turn":    "Tokens turno",
        "tokens_session": "Sesión total",
        "agent":          "Agente",
        "searches":       "{n} búsquedas realizadas",
        "commands_n":     "{n} comandos ejecutados",
        "func":           "función",
        "cls":            "clase",
        "added":          "añadido",
        "removed":        "eliminado",
        "file_created":   "`{name}` creado ({lines} líneas)",
        "file_modified":  "`{name}`: {detail}",
        "verb_implement": "Implementar",
        "verb_fix":       "Corregir",
        "verb_explain":   "Explicar",
        "verb_refactor":  "Refactorizar",
        "verb_verify":    "Verificar",
        "verb_delete":    "Eliminar",
        "verb_review":    "Revisar",
        "verb_attend":    "Atender",
    },
    "en": {
        "diary_title":    "Activity log",
        "objective":      "Objective",
        "user":           "User",
        "result":         "Result",
        "files":          "Files",
        "code_changes":   "Code changes",
        "actions":        "Actions",
        "created":        "Created",
        "modified":       "Modified",
        "consulted":      "Read",
        "consulted_n":    "{n} files",
        "tokens_turn":    "Turn tokens",
        "tokens_session": "Session total",
        "agent":          "Agent",
        "searches":       "{n} searches performed",
        "commands_n":     "{n} commands executed",
        "func":           "function",
        "cls":            "class",
        "added":          "added",
        "removed":        "removed",
        "file_created":   "`{name}` created ({lines} lines)",
        "file_modified":  "`{name}`: {detail}",
        "verb_implement": "Implement",
        "verb_fix":       "Fix",
        "verb_explain":   "Explain",
        "verb_refactor":  "Refactor",
        "verb_verify":    "Verify",
        "verb_delete":    "Delete",
        "verb_review":    "Review",
        "verb_attend":    "Handle",
    },
}


def t(key, lang, **kwargs):
    """Translate a key to the given language, with optional format args."""
    s = STRINGS.get(lang, STRINGS["en"]).get(key, key)
    return s.format(**kwargs) if kwargs else s


# ── Config ───────────────────────────────────────────────────────────────────

def load_config(project_root):
    """Loads autodoc.config.json from the project root. Returns defaults if missing."""
    defaults = {
        "lang": "es",
        "docs_dir": "docs",
        "max_summary_lines": 3,
        "max_changes_in_summary": 15,
        "min_message_length": 30,
        "skip_read_only_turns": True,
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


# ── System tag stripping ──────────────────────────────────────────────────────

_SYSTEM_TAG_PATTERNS = [
    r"<ide_opened_file>.*?</ide_opened_file>",
    r"<ide_selection>.*?</ide_selection>",
    r"<system-reminder>.*?</system-reminder>",
    r"<user-prompt-submit-hook>.*?</user-prompt-submit-hook>",
    r"<command-name>.*?</command-name>",
    r"<functions>.*?</functions>",
]


def strip_system_tags(text):
    for pattern in _SYSTEM_TAG_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.DOTALL)
    return " ".join(text.split()).strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def truncate(text, max_len=150):
    text = str(text).replace("\n", " ").strip()
    return text[:max_len] + "..." if len(text) > max_len else text


def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


# ── AST: Python ───────────────────────────────────────────────────────────────

def extract_definitions_python(code, lang):
    names = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(f"{t('func', lang)} `{node.name}`")
            elif isinstance(node, ast.ClassDef):
                names.append(f"{t('cls', lang)} `{node.name}`")
    except SyntaxError:
        pass
    return names


# ── AST: JavaScript / TypeScript ─────────────────────────────────────────────

_JS_PATTERNS = [
    # function foo() / async function foo()
    re.compile(r"\basync\s+function\s+(\w+)\s*\("),
    re.compile(r"\bfunction\s+(\w+)\s*\("),
    # const/let/var foo = () => / const foo = function
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(.*?\)\s*=>"),
    re.compile(r"\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function"),
    # class Foo
    re.compile(r"\bclass\s+(\w+)"),
    # export default function foo
    re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\("),
    # TypeScript: interface Foo / type Foo =
    re.compile(r"\binterface\s+(\w+)"),
    re.compile(r"\btype\s+(\w+)\s*="),
]

_JS_CLASS_PATTERN = re.compile(r"\bclass\s+(\w+)")
_JS_INTERFACE_PATTERN = re.compile(r"\b(?:interface|type)\s+(\w+)")


def extract_definitions_js(code, lang):
    names = []
    seen = set()
    for pattern in _JS_PATTERNS:
        for m in pattern.finditer(code):
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            full = m.group(0)
            if "class" in full:
                names.append(f"{t('cls', lang)} `{name}`")
            elif "interface" in full or "type " in full:
                names.append(f"type `{name}`")
            else:
                names.append(f"{t('func', lang)} `{name}`")
    return names


def extract_definitions(code, filename, lang):
    """Dispatch to the right AST parser based on file extension."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        return extract_definitions_js(code, lang)
    if ext in (".py", "") or ext == "":
        return extract_definitions_python(code, lang)
    # Fallback: try Python, then JS
    result = extract_definitions_python(code, lang)
    return result if result else extract_definitions_js(code, lang)


# ── Change descriptors ────────────────────────────────────────────────────────

def describe_edit(filename, old, new, lang):
    old_lines = old.strip().split("\n") if old.strip() else []
    new_lines = new.strip().split("\n") if new.strip() else []
    delta = len(new_lines) - len(old_lines)

    old_defs = extract_definitions(old, filename, lang)
    new_defs = extract_definitions(new, filename, lang)
    added_defs = [d for d in new_defs if d not in old_defs]
    removed_defs = [d for d in old_defs if d not in new_defs]

    parts = []
    if added_defs:
        parts.append(f"{t('added', lang)} {', '.join(added_defs)}")
    if removed_defs:
        parts.append(f"{t('removed', lang)} {', '.join(removed_defs)}")
    if not parts:
        if delta > 0:
            parts.append(f"+{delta} lines" if lang == "en" else f"+{delta} líneas")
        elif delta < 0:
            parts.append(f"{delta} lines" if lang == "en" else f"{delta} líneas")
        else:
            parts.append("modified" if lang == "en" else "modificado")

    detail = "; ".join(parts)
    return t("file_modified", lang, name=filename, detail=detail)


def describe_write(filename, content, lang):
    lines = content.strip().split("\n") if content.strip() else []
    defs = extract_definitions(content, filename, lang)
    desc = t("file_created", lang, name=filename, lines=len(lines))
    if defs:
        listed = ", ".join(defs[:5])
        if len(defs) > 5:
            listed += f" +{len(defs) - 5}"
        desc += f": {listed}"
    return desc


# ── Markdown cleaning ─────────────────────────────────────────────────────────

def clean_markdown(text):
    # Convertir links [texto](url) → texto
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Eliminar inline code muy largo (ruido), conservar el corto
    text = re.sub(r'`[^`]{40,}`', '', text)
    # Conservar ** y * — el diario es Markdown, se renderizan como negrita/cursiva
    return text.strip()


def is_table_separator(line):
    return bool(re.match(r'^[\|\-\s:]+$', line))


def parse_table_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return [clean_markdown(c) for c in cells if c.strip()]


def is_bold_header(line):
    """Detecta líneas que son títulos en negrita: **Texto** o **1. Texto**"""
    return bool(re.match(r'^\*\*[^*]{3,}\*\*\s*$', line))


def _extract_lines(text, max_lines, pre_code_only=False):
    """
    Extrae líneas de resumen de un bloque de texto.
    Si pre_code_only=True, se detiene en el primer bloque de código LARGO (>2 líneas).
    Bloques cortos (1-2 líneas) son ejemplos/resultados y se incluyen.
    """
    lines = text.split("\n")
    result = []
    inside_code_block = False
    code_block_lines = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("```"):
            if not inside_code_block:
                # Inicio de bloque: previsualizar cuántas líneas tiene
                inside_code_block = True
                code_block_lines = []
            else:
                # Fin de bloque
                inside_code_block = False
                if pre_code_only and len(code_block_lines) > 2:
                    break   # Bloque largo → parar
                # Bloque corto (1-2 líneas) → incluir su contenido como resultado
                for cl in code_block_lines:
                    cl = cl.strip()
                    if len(cl) >= 10:
                        result.append(truncate(cl, 180))
                        if len(result) >= max_lines:
                            break
                code_block_lines = []
            i += 1
            continue

        if inside_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        if not line:
            i += 1
            continue

        if line.startswith("---") or line.startswith("===") or line.startswith("#"):
            i += 1
            continue
        if line.startswith("|"):
            if is_table_separator(line):
                i += 1
                continue
            cells = parse_table_row(line)
            if len(cells) >= 2 and len(cells[0]) < 50:
                entry = f"{cells[0]}: {cells[1]}"
                if len(entry) >= 20:
                    result.append(truncate(entry, 180))
            elif len(cells) == 1 and len(cells[0]) >= 20:
                result.append(truncate(cells[0], 180))
            if len(result) >= max_lines:
                break
            i += 1
            continue

        # Títulos en negrita puros (**Texto**) — usar como punto
        if is_bold_header(line):
            clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line).strip()
            if len(clean) >= 10:
                result.append(truncate(clean, 180))
                if len(result) >= max_lines:
                    break
            i += 1
            continue

        # Líneas que empiezan con código inline (`foo`) — son explicaciones técnicas, descartar
        if line.startswith("`"):
            i += 1
            continue

        # Líneas con alta densidad de código — descartar
        code_chars = line.count("`") + line.count("(") + line.count(")")
        if code_chars > len(line) * 0.3:
            i += 1
            continue
        if len(line) < 20:
            i += 1
            continue

        clean = re.sub(r'^[-*>]+\s*', '', line)
        clean = re.sub(r'^\d+[.)]\s+', '', clean)
        clean = clean_markdown(clean)
        if len(clean) < 20:
            i += 1
            continue
        result.append(truncate(clean, 180))
        if len(result) >= max_lines:
            break
        i += 1

    return result


def build_summary_text(assistant_texts, last_message, max_lines):
    text_source = last_message or " ".join(assistant_texts)
    if not text_source:
        return []

    # Prioridad 1: texto ANTES del primer bloque de código
    # Es donde Claude suele dar el resultado de alto nivel
    pre_code = _extract_lines(text_source, max_lines, pre_code_only=True)
    if len(pre_code) >= 2:
        return pre_code

    # Prioridad 2: si no hay suficiente texto previo al código,
    # escanear todo el texto (ignorando bloques de código)
    return _extract_lines(text_source, max_lines, pre_code_only=False)


# ── Objective inference ───────────────────────────────────────────────────────

def infer_objective(user_question, tool_uses, lang):
    q = user_question.lower()
    if any(w in q for w in ["crea", "añade", "agrega", "implementa", "escribe", "genera",
                              "create", "add", "implement", "write", "generate", "build"]):
        verb = t("verb_implement", lang)
    elif any(w in q for w in ["arregla", "corrige", "fix", "bug", "error", "falla",
                               "no funciona", "broken", "wrong", "issue"]):
        verb = t("verb_fix", lang)
    elif any(w in q for w in ["explica", "qué es", "cómo", "por qué", "describe",
                               "explain", "what is", "how", "why"]):
        verb = t("verb_explain", lang)
    elif any(w in q for w in ["refactori", "mejora", "optimiza", "limpia",
                               "refactor", "improve", "optimize", "clean"]):
        verb = t("verb_refactor", lang)
    elif any(w in q for w in ["prueba", "test", "verifica", "comprueba", "verify", "check"]):
        verb = t("verb_verify", lang)
    elif any(w in q for w in ["borra", "elimina", "quita", "remove", "delete"]):
        verb = t("verb_delete", lang)
    elif tool_uses and all(tu["name"] == "Read" for tu in tool_uses):
        verb = t("verb_review", lang)
    else:
        verb = t("verb_attend", lang)

    # Limpiar la pregunta para el título: quitar bloques de código,
    # backticks, URLs y quedarse con la primera frase significativa
    clean_q = re.sub(r'```.*?```', '', user_question, flags=re.DOTALL)  # bloques código
    clean_q = re.sub(r'`[^`]+`', '', clean_q)                           # inline code
    clean_q = re.sub(r'https?://\S+', '', clean_q)                      # URLs
    clean_q = re.sub(r'\s+', ' ', clean_q).strip()

    # Tomar solo la primera oración o línea significativa
    for sep in ['\n', '. ', '? ', '! ']:
        part = clean_q.split(sep)[0].strip()
        if len(part) >= 8:
            clean_q = part
            break

    topic = truncate(clean_q, 60) if clean_q else truncate(user_question, 60)
    return f"{verb}: {topic}" if topic else verb


# ── Transcript parsing ────────────────────────────────────────────────────────

def parse_transcript(transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    messages = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return messages


def is_real_user_message(entry):
    if entry.get("type") != "user":
        return False
    content = entry.get("message", {}).get("content", [])
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return False
            if isinstance(block, (str, dict)):
                return True
    return False


def extract_user_question(entry):
    content = entry.get("message", {}).get("content", [])
    if isinstance(content, str):
        return strip_system_tags(content)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return strip_system_tags(" ".join(parts))
    return ""


def extract_token_usage(messages, last_user_idx):
    turn_input = turn_output = session_input = session_output = 0
    for i, entry in enumerate(messages):
        usage = entry.get("message", {}).get("usage", {})
        if not usage:
            continue
        inp = usage.get("input_tokens", 0)
        out = usage.get("output_tokens", 0)
        session_input += inp
        session_output += out
        if i > last_user_idx:
            turn_input += inp
            turn_output += out
    return {
        "turn_input": turn_input, "turn_output": turn_output,
        "turn_total": turn_input + turn_output,
        "session_input": session_input, "session_output": session_output,
        "session_total": session_input + session_output,
    }


def extract_last_turn(messages):
    tool_uses, assistant_texts = [], []
    user_question, token_usage = "", {}

    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if is_real_user_message(messages[i]):
            last_user_idx = i
            break

    if last_user_idx < 0:
        return user_question, tool_uses, assistant_texts, token_usage

    user_question = extract_user_question(messages[last_user_idx])
    token_usage = extract_token_usage(messages, last_user_idx)

    for entry in messages[last_user_idx + 1:]:
        msg = entry.get("message", {})
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant" and entry.get("type") != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, str):
            assistant_texts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, str):
                assistant_texts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    assistant_texts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_uses.append({"name": block.get("name", ""), "input": block.get("input", {})})

    return user_question, tool_uses, assistant_texts, token_usage


# ── Synthesis ─────────────────────────────────────────────────────────────────

def synthesize(tool_uses, assistant_texts, last_message, user_question, token_usage, cwd, cfg):
    lang = cfg["lang"]
    max_lines = cfg["max_summary_lines"]

    files_modified, files_created, files_read = set(), set(), set()
    commands_run, searches, agents, code_changes = [], [], [], []

    for tu in tool_uses:
        name = tu["name"]
        inp = tu.get("input") or {}

        if name == "Edit":
            path = inp.get("file_path", "")
            if path:
                fname = os.path.basename(path)
                files_modified.add(fname)
                code_changes.append(describe_edit(fname, inp.get("old_string", ""), inp.get("new_string", ""), lang))
        elif name == "Write":
            path = inp.get("file_path", "")
            if path:
                fname = os.path.basename(path)
                files_created.add(fname)
                code_changes.append(describe_write(fname, inp.get("content", ""), lang))
        elif name == "Read":
            path = inp.get("file_path", "")
            if path:
                files_read.add(os.path.basename(path))
        elif name == "Bash":
            desc = inp.get("description", "")
            if desc:
                commands_run.append(desc)
        elif name in ("Glob", "Grep"):
            if inp.get("pattern"):
                searches.append(inp["pattern"])
        elif name == "Agent":
            if inp.get("description"):
                agents.append(inp["description"])

    result = {
        "project": os.path.basename(os.path.normpath(cwd)) if cwd else None,
        "objective": "",
        "question": "",
        "summary": [],
        "files": [],
        "changes": code_changes,
        "actions": [],
        "tools": "",
        "tokens": token_usage or {},
    }

    if user_question:
        result["question"] = user_question.replace("\n", " ").strip()
        result["objective"] = infer_objective(user_question, tool_uses, lang)

    result["summary"] = build_summary_text(assistant_texts, last_message, max_lines)

    if files_created:
        result["files"].append(f"{t('created', lang)}: {', '.join(f'`{f}`' for f in sorted(files_created))}")
    if files_modified:
        result["files"].append(f"{t('modified', lang)}: {', '.join(f'`{f}`' for f in sorted(files_modified))}")
    read_only = files_read - files_modified - files_created
    if read_only:
        if len(read_only) <= 3:
            result["files"].append(f"{t('consulted', lang)}: {', '.join(f'`{f}`' for f in sorted(read_only))}")
        else:
            result["files"].append(f"{t('consulted', lang)}: {t('consulted_n', lang, n=len(read_only))}")

    if commands_run:
        for c in (commands_run if len(commands_run) <= 3 else []):
            result["actions"].append(c)
        if len(commands_run) > 3:
            result["actions"].append(t("commands_n", lang, n=len(commands_run)))
    if searches:
        result["actions"].append(t("searches", lang, n=len(searches)))
    for a in agents:
        result["actions"].append(f"{t('agent', lang)}: {a}")

    tool_counts = Counter(tu["name"] for tu in tool_uses)
    result["tools"] = ", ".join(f"{n}x{name}" for name, n in tool_counts.most_common())

    return result, lang


# ── Writer ────────────────────────────────────────────────────────────────────

def write_entry(data_out, lang, docs_dir, cfg):
    now = datetime.now()
    os.makedirs(docs_dir, exist_ok=True)
    filepath = os.path.join(docs_dir, f"{now:%Y-%m-%d}.md")
    exists = os.path.isfile(filepath)

    with open(filepath, "a", encoding="utf-8") as f:
        if not exists:
            project = data_out["project"] or "Project"
            f.write(f"# {t('diary_title', lang)} — {project} — {now:%Y-%m-%d}\n\n")

        objective_inline = f" — {data_out['objective']}" if data_out["objective"] else ""
        f.write(f"---\n\n### {now:%H:%M:%S}{objective_inline}\n\n")

        if data_out["question"]:
            f.write(f"> **{t('user', lang)}:** {data_out['question']}\n\n")

        if data_out["summary"]:
            f.write(f"**{t('result', lang)}:**\n")
            for line in data_out["summary"]:
                f.write(f"  - {line}\n")
            f.write("\n")

        if data_out["files"]:
            f.write(f"**{t('files', lang)}:**\n")
            for line in data_out["files"]:
                f.write(f"  - {line}\n")
            f.write("\n")

        if data_out["changes"]:
            f.write(f"**{t('code_changes', lang)}:**\n")
            for desc in data_out["changes"]:
                f.write(f"  - {desc}\n")
            f.write("\n")

        if data_out["actions"]:
            f.write(f"**{t('actions', lang)}:**\n")
            for line in data_out["actions"]:
                f.write(f"  - {line}\n")
            f.write("\n")

        footer_parts = []
        if data_out["tools"]:
            footer_parts.append(data_out["tools"])
        tokens = data_out.get("tokens", {})
        if tokens.get("turn_total"):
            footer_parts.append(
                f"{t('tokens_turn', lang)}: {format_tokens(tokens['turn_total'])} "
                f"(in: {format_tokens(tokens['turn_input'])}, out: {format_tokens(tokens['turn_output'])}) "
                f"| {t('tokens_session', lang)}: {format_tokens(tokens['session_total'])}"
            )
        if footer_parts:
            f.write(f"`{'  |  '.join(footer_parts)}`\n\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    if data.get("stop_hook_active"):
        return

    transcript_path = data.get("transcript_path", "")
    last_message = data.get("last_assistant_message", "")
    cwd = data.get("cwd", "")

    # Locate project root: where autodoc.config.json lives (or script's parent)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    cfg = load_config(project_root)

    if not last_message and len(last_message) < cfg["min_message_length"]:
        return

    messages = parse_transcript(transcript_path)
    user_question, tool_uses, assistant_texts, token_usage = extract_last_turn(messages)

    if not tool_uses and len(last_message) < cfg["min_message_length"]:
        return

    if cfg["skip_read_only_turns"] and tool_uses and all(tu["name"] == "Read" for tu in tool_uses):
        return

    data_out, lang = synthesize(tool_uses, assistant_texts, last_message,
                                 user_question, token_usage, cwd, cfg)

    has_content = (data_out["question"] or data_out["summary"]
                   or data_out["files"] or data_out["actions"])
    if not has_content:
        return

    docs_dir = os.path.join(project_root, cfg["docs_dir"])
    write_entry(data_out, lang, docs_dir, cfg)


if __name__ == "__main__":
    main()
