"""Detectors. All patterns run on diacritic-folded lower-case text (English and Romanian)."""

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

from .text import Clause, sentence_around

SEVERITIES = ("high", "medium", "low")

NUMWORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty-five": 45, "forty five": 45, "sixty": 60, "ninety": 90,
    "un": 1, "unu": 1, "o": 1, "doi": 2, "doua": 2, "trei": 3, "patru": 4, "cinci": 5, "sase": 6,
    "zece": 10, "doisprezece": 12, "cincisprezece": 15, "douazeci": 20, "treizeci": 30,
    "patruzeci si cinci": 45, "saizeci": 60, "nouazeci": 90,
}
NUM = r"(\d{1,3}|" + "|".join(sorted((re.escape(w) for w in NUMWORDS), key=len, reverse=True)) + r")"


def to_int(token: str) -> int:
    token = token.strip()
    return int(token) if token.isdigit() else NUMWORDS.get(token, 0)


def rx(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.S)


@dataclass
class Finding:
    rule: str
    category: str
    severity: str
    title: dict
    why: dict
    fix: dict
    quote: str = ""
    line: int = 0
    clause: int = -1

    def to_dict(self, lang: str = "en") -> dict:
        return {
            "rule": self.rule,
            "category": self.category,
            "severity": self.severity,
            "title": self.title[lang],
            "why": self.why[lang],
            "fix": self.fix[lang],
            "quote": self.quote,
            "line": self.line,
        }


@dataclass
class Doc:
    clauses: list
    full: str = field(init=False)

    def __post_init__(self):
        self.full = " ".join(c.folded for c in self.clauses)

    def has(self, pattern: re.Pattern) -> bool:
        return bool(pattern.search(self.full))


def finding(rule, category, severity, title, why, fix, clause: Optional[Clause] = None, span=None) -> Finding:
    quote, line, idx = "", 0, -1
    if clause is not None:
        quote = sentence_around(clause, *span) if span else clause.text[:320]
        line, idx = clause.line, clause.index
    return Finding(rule, category, severity, title, why, fix, quote, line, idx)


def each(doc: Doc, pattern: re.Pattern) -> Iterator[tuple]:
    for clause in doc.clauses:
        m = pattern.search(clause.folded)
        if m:
            yield clause, m


# ---------------------------------------------------------------- revisions

UNLIMITED_REV = rx(
    r"unlimited\s+(?:number\s+of\s+)?(?:revision|change|amendment|edit|round|modification|correction|iteration)",
    r"(?:any|an)\s+(?:number|amount)\s+of\s+(?:revision|change|amendment|edit|round|modification)",
    r"as\s+many\s+(?:revision|change|edit|round|amendment|modification)",
    r"(?:revision|change|amendment|edit|modification|correction|round)s?\b.{0,80}?until\s+(?:the\s+)?(?:client|customer|company)\b.{0,30}?(?:satisf|happy|approv|content)",
    r"until\s+(?:the\s+)?(?:client|customer|company)\b.{0,30}?(?:is|are)\s+(?:fully\s+|completely\s+|entirely\s+)?(?:satisf|happy|content)",
    r"(?:revision|change|modification)s?\b.{0,60}?without\s+(?:additional|extra|further)\s+(?:charge|cost|fee|payment|compensation)",
    r"(?:revizu|modificari|corecturi|ajustari)\w*\s+nelimitat",
    r"nelimitat\w*\s+(?:de\s+)?(?:revizu|modificari|corecturi|runde|ajustari)",
    r"oricate\s+(?:revizu|modificari|corecturi|runde|ajustari)",
    r"pana\s+(?:cand|la)\s+(?:clientul|beneficiarul)\b.{0,40}?(?:multumit|satisf|aprob)",
    r"pana\s+la\s+(?:satisfactia|multumirea|aprobarea)\s+(?:clientului|beneficiarului)",
)
SATISFACTION = rx(
    r"(?:to|until)\s+the\s+(?:client|customer|company)(?:'s|s)?\s+(?:sole\s+|reasonable\s+)?(?:satisfaction|approval)",
    r"(?:sole|absolute)\s+(?:discretion|satisfaction)\s+of\s+the\s+(?:client|customer|company)",
    r"(?:conform|potrivit)\s+(?:cu\s+)?(?:satisfactia|aprobarea)\s+(?:clientului|beneficiarului)",
    r"(?:pana\s+la|dupa)\s+(?:satisfactia|multumirea)\s+(?:deplina\s+)?(?:a\s+)?(?:clientului|beneficiarului)",
)
REV_CAP = rx(
    NUM + r"\s*(?:\(\d+\)\s*)?(?:rounds?|revisions?|iterations?|runde|revizu\w*|modificari)",
    r"(?:rounds?|revisions?|runde|revizu\w*|modificari)\b.{0,40}?(?:limited|capped|up\s+to|maximum|at\s+most|limitat|maxim)",
)
REV_MENTION = rx(r"revision|revizu|\bchanges\b|rounds?\b|modificari|corecturi|amendments?")
DELIVERABLE = rx(r"deliverable|design|develop|writ|content|website|logo|software|livrabil|proiect|servicii")
FREE_WINDOW = rx(
    r"(?:free\s+of\s+charge|at\s+no\s+(?:additional\s+)?(?:cost|charge)|without\s+(?:additional\s+)?(?:charge|cost)|gratuit|fara\s+(?:costuri|plata|taxa))\b.{0,80}?" + NUM + r"\s*(?:\(\d+\)\s*)?(months?|years?|luni|luna|ani|an)\b",
    NUM + r"\s*(?:\(\d+\)\s*)?(months?|years?|luni|luna|ani|an)\b.{0,80}?(?:free\s+of\s+charge|at\s+no\s+(?:additional\s+)?(?:cost|charge)|without\s+(?:additional\s+)?(?:charge|cost)|gratuit|fara\s+(?:costuri|plata|taxa))",
)
FREE_CONTEXT = rx(r"revision|change|modif|fix|correct|support|update|amend|revizu|ajustar|suport|actualiz")


def _months(num: str, unit: str) -> int:
    n = to_int(num)
    return n * 12 if unit.startswith(("year", "an")) else n


