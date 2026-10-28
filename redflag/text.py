"""Text loading, normalisation and clause splitting."""

import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NUMBERED = re.compile(r"^\s*(?:(?:article|section|clause|art\.?|sectiunea|clauza|capitolul)\s+)?\d+(?:\.\d+)*[.)]?\s+\S", re.I)
HEADING = re.compile(r"^\s*(?:article|section|clause|art\.?|sectiunea|clauza|capitolul)\s+[\dIVX]+\b", re.I)


class LoadError(Exception):
    pass


def fold(text: str) -> str:
    """Lower-case and strip diacritics one character at a time so offsets match the original."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0].lower()
        out.append(base if len(base) == 1 else ch.lower()[:1])
    return "".join(out)


def load(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    lower = path.lower()
    try:
        if lower.endswith(".docx"):
            return _read_docx(path)
        if lower.endswith(".pdf"):
            return _read_pdf(path)
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        raise LoadError(f"cannot read {path}: {exc.strerror or exc}") from exc


def _read_docx(path: str) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            root = ElementTree.fromstring(zf.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise LoadError(f"{path} is not a readable .docx file") from exc
    paragraphs = []
    for para in root.iter(f"{W_NS}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{W_NS}t":
                parts.append(node.text or "")
            elif node.tag in (f"{W_NS}tab",):
                parts.append(" ")
            elif node.tag == f"{W_NS}br":
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n\n".join(paragraphs)


def _read_pdf(path: str) -> str:
    exe = shutil.which("pdftotext")
    if not exe:
        raise LoadError("PDF input needs the 'pdftotext' tool (poppler-utils); or export the contract to .txt/.docx")
    result = subprocess.run([exe, "-layout", path, "-"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise LoadError(f"pdftotext failed: {result.stderr.strip()}")
    return result.stdout


@dataclass
class Clause:
    index: int
    line: int
    text: str  # original text, whitespace collapsed
    folded: str  # same length as text, lower-case and diacritic-free


def split_clauses(raw: str) -> list[Clause]:
    """Split on blank lines and on numbered/headed lines; remember the starting line."""
    clauses: list[Clause] = []
    buf: list[str] = []
    start = 1

    def flush():
        if buf:
            text = re.sub(r"\s+", " ", " ".join(buf)).strip()
            if text:
                clauses.append(Clause(len(clauses), start, text, fold(text)))
            buf.clear()

    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            flush()
            continue
        if buf and (NUMBERED.match(line) or HEADING.match(line)):
            flush()
        if not buf:
            start = number
        buf.append(line.strip())
    flush()
    return clauses


def sentence_around(clause: Clause, start: int, end: int, limit: int = 320) -> str:
    """Return the sentence of the clause containing the span [start, end)."""
    text = clause.text
    left = max(text.rfind(". ", 0, start), text.rfind("; ", 0, start))
    left = 0 if left < 0 else left + 2
    stops = [i for i in (text.find(". ", end), text.find("; ", end)) if i >= 0]
    right = min(stops) + 1 if stops else len(text)
    sentence = text[left:right].strip()
    if len(sentence) <= 40 and right < len(text):  # a bare heading such as "Non-Competition."
        nxt = text.find(". ", right + 1)
        sentence = text[left : nxt + 1 if nxt >= 0 else len(text)].strip()
    if len(sentence) > limit:
        mid = start - left
        lo = max(0, mid - limit // 2)
        sentence = ("…" if lo else "") + sentence[lo : lo + limit].strip() + "…"
    return sentence
