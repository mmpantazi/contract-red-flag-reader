import json

from .rules import SEVERITIES

LABELS = {
    "en": {"high": "HIGH", "medium": "MEDIUM", "low": "LOW", "why": "Why it matters", "fix": "Ask for", "line": "line",
           "none": "No red flags matched. That does not mean the contract is safe: read it fully.",
           "summary": "Found {n} red flag(s): {parts}.", "disclaimer": "Automated keyword scan, not legal advice. Have a lawyer review contracts with significant money or IP at stake."},
    "ro": {"high": "RIDICAT", "medium": "MEDIU", "low": "SCĂZUT", "why": "De ce contează", "fix": "Cereți", "line": "rândul",
           "none": "Nicio clauză periculoasă detectată. Asta nu înseamnă că actul e sigur: citiți-l integral.",
           "summary": "{n} clauză/clauze de risc: {parts}.", "disclaimer": "Scanare automată pe cuvinte-cheie, nu consultanță juridică. Cereți avizul unui avocat pentru contracte cu sume sau drepturi importante."},
}
COLORS = {"high": "\033[1;31m", "medium": "\033[1;33m", "low": "\033[36m"}
RESET = "\033[0m"


def counts(findings) -> dict:
    return {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}


def _summary(findings, lang) -> str:
    t = LABELS[lang]
    c = counts(findings)
    if not findings:
        return t["none"]
    parts = ", ".join(f"{c[s]} {t[s].lower()}" for s in SEVERITIES if c[s])
    return t["summary"].format(n=len(findings), parts=parts)


def render_text(findings, source: str, lang: str = "en", color: bool = False) -> str:
    t = LABELS[lang]
    lines = [f"Contract Red-Flag Reader: {source}", _summary(findings, lang), ""]
    for i, f in enumerate(findings, 1):
        tag = f"[{t[f.severity]}]"
        if color:
            tag = f"{COLORS[f.severity]}{tag}{RESET}"
        where = f" ({t['line']} {f.line})" if f.line else ""
        lines.append(f"{i}. {tag} {f.title[lang]}{where}")
        if f.quote:
            lines.append(f"   > {f.quote}")
        lines.append(f"   {t['why']}: {f.why[lang]}")
        lines.append(f"   {t['fix']}: {f.fix[lang]}")
        lines.append("")
    lines.append(t["disclaimer"])
    return "\n".join(lines)


def render_markdown(findings, source: str, lang: str = "en") -> str:
    t = LABELS[lang]
    lines = [f"# Contract Red-Flag Reader: {source}", "", _summary(findings, lang), ""]
    for f in findings:
        where = f" ({t['line']} {f.line})" if f.line else ""
        lines.append(f"## {t[f.severity]}: {f.title[lang]}{where}")
        if f.quote:
            lines.append(f"> {f.quote}")
            lines.append("")
        lines.append(f"**{t['why']}:** {f.why[lang]}")
        lines.append("")
        lines.append(f"**{t['fix']}:** {f.fix[lang]}")
        lines.append("")
    lines.append(f"_{t['disclaimer']}_")
    return "\n".join(lines)


def render_json(findings, source: str, lang: str = "en") -> str:
    payload = {
        "source": source,
        "summary": counts(findings),
        "findings": [f.to_dict(lang) for f in findings],
        "disclaimer": LABELS[lang]["disclaimer"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