def detect_revisions(doc: Doc) -> list:
    out = []
    unlimited = False
    for clause, m in each(doc, UNLIMITED_REV):
        unlimited = True
        out.append(finding(
            "revisions.unlimited", "Unpaid revisions", "high",
            {"en": "Unlimited or open-ended revisions", "ro": "Revizuiri nelimitate sau fără capăt"},
            {"en": "There is no limit on how many times the client can ask for changes, so a fixed fee can turn into unpaid work for months.",
             "ro": "Nu există o limită a cererilor de modificări, deci un preț fix se poate transforma în luni de muncă neplătită."},
            {"en": "Cap it: \"Fee includes two (2) rounds of revisions per deliverable; further changes are billed at [rate]/hour.\" Define a revision as a refinement of the agreed brief, not new direction.",
             "ro": "Limitați: „Prețul include două (2) runde de modificări pentru fiecare livrabil; modificările suplimentare se taxează cu [tarif]/oră.” Definiți modificarea ca ajustare a brief-ului agreat, nu direcție nouă."},
            clause, m.span()))
    for clause, m in each(doc, SATISFACTION):
        if unlimited and any(f.clause == clause.index for f in out):
            continue
        out.append(finding(
            "revisions.satisfaction", "Unpaid revisions", "medium",
            {"en": "Work must meet the client's own satisfaction", "ro": "Livrabilul trebuie să satisfacă clientul după propria apreciere"},
            {"en": "\"Satisfaction\" is undefined and decided by the client, which lets them reject or re-do work indefinitely and delay payment.",
             "ro": "„Satisfacția” nu este definită și o decide clientul, ceea ce îi permite să respingă sau să ceară refacerea lucrării la nesfârșit și să amâne plata."},
            {"en": "Replace with objective acceptance: written specs, a 5-10 business day review window, and deemed acceptance if the client is silent.",
             "ro": "Înlocuiți cu criterii obiective de recepție: specificații scrise, 5-10 zile lucrătoare pentru verificare și recepție tacită dacă clientul nu răspunde."},
            clause, m.span()))
    for clause in doc.clauses:
        if not FREE_CONTEXT.search(clause.folded):
            continue
        m = FREE_WINDOW.search(clause.folded)
        if not m:
            continue
        groups = [g for g in m.groups() if g]
        months = _months(groups[0], groups[1]) if len(groups) >= 2 else 0
        if months >= 6:
            out.append(finding(
                "revisions.free_window", "Unpaid revisions", "high" if months >= 12 else "medium",
                {"en": f"Free changes or fixes for {months} months", "ro": f"Modificări sau remedieri gratuite timp de {months} luni"},
                {"en": "Free post-delivery work for this long is open-ended unpaid support, far beyond a normal 30-90 day bug-fix warranty.",
                 "ro": "Muncă gratuită după livrare pe o perioadă atât de lungă înseamnă suport neplătit, mult peste garanția obișnuită de 30-90 de zile."},
                {"en": "Limit free corrections to defects against the written spec for 30-90 days after acceptance; bill anything else.",
                 "ro": "Limitați remedierile gratuite la defecte față de specificația scrisă, 30-90 de zile după recepție; restul se facturează."},
                clause, m.span()))
    if not unlimited and not doc.has(REV_CAP) and doc.has(DELIVERABLE):
        first = next((c for c in doc.clauses if REV_MENTION.search(c.folded)), None)
        out.append(finding(
            "revisions.no_cap", "Unpaid revisions", "medium",
            {"en": "No limit on revision rounds is stated", "ro": "Nu este stabilită nicio limită a rundelor de modificări"},
            {"en": "The contract names no number of revision rounds. Silence usually means the client expects changes until they are happy.",
             "ro": "Contractul nu menționează un număr de runde de modificări. Tăcerea înseamnă de obicei că clientul se așteaptă la modificări până este mulțumit."},
            {"en": "Add: \"Includes [2] rounds of revisions per deliverable; extra rounds billed at [rate]; client feedback due within [5] business days.\"",
             "ro": "Adăugați: „Include [2] runde de modificări pe livrabil; rundele suplimentare se taxează cu [tarif]; feedback-ul clientului în maximum [5] zile lucrătoare.”"},
            first))
    return out


# ---------------------------------------------------------------- IP assignment

IP_WORDS = rx(r"intellectual\s+property|copyright|work\s+product|deliverable|invention|\bworks?\b|\brights\b|drepturi|opera\b|operele|lucrar|livrabil|proprietate\s+intelectuala|creati")
ASSIGN = rx(
    r"\bassign", r"work[\s-]+made[\s-]+for[\s-]+hire", r"work[\s-]+for[\s-]+hire",
    r"(?:shall|will)\s+(?:be|remain)\s+(?:the\s+)?(?:sole\s+and\s+exclusive\s+)?(?:property|owned)",
    r"belongs?\s+to\s+(?:the\s+)?(?:client|company)", r"\bowned\s+by", r"\bvest\w*\s+(?:in|with)\s+(?:the\s+)?(?:client|company)",
    r"transfer\w*\s+.{0,40}?(?:ownership|title|rights)",
    r"cesion", r"cesiun", r"transmite\w*\s+.{0,40}?drepturi", r"proprietatea\s+(?:asupra|intelectuala)", r"drepturile?\s+patrimonial",
)
IMMEDIATE = rx(
    r"(?:upon|on|at)\s+(?:the\s+)?(?:creation|signing|execution|delivery|completion|substantial\s+completion)",
    r"as\s+(?:it\s+is|they\s+are)\s+created", r"\bautomatically\b",
    r"from\s+(?:the\s+)?(?:moment|time)\s+of\s+creation",
    r"la\s+(?:data\s+)?(?:crearii|semnarii|livrarii)", r"(?:din|in)\s+momentul\s+(?:crearii|semnarii|livrarii)",
)
PAY_CONDITION = rx(
    r"(?:full|final|complete)\s+payment", r"payment\s+in\s+full",
    r"(?:upon|after|following|subject\s+to|conditional\s+(?:up)?on|until)\s+(?:the\s+)?(?:receipt\s+of\s+|client'?s\s+)?(?:full\s+|final\s+|complete\s+)?payment",
    r"(?:paid|payment)\s+(?:in\s+full|of\s+all\s+(?:fees|amounts|sums))",
    r"plata\s+integral", r"dupa\s+(?:achitarea|plata|incasarea)", r"conditionat\w*\s+de\s+(?:plata|achitarea)",
)
BROAD_IP = rx(
    r"whether\s+or\s+not\s+(?:related|connected|relating)",
    r"whether\s+(?:now\s+)?(?:existing|pre-?existing)\s+or",
    r"(?:existing|pre-?existing|prior|previously\s+(?:created|developed)).{0,60}?(?:as\s+of|before|prior\s+to).{0,40}?(?:effective|date|agreement)",
    r"(?:all|any)\s+(?:inventions?|ideas?|works?|work\s+product|intellectual\s+property|discoveries)\b.{0,80}?(?:during\s+the\s+term|conceived|developed\s+(?:by|during))",
    r"(?:regardless|irrespective)\s+of\s+whether.{0,40}?(?:related|connected)",
    r"indiferent\s+daca\s+.{0,40}?(?:legat|conexe|are\s+legatura)",
    r"inclusiv\s+(?:cele|operele|lucrarile|creatiile)\s+(?:existente|create)\s+anterior",
)
LICENSE_BACK = rx(
    r"(?:pre-?existing|background|prior|contractor(?:'s)?\s+(?:tools|materials)|preexistent|instrumente\w*\s+proprii).{0,150}?(?:perpetual|irrevocabl|sublicens|perpetu)",
    r"(?:perpetual|irrevocabl|sublicens|perpetu).{0,150}?(?:pre-?existing|background|prior\s+(?:ip|works?|materials)|contractor(?:'s)?\s+(?:tools|materials)|preexistent|instrumente\w*\s+proprii)",
)
CARVE_OUT = rx(
    r"pre-?existing", r"background\s+(?:ip|technology|materials|intellectual)", r"prior\s+(?:ip|works?|materials|inventions)",
    r"contractor(?:'s)?\s+(?:tools|materials|retained)", r"retain\w*\s+(?:all\s+)?(?:right|ownership)", r"preexistent",
    r"anterioare", r"instrumente\w*\s+proprii", r"reserva\w*\s+(?:dreptul|drepturile)",
)


