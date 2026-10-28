from .rules import DETECTORS, SEVERITIES, Doc
from .text import split_clauses


def scan(raw: str) -> list:
    doc = Doc(split_clauses(raw))
    findings = [f for detector in DETECTORS for f in detector(doc)]
    order = {s: i for i, s in enumerate(SEVERITIES)}
    findings.sort(key=lambda f: (order[f.severity], f.line))
    return findings
