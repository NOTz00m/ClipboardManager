from __future__ import annotations

import json
import re
from collections.abc import Iterable

# flags for multiline regex matching
_FLAGS = re.MULTILINE


def _score(text: str, rules: Iterable[tuple[str, int, int]]) -> int:
    # weigh regex pattern hits against caps
    total = 0
    for pattern, weight, cap in rules:
        matches = re.findall(pattern, text, _FLAGS)
        total += min(len(matches), cap) * weight
    return total


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2 or stripped[0] not in "[{" or stripped[-1] not in "]}":
        return False
    try:
        value = json.loads(stripped)
        return isinstance(value, (dict, list))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


def detect_language(text: str) -> str:
    # Figure out the language or default to Text
    if not text or not text.strip():
        return "Text"

    sample = text[:100_000]
    lower = sample.lower()

    # Instant wins for obvious markers
    if re.search(r"<\?(?:php|=)", sample, re.IGNORECASE):
        return "PHP"
    if re.search(r"^\s*#!.*\bpython(?:\d+(?:\.\d+)?)?\b", sample, re.MULTILINE):
        return "Python"
    if re.search(r"^\s*#!.*\b(?:bash|zsh|fish|sh)\b", sample, re.MULTILINE):
        return "Shell"
    if re.search(r"^\s*#\s*include\s*[<\"]", sample, re.MULTILINE) or "std::" in sample:
        return "C++"
    if re.search(r"\bpackage\s+main\b", sample) and re.search(r"\bfunc\s+\w+\s*\(", sample):
        return "Go"
    if re.search(r"\bfn\s+\w+\s*\([^)]*\)\s*(?:->[^\{]+)?\{", sample):
        return "Rust"
    if re.search(r"\bpublic\s+static\s+void\s+main\s*\(", sample) or "System.out." in sample:
        return "Java"
    if re.search(r"\busing\s+System\s*;", sample) or "Console.WriteLine(" in sample:
        return "C#"
    if re.search(r"<!doctype\s+html", sample, re.IGNORECASE):
        return "HTML"
    if _looks_like_json(sample):
        return "JSON"

    rules: dict[str, tuple[tuple[str, int, int], ...]] = {
        "Python": (
            (r"^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*\([^\n]*\)\s*(?:->[^:]+)?\s*:", 9, 4),
            (r"^\s*class\s+[A-Za-z_]\w*(?:\([^\n]*\))?\s*:", 8, 3),
            (r"^\s*(?:from\s+[\w.]+\s+import|import\s+[\w.]+)", 5, 5),
            (r"\b(?:elif|except|with)\b[^\n]*:", 4, 4),
            (r"\b(?:self|cls)\.[A-Za-z_]\w*", 3, 5),
            (r"\b(?:True|False|None)\b", 2, 5),
            (r"^\s*@\w+(?:\.\w+)*(?:\([^\n]*\))?\s*$", 3, 3),
            (r"\bprint\s*\([^\n]*\)", 3, 4),
        ),
        "JS": (
            (r"\b(?:const|let|var)\s+[A-Za-z_$]", 4, 6),
            (r"(?:\([^\n)]*\)|[A-Za-z_$]\w*)\s*=>", 7, 4),
            (r"\b(?:async\s+)?function\s+[A-Za-z_$]\w*\s*\(", 7, 4),
            (r"\b(?:console|document|window)\.[A-Za-z_$]\w*", 5, 5),
            (r"\b(?:import|export)\s+(?:default\s+)?", 3, 4),
            (r"===|!==|\?\.", 2, 5),
            (r"\b(?:require|module\.exports)\b", 4, 4),
        ),
        "PHP": (
            (r"\$[A-Za-z_]\w*", 4, 8),
            (r"\b(?:echo|foreach|namespace)\b", 5, 5),
            (r"(?:->|::)[A-Za-z_]\w*", 3, 5),
            (r"\bfunction\s+[A-Za-z_]\w*\s*\([^)]*\$", 7, 3),
        ),
        "HTML": (
            (r"</?(?:html|head|body|main|section|article|div|span|script|style|a|p|img|form|input)\b[^>]*>", 4, 8),
            (r"<!--[\s\S]*?-->", 3, 2),
        ),
        "CSS": (
            (r"(?:^|\})\s*[.#]?[A-Za-z_][\w\s.#:[\]=\"'()>+~-]*\s*\{", 4, 5),
            (r"\b(?:display|position|margin|padding|background|color|font|grid|flex|width|height)[-\w]*\s*:", 3, 8),
            (r"@(?:media|supports|keyframes)\b", 5, 3),
        ),
        "Java": (
            (r"\b(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:class|interface|void|String|int|boolean)\b", 4, 6),
            (r"^\s*package\s+[\w.]+\s*;", 6, 1),
            (r"^\s*import\s+java\.[\w.*]+\s*;", 5, 4),
            (r"\bnew\s+[A-Z]\w*\s*\(", 3, 4),
        ),
        "C#": (
            (r"\busing\s+System\b", 6, 1),
            (r"\bnamespace\s+[\w.]+", 5, 1),
            (r"\b(?:public|private|internal|protected)\s+(?:async\s+)?(?:class|struct|interface|void|string|int|bool)\b", 4, 5),
        ),
        "Go": (
            (r"^\s*package\s+\w+", 6, 1),
            (r"\bfunc\s+(?:\([^)]*\)\s*)?[A-Za-z_]\w*\s*\(", 7, 4),
            (r"\b(?:defer|goroutine|chan)\b|\bgo\s+\w+\s*\(", 4, 4),
            (r"\bfmt\.[A-Za-z_]\w*", 4, 4),
        ),
        "Rust": (
            (r"\b(?:let\s+mut|impl|trait|pub\s+fn|match)\b", 4, 5),
            (r"\b(?:println|format|vec)!\s*\(", 5, 4),
            (r"&(?:mut\s+)?[A-Za-z_]\w*", 2, 4),
        ),
        "SQL": (
            (r"\bSELECT\b[\s\S]{0,500}\bFROM\b", 8, 3),
            (r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+TABLE)\b", 8, 3),
            (r"\b(?:WHERE|JOIN|GROUP\s+BY|ORDER\s+BY|HAVING)\b", 2, 6),
        ),
        "Shell": (
            (r"^\s*(?:export\s+)?[A-Za-z_]\w*=", 3, 5),
            (r"\$\([^)]+\)|\$\{[^}]+\}", 4, 4),
            (r"^\s*(?:sudo\s+)?(?:apt|brew|npm|npx|pip|pip3|yarn|pnpm|git|docker|kubectl|cargo)\b", 4, 5),
            (r"\b(?:then|fi|done|esac)\b", 4, 5),
        ),
    }

    scores = {language: _score(sample, language_rules) for language, language_rules in rules.items()}

    if re.search(r"^\s{4,}\S", sample, re.MULTILINE):
        scores["Python"] += 1
    if ";" in sample and "{" in sample:
        for language in ("JS", "PHP", "Java", "C++", "C#"):
            scores[language] = scores.get(language, 0) + 1
    if lower.lstrip().startswith(("select ", "insert ", "update ", "delete ", "create table")):
        scores["SQL"] += 3

    language, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score < 3:
        return "Text"

    ordered = sorted(scores.values(), reverse=True)
    if len(ordered) > 1 and ordered[0] == ordered[1] and best_score < 6:
        return "Text"
    return language