def detect_ip(doc: Doc) -> list:
    out = []
    ip_clauses = [c for c in doc.clauses if ASSIGN.search(c.folded) and IP_WORDS.search(c.folded)]
    if not ip_clauses:
        return out
    tied = any(PAY_CONDITION.search(c.folded) for c in ip_clauses)
    first = ip_clauses[0]
    immediate = next(((c, IMMEDIATE.search(c.folded)) for c in ip_clauses if IMMEDIATE.search(c.folded) and not PAY_CONDITION.search(c.folded)), None)
    if not tied:
        c, m = immediate if immediate else (first, ASSIGN.search(first.folded))
        out.append(finding(
            "ip.before_payment", "IP assignment", "high" if immediate else "medium",
            {"en": "Ownership passes to the client before you are paid" if immediate else "IP transfer is not tied to payment",
             "ro": "Drepturile trec la client înainte să fiți plătit" if immediate else "Cesiunea drepturilor nu este condiționată de plată"},
            {"en": "Once the client owns the work, you lose all leverage if an invoice goes unpaid and cannot re-license or withdraw it.",
             "ro": "Odată ce clientul deține lucrarea, nu mai aveți nicio pârghie dacă factura rămâne neplătită și nu o mai puteți relicenția sau retrage."},
            {"en": "Add: \"Ownership transfers only on receipt of full payment; until then Client has a revocable, non-exclusive licence to use the work.\"",
             "ro": "Adăugați: „Drepturile se cesionează doar la încasarea integrală a plății; până atunci Clientul are o licență neexclusivă și revocabilă.”"},
            c, m.span()))
    for c in ip_clauses:
        m = BROAD_IP.search(c.folded)
        if m:
            out.append(finding(
                "ip.broad_scope", "IP assignment", "high",
                {"en": "Assignment reaches past this project (prior, side or unrelated work)", "ro": "Cesiunea depășește proiectul (lucrări anterioare, personale sau fără legătură)"},
                {"en": "Wording like \"whether or not related\" or \"existing as of the effective date\" can hand over your older work, open-source code or side projects.",
                 "ro": "Formulări precum „indiferent dacă are legătură” sau „existente la data intrării în vigoare” pot transfera lucrările voastre mai vechi, codul open-source sau proiectele personale."},
                {"en": "Limit it to \"deliverables created specifically for this engagement and paid for\", and list your pre-existing IP in a schedule.",
                 "ro": "Limitați la „livrabilele create special pentru acest proiect și plătite” și enumerați într-o anexă proprietatea intelectuală preexistentă."},
                c, m.span()))
            break
    for c in doc.clauses:
        m = LICENSE_BACK.search(c.folded)
        if m:
            out.append(finding(
                "ip.license_back", "IP assignment", "high",
                {"en": "Perpetual, irrevocable licence over your own tools", "ro": "Licență perpetuă și irevocabilă asupra instrumentelor voastre"},
                {"en": "Your reusable code, templates or tools stay yours on paper, but the client may use and sublicense them forever, for free.",
                 "ro": "Codul, șabloanele sau instrumentele reutilizabile rămân ale voastre pe hârtie, dar clientul le poate folosi și sublicenția pe vecie, gratuit."},
                {"en": "Grant only a non-exclusive licence to use them as embedded in the deliverable, not transferable or sublicensable on their own.",
                 "ro": "Acordați doar o licență neexclusivă de utilizare a lor ca parte din livrabil, fără drept de transfer sau sublicențiere separată."},
                c, m.span()))
            break
    if not doc.has(CARVE_OUT):
        out.append(finding(
            "ip.no_carveout", "IP assignment", "medium",
            {"en": "No carve-out for your pre-existing tools and code", "ro": "Nicio excepție pentru instrumentele și codul vostru preexistent"},
            {"en": "Without a carve-out, anything you reuse in the deliverable risks being swept into the assignment.",
             "ro": "Fără o excepție, tot ce reutilizați în livrabil riscă să intre în cesiune."},
            {"en": "Add a clause: you keep your pre-existing materials and general know-how; the client gets a licence only to what is embedded in the deliverable.",
             "ro": "Adăugați o clauză: păstrați materialele preexistente și know-how-ul general; clientul primește licență doar pentru ce este inclus în livrabil."},
            first, ASSIGN.search(first.folded).span()))
    return out


# ---------------------------------------------------------------- payment

