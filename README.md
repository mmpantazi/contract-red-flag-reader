# Contract Red-Flag Reader

Offline scanner that reads a freelance or service contract and flags the clauses that hurt solo freelancers, with the exact sentence, a plain-language explanation and wording to ask for instead. English and Romanian contracts; notes follow the contract's language by default (`--lang en|ro` to force). *RO: găsește clauzele periculoase din contractele de freelancing.*

Nothing is uploaded; there is no AI model and no network access. Python 3.9+ standard library only.

## What it flags

| Category | Examples |
|---|---|
| Unpaid revisions | "until the Client is fully satisfied", unlimited rounds, free fixes for years, no stated cap |
| IP assignment | ownership on creation (not on payment), "whether or not related", prior/side work, perpetual licence over your tools, no carve-out |
| Payment terms | Net 45/60/90, pay-when-paid, payment on "satisfaction", no due date, no late fee, no deposit |
| Non-compete | industry-wide bans, exclusivity, long non-solicits |
| Liability | "unlimited", broad indemnity, lost-profits liability, no cap at all |
| Quiet clauses | client-only termination, no kill fee, "error-free" warranties, open-ended scope, unilateral changes, auto-renewal, forever-NDA, arbitration/venue, insurance, delay penalties, employee-like control (fixed hours, no substitute), no portfolio right, Romanian cession without duration/territory |

Thresholds follow common freelancer guidance (see the research notes): Net 30 or less is fine, 31-44 days low, 45-59 medium, 60+ high.

## Run

```bash
python -m redflag contract.txt                 # text report
python -m redflag contract.docx --lang ro      # force Romanian notes (default: auto-detect)
python -m redflag contract.txt --format json   # or markdown
python -m redflag - < contract.txt             # stdin
python -m redflag contract.txt --min-severity medium --fail-on high   # exit 1 if any high finding
```

Inputs: `.txt`, `.md`, `.docx` (built in), `.pdf` (needs `pdftotext` from poppler-utils; otherwise export to text). Scanned PDFs without a text layer are not supported.

Optional install: `pip install .` gives a `redflag` command.

Try it: `python -m redflag examples/bad_en.txt`, `examples/bad_ro.txt` (Romanian), `examples/realistic_en.txt` (typical client-drafted contract), `examples/fair_en.txt` (clean).

Exit codes: 0 ok, 1 findings at or above `--fail-on`, 2 unreadable input.

## Tests

```bash
python -m unittest discover -s tests
```

## Limits

- Each finding has a stable `rule` id in the JSON output (e.g. `payment.long_terms`, `ip.before_payment`) so you can filter results.
- Keyword and pattern matching: it misses unusual wording and can misread context. A clean result is not a safe contract.
- Sources are mostly US-centric. The only local-law hint is the Romanian note on Law 72/2013 payment terms; non-compete enforceability varies by country.
- Not legal advice. Have a lawyer check contracts with real money or IP at stake.

## Layout

`redflag/text.py` loading and clause splitting, `redflag/rules.py` detectors (each finding has EN and RO text), `redflag/report.py` output, `redflag/cli.py` entry point.