def is_code(text: str) -> int:
    # 1 for code, 0 for normal text
    if not text or not text.strip():
        return 0

    language = detect_language(text)
    if language != "Text":
        return 1

    stripped = text.strip()

    # Structural check for single-line or multi-line code/commands
    code_keywords = (
        r"\b(?:const|let|var|def|class|function|val|fn|struct|enum|import|from|"
        r"return|if|for|while|package|pub|using|include)\b"
    )
    cli_commands = (
        r"^\s*(?:npm|npx|pip|pip3|git|docker|kubectl|cargo|yarn|pnpm|go|dotnet|python|python3|node)\s+"
    )
    code_syntax = (
        r"(?:;\s*$|=>|==|!=|===|!==|&&|\|\||^\s*#include\b|\b\w+\([^)]*\)\s*;?$"
        r"|\w+\s*=\s*[^=]|\{[^}]*\}|\[[^\]]*\])"
    )

    if re.search(code_keywords, stripped) or re.search(cli_commands, stripped) or re.search(code_syntax, stripped):
        return 1

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2:
        indented = sum(line.startswith(("    ", "\t")) for line in lines)
        structural = sum(bool(re.search(pattern, text)) for pattern in (r"[{}]", r";\s*$", r"\w+\s*=\s*[^=]", r"\([^)]*\)"))
        if structural >= 2 or (indented / len(lines) >= 0.25):
            return 1

    return 0


def detect_content_type(text: str) -> str:
    # classify clipboard item as code, link, or text
    if not text:
        return "text"
    stripped = text.strip()
    # Check for links/URLs or domains
    if re.fullmatch(r"(?:https?://|ftp://|www\.)[^\s]+", stripped, re.IGNORECASE) or \
       re.fullmatch(r"[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?", stripped, re.IGNORECASE):
        return "link"
    return "code" if is_code(text) else "text"