PAY_CONTEXT = rx(r"pay|invoice|fee\b|fees\b|compensation|remunerat|plat[aei]|factur|onorar|tarif")
AMOUNT = rx(r"[$€£]|\beur\b|\busd\b|\bron\b|\blei\b|\bfee\b|\bfees\b|\brate\b|hourly|\bprice|\bpret|onorar|tarif|remunerat")
UNIT = r"\s*(?:\(\d+\)\s*)?(calendar\s+|business\s+|working\s+|banking\s+|calendaristice\s+|lucratoare\s+|bancare\s+)?(?:days?|zile|zi)\b"
PAYTERM = [
    re.compile(r"\bnet[\s-]?(\d{2,3})\b"),
    re.compile(r"(?:pay|invoice|fee|compensat|remunerat|due|payable)\w*.{0,80}?(?:within|in|after|of)\s+" + NUM + UNIT, re.S),
    re.compile(r"(?:within|after)\s+" + NUM + UNIT + r".{0,60}?(?:of|from|after|following)\s+(?:the\s+|each\s+|an\s+|your\s+)?(?:receipt|date|issue|issuance|delivery|acceptance|completion)", re.S),
    re.compile(r"(?:plat|factur|achit|onorar|remunerat)\w*.{0,80}?(?:in\s+termen\s+de|dupa|la)\s+" + NUM + r"\s*(?:de\s+)?(?:zile|zi)(?:\s+(calendaristice|lucratoare|bancare))?", re.S),
    re.compile(r"in\s+termen\s+de\s+" + NUM + r"\s*(?:de\s+)?(?:zile|zi)(?:\s+(calendaristice|lucratoare|bancare))?\s+(?:de\s+la|dupa)\s+(?:primirea|emiterea|data)", re.S),
]
PAY_MONTHS = re.compile(r"(?:pay|invoice|payable|plat|factur)\w*.{0,60}?(?:within|after|in)\s+" + NUM + r"\s+(?:months?|luni)", re.S)
PAY_WHEN_PAID = rx(
    r"pay(?:ment)?[\s-]+(?:when|if|once|after|upon)[\s-]+paid",
    r"(?:when|if|once|after|as\s+soon\s+as)\s+(?:the\s+)?(?:client|company|customer)\s+(?:is\s+paid|has\s+been\s+paid|receives?\s+payment|receives?\s+funds|gets\s+paid)",
    r"paid\s+by\s+(?:its|their|the\s+client'?s)\s+(?:own\s+)?(?:client|customer)",
    r"(?:dupa\s+ce|numai\s+daca|dupa)\s+(?:beneficiarul|clientul|compania)\s+(?:incaseaza|primeste|a\s+incasat|a\s+primit)",
)
COND_SATISFACTION = rx(
    r"(?:payment|fees?|compensation)\b.{0,60}?(?:conditional|contingent|subject)\s+(?:up)?on\b.{0,60}?(?:satisf|approv|acceptance)",
    r"(?:plata|onorariul)\b.{0,60}?(?:conditionat|depinde)\w*\b.{0,60}?(?:satisf|aprob|acceptare)",
)
LATE_FEE = rx(r"late\s+(?:fee|payment|charge|interest)", r"interest\s+(?:on|for)\s+(?:overdue|late|unpaid)", r"overdue", r"dobanz", r"penalit", r"majorar", r"intarziere")
DEPOSIT = rx(r"deposit|advance|upfront|up-front|retainer|milestone|installment|avans|transe|etap|in\s+rate|(?:on|upon)\s+(?:signing|signature|execution)|la\s+semnare")


def payment_days(clause: Clause):
    """Return (days, match) of the longest payment term in the clause, or None."""
    text = clause.folded
    if re.search(r"terminat|rezilie|denunt", text) and not re.search(r"invoice|factur", text):
        return None
    best = None
    for pat in PAYTERM:
        for m in pat.finditer(text):
            groups = [g for g in m.groups() if g]
            if not groups:
                continue
            days = to_int(groups[0])
            kind = groups[1] if len(groups) > 1 else ""
            if kind.startswith(("business", "working", "lucr")):
                days = round(days * 1.45)
            if best is None or days > best[0]:
                best = (days, m)
    for m in PAY_MONTHS.finditer(text):
        days = to_int(m.group(1)) * 30
        if best is None or days > best[0]:
            best = (days, m)
    return best


def detect_payment(doc: Doc) -> list:
    out = []
    longest = None
    pay_clause_seen = False
    for clause in doc.clauses:
        if PAY_CONTEXT.search(clause.folded) and AMOUNT.search(clause.folded):
            pay_clause_seen = True
        found = payment_days(clause)
        if found and (longest is None or found[0] > longest[0]):
            longest = (found[0], found[1], clause)
    if longest:
        days, m, clause = longest
        sev = "high" if days >= 60 else "medium" if days >= 45 else "low" if days > 30 else None
        if sev:
            out.append(finding(
                "payment.long_terms", "Payment terms", sev,
                {"en": f"Payment due after {days} days", "ro": f"Plata se face după {days} de zile"},
                {"en": f"You finance the client for {days} days. Net 15-30 is normal for freelancers; 60+ days is a cash-flow risk, and the client can still pay later if you chase them.",
                 "ro": f"Finanțați clientul timp de {days} de zile. Pentru freelanceri, 15-30 de zile este normal; peste 60 de zile pune în pericol fluxul de numerar."
                        + (" Între profesioniști, Legea 72/2013 limitează termenele contractuale la 60 de zile (peste, doar dacă nu sunt abuzive)." if days > 60 else "")},
                {"en": "Counter with Net 15 or Net 30, a 30-50% deposit up front, and milestone invoices.",
                 "ro": "Propuneți 15 sau 30 de zile, un avans de 30-50% și facturare pe etape."},
                clause, m.span()))
    elif pay_clause_seen:
        first = next(c for c in doc.clauses if PAY_CONTEXT.search(c.folded) and AMOUNT.search(c.folded))
        out.append(finding(
            "payment.no_due_date", "Payment terms", "medium",
            {"en": "Fees are mentioned but no payment deadline is set", "ro": "Sunt menționate onorarii, dar fără termen de plată"},
            {"en": "Without a due date you cannot say when an invoice is late, and late-payment remedies are harder to claim.",
             "ro": "Fără un termen de plată nu puteți stabili când o factură este întârziată, iar remediile pentru întârziere sunt mai greu de cerut."},
            {"en": "State a due date, e.g. \"Invoices are payable within 14 days of the invoice date.\"",
             "ro": "Stabiliți un termen, de ex. „Facturile se plătesc în 14 zile de la data facturii.”"},
            first))
    for clause, m in each(doc, PAY_WHEN_PAID):
        out.append(finding(
            "payment.pay_when_paid", "Payment terms", "high",
            {"en": "You are paid only when the client's own customer pays", "ro": "Sunteți plătit doar dacă clientul clientului plătește"},
            {"en": "You carry the risk of the client's customers and may wait indefinitely for money you already earned.",
             "ro": "Preluați riscul clienților clientului și puteți aștepta nedefinit bani deja câștigați."},
            {"en": "Strike it: your fee is due on a fixed date regardless of whom the client has billed.",
             "ro": "Eliminați: onorariul este datorat la o dată fixă, indiferent de încasările clientului."},
            clause, m.span()))
        break
    for clause, m in each(doc, COND_SATISFACTION):
        out.append(finding(
            "payment.conditional", "Payment terms", "high",
            {"en": "Payment depends on the client's satisfaction or approval", "ro": "Plata depinde de satisfacția sau aprobarea clientului"},
            {"en": "A client who never approves never has to pay.", "ro": "Un client care nu aprobă niciodată nu trebuie să plătească niciodată."},
            {"en": "Tie payment to delivery, with deemed acceptance after 5-10 business days of silence.",
             "ro": "Legați plata de livrare, cu recepție tacită după 5-10 zile lucrătoare fără răspuns."},
            clause, m.span()))
        break
    if pay_clause_seen or longest:
        if not doc.has(LATE_FEE):
            out.append(finding(
                "payment.no_late_fee", "Payment terms", "medium",
                {"en": "No late-payment fee or interest", "ro": "Fără penalități sau dobândă pentru întârziere"},
                {"en": "Clients have no reason to pay on time if lateness is free. Fees generally must be agreed in advance to be enforceable.",
                 "ro": "Clientul nu are motiv să plătească la timp dacă întârzierea este gratuită. Penalitățile trebuie convenite în avans."},
                {"en": "Add: \"Overdue amounts accrue interest of 1.5% per month (or the statutory maximum).\"",
                 "ro": "Adăugați: „Sumele restante produc dobândă penalizatoare de [x]% pe zi/lună (sau maximul legal).” În România se aplică oricum dobânda legală penalizatoare."}))
        if not doc.has(DEPOSIT):
            out.append(finding(
                "payment.no_deposit", "Payment terms", "low",
                {"en": "No deposit or milestone payments", "ro": "Fără avans sau plăți pe etape"},
                {"en": "All payment comes after the work is done, so you carry the full risk.",
                 "ro": "Toată plata vine după finalizare, deci purtați tot riscul."},
                {"en": "Ask for 30-50% up front, or split the fee into milestones.",
                 "ro": "30-50% avans sau împărțirea onorariului pe etape."}))
    return out


