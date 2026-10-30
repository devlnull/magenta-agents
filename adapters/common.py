"""Shared helpers for Magenta: a small YAML subset parser, front matter, and glob matching.

Only the Python standard library is used, so the tools run on any machine with Python 3.9+.
The YAML parser supports the subset that the Magenta source files use: block maps, block
lists, flow lists and maps, quoted and plain scalars, folded (>, >-) and literal (|, |-)
blocks, and comments.
"""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath


class YamlError(ValueError):
    """The text uses YAML that the subset parser does not support."""


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow(text: str) -> list[str]:
    parts, cur, depth, quote = [], "", 0, None
    for ch in text:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _scalar(text: str):
    s = text.strip()
    if s == "":
        return None
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return json.loads(s)  # YAML double-quoted escapes are a superset of JSON escapes
        except ValueError:
            return s[1:-1]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if s.startswith("[") and s.endswith("]"):
        return [_scalar(x) for x in _split_flow(s[1:-1].strip())]
    if s.startswith("{") and s.endswith("}"):
        result = {}
        for part in _split_flow(s[1:-1].strip()):
            key, sep, value = part.partition(":")
            if not sep:
                raise YamlError(f"flow map entry without ':': {part!r}")
            result[_scalar(key)] = _scalar(value)
        return result
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


_KEY = re.compile(r"""^("[^"]*"|'[^']*'|[^:"'\[{][^:]*?):(?:\s+(.*))?$""")
_SEQ_MAP_ITEM = re.compile(r"""^[^"'\[{][^:]*:(\s|$)""")


class _Parser:
    def __init__(self, text: str):
        self.lines = text.splitlines()
        self.i = 0

    def current(self):
        while self.i < len(self.lines):
            stripped = _strip_comment(self.lines[self.i])
            if stripped.strip():
                return len(stripped) - len(stripped.lstrip(" ")), stripped.strip()
            self.i += 1
        return None

    def block(self, indent: int):
        cur = self.current()
        if cur is None or cur[0] < indent:
            return None
        if cur[1] == "-" or cur[1].startswith("- "):
            return self.seq(cur[0])
        return self.map(cur[0])

    def seq(self, indent: int) -> list:
        out = []
        while True:
            cur = self.current()
            if cur is None or cur[0] != indent or not (cur[1] == "-" or cur[1].startswith("- ")):
                return out
            item = cur[1][1:].strip()
            if item == "":
                self.i += 1
                out.append(self.block(indent + 1))
            elif _SEQ_MAP_ITEM.match(item):
                self.lines[self.i] = " " * (indent + 2) + item
                out.append(self.map(indent + 2))
            else:
                self.i += 1
                out.append(_scalar(item))

    def map(self, indent: int) -> dict:
        out = {}
        while True:
            cur = self.current()
            if cur is None or cur[0] != indent or cur[1].startswith("- "):
                return out
            m = _KEY.match(cur[1])
            if not m:
                raise YamlError(f"line {self.i + 1}: cannot parse {cur[1]!r}")
            key, value = _scalar(m.group(1)), (m.group(2) or "").strip()
            self.i += 1
            if value in (">", ">-", "|", "|-"):
                parts = []
                while self.i < len(self.lines):
                    raw = self.lines[self.i]
                    if raw.strip() and len(raw) - len(raw.lstrip(" ")) <= indent:
                        break
                    parts.append(raw.strip())
                    self.i += 1
                while parts and parts[-1] == "":
                    parts.pop()
                if value.startswith(">"):
                    out[key] = " ".join(p for p in parts if p)
                else:
                    out[key] = "\n".join(parts)
            elif value == "":
                nxt = self.current()
                if nxt and (nxt[0] > indent or (nxt[0] == indent and nxt[1].startswith("- "))):
                    out[key] = self.block(nxt[0])
                else:
                    out[key] = None
            else:
                out[key] = _scalar(value)


def parse_yaml(text: str):
    """Parse the YAML subset. Returns a dict, a list, or None."""
    parser = _Parser(text)
    result = parser.block(0)
    if parser.current() is not None:
        raise YamlError(f"line {parser.i + 1}: unexpected indentation")
    return result


def split_front_matter(text: str):
    """Return (front matter dict, body) of a Markdown file with YAML front matter."""
    if not text.startswith("---\n"):
        raise YamlError("the file does not start with '---'")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise YamlError("the front matter has no closing '---'")
    return parse_yaml(text[4:end]) or {}, text[end + 5:]


def glob_to_regex(pattern: str) -> re.Pattern:
    """Path glob: '**/' = zero or more folders, '**' = anything, '*' and '?' stop at '/'."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile("^" + out + "$")


def path_matches(path: str, patterns) -> bool:
    path = str(PurePosixPath(path))
    return any(glob_to_regex(p).match(path) for p in patterns or [])
