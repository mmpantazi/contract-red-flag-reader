import argparse
import sys

from . import __version__
from .report import render_json, render_markdown, render_text
from .rules import SEVERITIES
from .scanner import scan
from .text import LoadError, detect_language, load


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="redflag",
        description="Scan a freelance/service contract for dangerous clauses. Offline; nothing leaves your machine.",
    )
    p.add_argument("file", help="contract file (.txt, .md, .docx, .pdf via pdftotext) or - for stdin")
    p.add_argument("--lang", choices=("auto", "en", "ro"), default="auto", help="language of the notes; auto follows the contract's language")
    p.add_argument("--format", choices=("text", "markdown", "json"), default="text")
    p.add_argument("--min-severity", choices=SEVERITIES[::-1], default="low", help="hide findings below this level")
    p.add_argument("--fail-on", choices=SEVERITIES, help="exit with status 1 if any finding is at least this severe")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        raw = load(args.file)
    except LoadError as exc:
        print(f"redflag: {exc}", file=sys.stderr)
        return 2
    if not raw.strip():
        print("redflag: the document is empty", file=sys.stderr)
        return 2
    findings = scan(raw)
    lang = detect_language(raw) if args.lang == "auto" else args.lang
    cutoff = SEVERITIES.index(args.min_severity)
    shown = [f for f in findings if SEVERITIES.index(f.severity) <= cutoff]
    source = "stdin" if args.file == "-" else args.file
    if args.format == "json":
        out = render_json(shown, source, lang)
    elif args.format == "markdown":
        out = render_markdown(shown, source, lang)
    else:
        out = render_text(shown, source, lang, color=sys.stdout.isatty() and not args.no_color)
    print(out)
    if args.fail_on:
        limit = SEVERITIES.index(args.fail_on)
        if any(SEVERITIES.index(f.severity) <= limit for f in findings):
            return 1
    return 0