# ---------------------------------------------------------------- non-compete

NONCOMPETE = rx(
    r"non-?\s?compet", r"not\s+(?:to\s+)?compet",
    r"restrictive\s+covenant", r"competes?\s+with\s+(?:the\s+)?(?:client|company)",
    r"shall\s+not,?\s+(?:directly\s+or\s+indirectly,?\s+)?(?:provide|perform|render|offer|engage|work|be\s+engaged|accept)\b.{0,100}?(?:compet|similar|same|any\s+other\s+(?:client|customer|company))",
    r"neconcurent", r"nu\s+va\s+(?:presta|desfasura|furniza|lucra)\b.{0,100}?(?:similar|concurent|alt\w+\s+client|alti\s+clienti)",
)
EXCLUSIVITY = rx(
    r"exclusive(?:ly)?\s+(?:to|for|with)\s+(?:the\s+)?(?:client|company)",
    r"(?:work|provide\s+(?:services|work))\s+exclusively",
    r"during\s+the\s+term.{0,60}?(?:no|any)\s+other\s+(?:client|customer|work|engagement)",
    r"exclusivitate",
)
NONSOLICIT = rx(r"non-?\s?solicit", r"not\s+(?:to\s+)?solicit", r"nu\s+va\s+(?:solicita|racola|atrage)", r"neraco")
DURATION = re.compile(NUM + r"\s*(?:\(\d+\)\s*)?(months?|years?|luni|luna|ani|an)\b")
BROAD_SCOPE = rx(r"industry|sector|worldwide|global|any\s+(?:company|business|client|customer|person|entity)|entire|domeniu|oriunde|orice\s+(?:companie|client|persoana|societate)|toate")


def detect_noncompete(doc: Doc) -> list:
    out = []
    for kind, pat in (("noncompete", NONCOMPETE), ("exclusivity", EXCLUSIVITY)):
        for clause, m in each(doc, pat):
            dur = DURATION.search(clause.folded)
            months = _months(dur.group(1), dur.group(2)) if dur else None
            broad = bool(BROAD_SCOPE.search(clause.folded))
            sev = "high" if (months is None or months >= 12 or broad or kind == "exclusivity") else "medium"
            span = {"en": f"{months} months" if months else "no stated end",
                    "ro": f"{months} luni" if months else "fără dată de încheiere"}
            out.append(finding(
                f"noncompete.{kind}", "Non-compete", sev,
                {"en": "Non-compete restricts your other clients" if kind == "noncompete" else "Exclusivity: you may not work for others",
                 "ro": "Clauză de neconcurență care vă limitează ceilalți clienți" if kind == "noncompete" else "Exclusivitate: nu puteți lucra pentru alții"},
                {"en": f"This can block you from serving whole segments of the market ({span['en']}{', broad scope' if broad else ''}). A freelancer lives on many clients; a blanket ban can mean no income, usually unpaid.",
                 "ro": f"Vă poate bloca accesul la segmente întregi de piață ({span['ro']}{', domeniu larg' if broad else ''}). Un freelancer trăiește din mai mulți clienți; o interdicție generală înseamnă venit zero, de obicei necompensat."},
                {"en": "Delete it, or narrow to 2-3 named direct competitors, project-only duration (max ~6 months) and pay for the restriction. Also check local law on contractor non-competes.",
                 "ro": "Eliminați-o sau restrângeți la 2-3 concurenți numiți, doar pe durata proiectului (max ~6 luni) și cu compensație. Verificați și legea locală privind neconcurența colaboratorilor."},
                clause, m.span()))
            break
    ns = next(each(doc, NONSOLICIT), None)
    if ns:
        clause, m = ns
        dur = DURATION.search(clause.folded)
        months = _months(dur.group(1), dur.group(2)) if dur else None
        out.append(finding(
            "noncompete.nonsolicit", "Non-compete", "medium" if (months is None or months > 24) else "low",
            {"en": "Non-solicitation clause", "ro": "Clauză de neîncercare de a atrage clienți sau personal"},
            {"en": "Usually acceptable if short and limited to named people, but it can stop you from working with the client's own contacts or customers afterwards.",
             "ro": "De obicei acceptabilă dacă este scurtă și limitată la persoane numite, dar vă poate împiedica să lucrați ulterior cu contactele sau clienții clientului."},
            {"en": "Limit to 6-12 months and to people you worked with directly.",
             "ro": "Limitați la 6-12 luni și la persoanele cu care ați lucrat direct."},
            clause, m.span()))
    return out


# ---------------------------------------------------------------- liability

UNLIMITED_LIAB = rx(
    r"unlimited\s+liabilit", r"liabilit\w*\s+(?:shall\s+be|is|will\s+be)\s+unlimited", r"\buncapped\b",
    r"without\s+(?:any\s+)?(?:limit|cap)\w*.{0,30}?(?:liabilit|damages)", r"(?:liabilit|damages).{0,40}?without\s+(?:any\s+)?(?:limit|cap)",
    r"no\s+(?:limit|cap)\s+(?:on|to)\s+(?:the\s+)?(?:liabilit|damages)",
    r"raspundere\w*\s+nelimitat", r"raspunde\w*\s+(?:nelimitat|fara\s+limita)", r"fara\s+limita\w*\s+de\s+raspundere",
)
LIAB_CAP = rx(
    r"(?:liabilit\w*|responsab\w*|raspunder\w*).{0,100}?(?:shall\s+not\s+exceed|limited\s+to|capped|not\s+exceed|maximum|nu\s+(?:va|poate)\s+depasi|se\s+limiteaza|limitat\w*\s+la)",
    r"cap\s+on\s+liability", r"limitation\s+of\s+liability", r"limitarea\s+raspunderii", r"total\s+liability",
)
INDEMNITY = rx(r"indemnif", r"hold\s+harmless", r"despagubi", r"exonera\w*\s+.{0,30}?de\s+raspundere")
BROAD_INDEMNITY = rx(r"any\s+and\s+all", r"all\s+(?:claims|losses|damages|liabilit|costs)", r"\borice\b", r"toate\s+(?:pierderile|daunele|pretentiile|costurile)")
CONSEQUENTIAL = re.compile(r"(?:liable|responsible|raspunde|raspunzator)\w*.{0,60}?(?:consequential|indirect|lost\s+profits?|loss\s+of\s+(?:profit|revenue|business)|beneficiul\s+nerealizat|pierderi\s+indirecte)", re.S)
NEGATION = re.compile(r"\bnot\b|\bno\b|\bneither\b|\bnor\b|exclud|waive|disclaim|nu\s+(?:va|vor)|fara")


def detect_liability(doc: Doc) -> list:
    out = []
    capped = doc.has(LIAB_CAP)
    reported_unlimited = False
    for clause, m in each(doc, UNLIMITED_LIAB):
        reported_unlimited = True
        out.append(finding(
            "liability.unlimited", "Liability", "high",
            {"en": "Unlimited liability", "ro": "Răspundere nelimitată"},
            {"en": "One mistake on a small job could cost you more than the whole fee, up to your personal assets if you are a sole trader.",
             "ro": "O singură greșeală la un proiect mic vă poate costa mai mult decât întregul onorariu, până la bunurile personale dacă sunteți PFA."},
            {"en": "Cap total liability at the fees paid in the last 12 months (or the project fee), mutual, and exclude indirect and consequential damages.",
             "ro": "Plafonați răspunderea totală la onorariile încasate în ultimele 12 luni (sau valoarea proiectului), reciproc, și excludeți daunele indirecte."},
            clause, m.span()))
        break
    ind = next(each(doc, INDEMNITY), None)
    if ind:
        clause, m = ind
        broad = bool(BROAD_INDEMNITY.search(clause.folded))
        sev = "high" if broad and not capped else "medium"
        out.append(finding(
            "liability.indemnity", "Liability", sev,
            {"en": "Broad indemnity: you cover the client's losses" if broad else "Indemnity clause (check who covers whom)",
             "ro": "Despăgubire largă: acoperiți pierderile clientului" if broad else "Clauză de despăgubire (verificați cine pe cine acoperă)"},
            {"en": "You promise to pay the client's costs and claims, possibly even ones you did not cause, and usually without a ceiling.",
             "ro": "Vă angajați să plătiți costurile și pretențiile clientului, posibil chiar pentru fapte care nu v-au aparținut, de obicei fără plafon."},
            {"en": "Make it mutual, limit to third-party claims caused by your breach or negligence, and subject it to the liability cap.",
             "ro": "Faceți-o reciprocă, limitată la pretenții ale terților cauzate de culpa voastră, și supusă plafonului de răspundere."},
            clause, m.span()))
    for clause in doc.clauses:
        m = CONSEQUENTIAL.search(clause.folded)
        if m and not NEGATION.search(clause.folded[max(0, m.start() - 40):m.end()]):
            out.append(finding(
                "liability.consequential", "Liability", "high",
                {"en": "You are liable for indirect losses and lost profits", "ro": "Răspundeți pentru pierderi indirecte și beneficii nerealizate"},
                {"en": "The client's lost business can dwarf your fee.", "ro": "Afacerea pierdută a clientului poate depăși cu mult onorariul vostru."},
                {"en": "Exclude consequential, indirect and lost-profit damages for both sides.",
                 "ro": "Excludeți daunele indirecte și beneficiul nerealizat pentru ambele părți."},
                clause, m.span()))
            break
    if not capped and not reported_unlimited:
        first = ind[0] if ind else None
        out.append(finding(
            "liability.no_cap", "Liability", "high" if ind else "medium",
            {"en": "No limitation of liability found", "ro": "Nu există nicio limitare a răspunderii"},
            {"en": "With no cap, the law's default applies: you answer for all provable damage, however large compared with your fee.",
             "ro": "Fără plafon se aplică dreptul comun: răspundeți pentru tot prejudiciul dovedit, oricât de mare față de onorariu."},
            {"en": "Add: \"Each party's total liability is limited to the fees paid under this agreement; neither party is liable for indirect damages.\"",
             "ro": "Adăugați: „Răspunderea totală a fiecărei părți este limitată la onorariile plătite în baza contractului; nicio parte nu răspunde pentru daune indirecte.”"},
            first, ind[1].span() if ind else None))
    return out


# ---------------------------------------------------------------- other quiet clauses

TERMINATION = rx(r"terminate\b", r"upon\s+termination", r"termination\s+(?:of|for|by|without)", r"cancel", r"rezilie", r"denunt", r"anulare")
TERM_CONVENIENCE = rx(
    r"terminate\b.{0,80}?(?:for\s+convenience|at\s+any\s+time|for\s+any\s+reason|without\s+cause|sole\s+discretion)",
    r"(?:for\s+convenience|without\s+cause)\b.{0,60}?terminat",
    r"(?:denunta|rezili)\w*\s+unilateral.{0,60}?(?:oricand|fara\s+(?:motiv|preaviz))", r"fara\s+preaviz",
)
PAID_ON_EXIT = rx(
    r"kill\s+fee", r"cancell?ation\s+fee", r"pay\w*\s+for\s+(?:all\s+)?(?:work|services)\s+(?:completed|performed|done|rendered)",
    r"(?:work|services)\s+(?:completed|performed|rendered|delivered)\s+(?:up\s+to|through|until|prior|before)",
    r"taxa\s+de\s+anulare", r"(?:serviciile|lucrarile)\s+(?:prestate|efectuate|realizate)",
)
ABSOLUTE_WARRANTY = rx(
    r"error[\s-]free", r"bug[\s-]free", r"defect[\s-]free", r"uninterrupted", r"free\s+from\s+(?:all\s+)?(?:defects|errors|bugs)",
    r"guarantee[sd]?\s+(?:that\s+)?(?:the\s+)?(?:work|deliverables?|results?|services?)",
    r"fara\s+(?:erori|defecte)", r"garanteaza\s+(?:ca\s+)?(?:rezultat|livrabil)",
)
SCOPE_CREEP = rx(
    r"(?:additional|extra|further|other)\s+(?:work|services|tasks|deliverables)\b.{0,60}?(?:at\s+no\s+(?:additional\s+)?(?:cost|charge|fee)|without\s+(?:additional\s+)?(?:charge|cost|compensation)|included)",
    r"as\s+(?:may\s+be\s+)?(?:reasonably\s+)?(?:requested|required|directed)\s+by\s+(?:the\s+)?(?:client|company)",
    r"from\s+time\s+to\s+time\s+(?:as\s+)?(?:requested|directed)",
    r"servicii\s+suplimentare.{0,60}?(?:fara\s+(?:plata|cost|costuri|taxa)|inclus)",
)
UNILATERAL = rx(
    r"(?:client|company|beneficiar\w*)\s+(?:may|can|reserves\s+the\s+right\s+to)\s+(?:modify|amend|change|update)\s+(?:this|these|the)\s+(?:agreement|terms|contract)\b.{0,40}?(?:at\s+any\s+time|unilateral|sole\s+discretion|without)",
    r"modifica\w*\s+unilateral",
)
AUTORENEW = rx(r"automatic(?:ally)?\s+(?:renew|extend)", r"auto-?renew", r"se\s+(?:prelungeste|reinnoieste)\s+automat", r"prelungire\s+automata", r"reinnoire\s+automata")
CONFIDENTIAL = rx(r"confiden")
PERPETUAL = rx(r"in\s+perpetuity", r"perpetual", r"indefinite", r"forever", r"fara\s+limita\s+de\s+timp", r"nelimitat\s+in\s+timp", r"pe\s+perioada\s+nedeterminata")
DISPUTES = rx(r"arbitra", r"exclusive\s+jurisdiction", r"venue", r"jurisdictia\s+exclusiva", r"instantel?\s+(?:din|de\s+la)")
INSURANCE = rx(r"(?:maintain|carry|obtain|procure)\s+.{0,40}?insurance", r"(?:asigurare|asigurari)\s+(?:de\s+raspundere|profesional)")


PENALTY = rx(
    r"liquidated\s+damages", r"(?:penalt(?:y|ies)|late\s+(?:delivery|completion)\s+(?:fee|charge))\b.{0,80}?(?:delay|late|deadline|each\s+day|per\s+day)",
    r"(?:delay|late|deadline|each\s+day|per\s+day).{0,80}?(?:penalt(?:y|ies)|deduct)",
    r"penalitati?\s+de\s+intarziere\s+(?:pentru\s+)?(?:prestator|livrare)", r"(?:prestatorul|contractorul)\s+datoreaza\s+penalit",
)
NO_PORTFOLIO_MENTION = rx(r"portfolio", r"self-?promotion", r"promotional\s+purposes", r"portofoliu", r"promovare")
CONTROL = rx(
    r"(?:fixed|set|regular|standard)\s+(?:working\s+)?hours", r"(?:normal|regular)\s+business\s+hours",
    r"(?:shall|must)\s+(?:personally\s+)?(?:perform|render|provide)\b.{0,40}?(?:personally|in\s+person)",
    r"(?:may|shall)\s+not\s+(?:subcontract|delegate|use\s+(?:a\s+)?(?:substitute|replacement))",
    r"(?:on|at)\s+(?:the\s+)?client'?s\s+premises", r"(?:request|approval)\s+for\s+(?:leave|time\s+off|vacation)",
    r"program\s+de\s+lucru\s+(?:fix|stabilit)", r"nu\s+poate\s+(?:subcontracta|delega)",
)
RO_ASSIGNMENT = rx(r"cesion", r"cesiun")
RO_DURATION = rx(r"durat", r"perioad", r"termen\s+de\s+\d", r"nelimitat", r"pe\s+viata")
RO_TERRITORY = rx(r"teritori", r"mondial", r"romania")


def _simple(doc, pat, rule, cat, sev, title, why, fix, only_if=None) -> list:
    for clause, m in each(doc, pat):
        if only_if and not only_if(clause):
            continue
        return [finding(rule, cat, sev, title, why, fix, clause, m.span())]
    return []


def detect_other(doc: Doc) -> list:
    out = []
    conv = _simple(
        doc, TERM_CONVENIENCE, "termination.convenience", "Termination", "medium",
        {"en": "Client can end the deal at any time", "ro": "Clientul poate rezilia oricând"},
        {"en": "If you are not guaranteed payment for work already done, the client can walk away from the unpaid part.",
         "ro": "Dacă nu aveți garantată plata pentru munca deja făcută, clientul poate renunța la partea neplătită."},
        {"en": "Allow it only with notice and payment for all work done plus a kill fee (often ~25% of the remaining value).",
         "ro": "Acceptați doar cu preaviz și plata întregii munci efectuate plus o taxă de anulare (adesea ~25% din valoarea rămasă)."},
        only_if=lambda c: not re.search(r"either\s+party|both\s+parties|ambele\s+parti|oricare\s+dintre\s+parti", c.folded),
    )
    out += conv
    if doc.has(TERMINATION) and not doc.has(PAID_ON_EXIT):
        first = next(c for c in doc.clauses if TERMINATION.search(c.folded))
        out.append(finding(
            "termination.no_kill_fee", "Termination", "medium",
            {"en": "No payment for work done or kill fee on cancellation", "ro": "Nu e prevăzută plata muncii efectuate sau taxa de anulare"},
            {"en": "If the project is cancelled midway you may be paid nothing for the work already delivered.",
             "ro": "Dacă proiectul este anulat pe parcurs, puteți rămâne fără plată pentru munca deja livrată."},
            {"en": "Add: \"On termination Client pays for all work performed to date plus [25]% of the remaining fee.\"",
             "ro": "Adăugați: „La reziliere Clientul plătește toată munca efectuată până la acea dată plus [25]% din onorariul rămas.”"},
            first, TERMINATION.search(first.folded).span()))
    out += _simple(
        doc, ABSOLUTE_WARRANTY, "warranty.absolute", "Warranties", "medium",
        {"en": "Absolute promise (error-free, guaranteed results)", "ro": "Promisiune absolută (fără erori, rezultate garantate)"},
        {"en": "No real work is flawless; an absolute warranty makes every defect a breach.",
         "ro": "Nicio lucrare reală nu este perfectă; o garanție absolută transformă orice defect în încălcare de contract."},
        {"en": "Warrant only conformance to the written spec for 30 days, with fixing as the sole remedy.",
         "ro": "Garantați doar conformitatea cu specificația scrisă pentru 30 de zile, remedierea fiind unica despăgubire."})
    out += _simple(
        doc, SCOPE_CREEP, "scope.open_ended", "Scope", "medium",
        {"en": "Open-ended scope or extras at no charge", "ro": "Domeniu de lucru deschis sau extra fără plată"},
        {"en": "\"As requested by the client\" lets the job grow while the fee stays fixed.",
         "ro": "„La solicitarea clientului” lasă proiectul să crească în timp ce prețul rămâne fix."},
        {"en": "List named deliverables; anything else needs a written change order with a price.",
         "ro": "Enumerați livrabilele; orice altceva necesită un act adițional scris cu preț."})
    out += _simple(
        doc, UNILATERAL, "terms.unilateral_change", "Scope", "medium",
        {"en": "Client can change the contract on its own", "ro": "Clientul poate modifica singur contractul"},
        {"en": "Terms you agreed to can change without your consent.", "ro": "Termenii agreați se pot schimba fără acordul vostru."},
        {"en": "Require written amendments signed by both parties.", "ro": "Cereți modificări scrise, semnate de ambele părți."})
    out += _simple(
        doc, AUTORENEW, "terms.auto_renew", "Scope", "low",
        {"en": "Contract renews automatically", "ro": "Contractul se prelungește automat"},
        {"en": "You may be locked in for another term if you miss a notice window.", "ro": "Puteți rămâne legat pentru încă o perioadă dacă ratați termenul de preaviz."},
        {"en": "Ask for renewal by mutual written agreement, or a short opt-out window you can calendar.",
         "ro": "Cereți prelungire doar prin acord scris sau un termen scurt de renunțare pe care îl puteți urmări."})
    out += _simple(
        doc, PERPETUAL, "confidentiality.perpetual", "Confidentiality", "low",
        {"en": "Confidentiality or restriction with no end date", "ro": "Confidențialitate sau restricție fără dată de încheiere"},
        {"en": "A forever-NDA with no standard exclusions can stop you from reusing general know-how.",
         "ro": "Un acord de confidențialitate fără limită și fără excepții standard vă poate împiedica să folosiți know-how-ul general."},
        {"en": "Ask for 3-5 years after the end, with standard exclusions (public, independently developed, already known).",
         "ro": "Cereți 3-5 ani de la încheiere, cu excepțiile standard (public, dezvoltat independent, deja cunoscut)."},
        only_if=lambda c: bool(CONFIDENTIAL.search(c.folded)))
    out += _simple(
        doc, DISPUTES, "disputes.forum", "Disputes", "low",
        {"en": "Check where disputes are decided", "ro": "Verificați unde se soluționează litigiile"},
        {"en": "Arbitration or a far-away court can cost more than a small invoice is worth.",
         "ro": "Arbitrajul sau o instanță îndepărtată poate costa mai mult decât o factură mică."},
        {"en": "Prefer your home courts, a small-claims carve-out and remote hearings.",
         "ro": "Preferați instanțele din localitatea voastră, o excepție pentru pretenții mici și audieri la distanță."})
    out += _simple(
        doc, INSURANCE, "insurance.required", "Insurance", "low",
        {"en": "You must carry insurance", "ro": "Sunteți obligat să aveți asigurare"},
        {"en": "Insurance limits sized for large vendors can cost more than a small contract earns.",
         "ro": "Limitele de asigurare gândite pentru furnizori mari pot costa mai mult decât câștigați din contract."},
        {"en": "Negotiate the limits or have the client reimburse the premium.",
         "ro": "Negociați limitele sau cereți clientului să ramburseze prima."})
    out += _simple(
        doc, PENALTY, "delivery.penalty", "Scope", "medium",
        {"en": "Penalties or liquidated damages for delay", "ro": "Penalități sau daune convenite pentru întârziere"},
        {"en": "You pay per day of delay, even when the delay was caused by late client feedback, and often with no ceiling.",
         "ro": "Plătiți pe zi de întârziere, chiar dacă întârzierea vine din feedback-ul tardiv al clientului, adesea fără plafon."},
        {"en": "Make deadlines move with client delays, cap the penalty (e.g. 5-10% of the fee) and make it the client's sole remedy.",
         "ro": "Legați termenele de răspunsurile clientului, plafonați penalitatea (de ex. 5-10% din onorariu) și faceți-o unica despăgubire."})
    out += _simple(
        doc, CONTROL, "classification.control", "Scope", "low",
        {"en": "Employee-like control (fixed hours, personal service, no substitute)", "ro": "Control de tip angajat (program fix, prestare personală, fără înlocuitor)"},
        {"en": "Terms that dictate when and how you work blur the line between contractor and employee: you take the risk of a contractor without a contractor's freedom, and tax or labour authorities may reclassify the relationship.",
         "ro": "Clauzele care dictează când și cum lucrați estompează granița dintre colaborator și angajat: purtați riscul unui colaborator fără libertatea lui, iar autoritățile fiscale sau de muncă pot reîncadra relația."},
        {"en": "Describe results and deadlines instead of hours, allow substitution or subcontracting, and work from your own premises and tools.",
         "ro": "Descrieți rezultate și termene în loc de ore, permiteți înlocuirea sau subcontractarea și lucrați din spațiul și cu echipamentul vostru."})
    ip_clause = next((c for c in doc.clauses if ASSIGN.search(c.folded) and IP_WORDS.search(c.folded)), None)
    if ip_clause and not doc.has(NO_PORTFOLIO_MENTION):
        out.append(finding(
            "ip.no_portfolio", "IP assignment", "low",
            {"en": "No right to show the work in your portfolio", "ro": "Niciun drept de a arăta lucrarea în portofoliu"},
            {"en": "After a full assignment you technically need permission to show your own work.",
             "ro": "După o cesiune integrală, tehnic aveți nevoie de permisiune ca să vă arătați propria lucrare."},
            {"en": "Add: \"Contractor may display the deliverables in a portfolio after public release.\"",
             "ro": "Adăugați: „Prestatorul poate afișa livrabilele în portofoliu după lansarea publică.”"},
            ip_clause, ASSIGN.search(ip_clause.folded).span()))
    ro_clause = next((c for c in doc.clauses if RO_ASSIGNMENT.search(c.folded) and IP_WORDS.search(c.folded)), None)
    if ro_clause and not (RO_DURATION.search(ro_clause.folded) and RO_TERRITORY.search(ro_clause.folded)):
        out.append(finding(
            "ip.ro_cession_scope", "IP assignment", "medium",
            {"en": "Romanian copyright assignment without stated duration or territory", "ro": "Cesiune de drepturi de autor fără durată sau teritoriu precizate"},
            {"en": "Romanian copyright law expects an assignment to state its scope, duration, territory and remuneration; a vague blanket cession is both unfavourable to you and legally shaky. Confirm with a lawyer.",
             "ro": "Legea nr. 8/1996 presupune ca cesiunea să precizeze modul de exploatare, durata, teritoriul și remunerația; o cesiune generală și vagă este defavorabilă și nesigură juridic. Confirmați cu un avocat."},
            {"en": "Spell out which uses, for how long, where, and at what price the rights are assigned.",
             "ro": "Precizați ce moduri de exploatare, pentru cât timp, unde și la ce preț se cesionează drepturile."},
            ro_clause, RO_ASSIGNMENT.search(ro_clause.folded).span()))
    return out


DETECTORS: list[Callable[[Doc], list]] = [
    detect_revisions, detect_ip, detect_payment, detect_noncompete, detect_liability, detect_other,
]
