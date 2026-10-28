import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

from redflag.cli import main
from redflag.scanner import scan
from redflag.text import fold, load, split_clauses

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rules(text):
    return {f.rule for f in scan(text)}


def sev(text, rule):
    return next((f.severity for f in scan(text) if f.rule == rule), None)


class Revisions(unittest.TestCase):
    def test_unlimited_variants(self):
        for t in (
            "Contractor shall provide revisions until the Client is fully satisfied.",
            "The fee includes unlimited revisions.",
            "Contractor will make as many changes as needed.",
            "Prestatorul va face modificări nelimitate.",
            "Prestatorul face oricâte modificări cere Beneficiarul.",
        ):
            self.assertIn("revisions.unlimited", rules(t), t)

    def test_capped_revisions_ok(self):
        t = "Design work. The fee includes two (2) rounds of revisions per deliverable."
        self.assertNotIn("revisions.unlimited", rules(t))
        self.assertNotIn("revisions.no_cap", rules(t))

    def test_missing_cap(self):
        self.assertIn("revisions.no_cap", rules("Contractor will design the website and deliver the files."))

    def test_free_window(self):
        t = "Contractor will make corrections free of charge for 3 years after delivery."
        self.assertEqual(sev(t, "revisions.free_window"), "high")
        t = "Contractor will fix bugs at no charge for 30 days after delivery."
        self.assertNotIn("revisions.free_window", rules(t))


class IP(unittest.TestCase):
    def test_immediate_assignment(self):
        t = "Contractor assigns all intellectual property in the deliverables to Client upon creation."
        self.assertEqual(sev(t, "ip.before_payment"), "high")

    def test_tied_to_payment(self):
        t = "Ownership of the deliverables transfers to Client upon receipt of full payment. Contractor retains pre-existing materials."
        r = rules(t)
        self.assertNotIn("ip.before_payment", r)
        self.assertNotIn("ip.no_carveout", r)

    def test_broad(self):
        t = "Contractor assigns all inventions, whether or not related to the Services, to Client."
        self.assertIn("ip.broad_scope", rules(t))

    def test_license_back(self):
        t = "Contractor assigns the work product to Client. Pre-existing materials are licensed to Client on a perpetual, irrevocable basis."
        self.assertIn("ip.license_back", rules(t))

    def test_no_ip_clause_no_ip_findings(self):
        self.assertFalse({r for r in rules("Client will pay within 14 days.") if r.startswith("ip.")})


class Payment(unittest.TestCase):
    def test_thresholds(self):
        for days, expected in ((30, None), (40, "low"), (45, "medium"), (60, "high"), (90, "high")):
            t = f"Invoices are payable within {days} days of receipt. Fee is $1,000."
            self.assertEqual(sev(t, "payment.long_terms"), expected, days)

    def test_net_and_words(self):
        self.assertEqual(sev("Payment terms: Net 90. Fee $500.", "payment.long_terms"), "high")
        self.assertEqual(sev("Client shall pay the fee within sixty (60) days of the invoice date.", "payment.long_terms"), "high")

    def test_business_days_converted(self):
        self.assertEqual(sev("Invoices are payable within 30 business days. Fee $100.", "payment.long_terms"), "low")

    def test_termination_notice_is_not_payment(self):
        t = "Either party may terminate on 90 days notice. Fee is $100, payable within 14 days."
        self.assertNotIn("payment.long_terms", rules(t))

    def test_romanian(self):
        t = "Plata se face în termen de 75 de zile de la primirea facturii."
        self.assertEqual(sev(t, "payment.long_terms"), "high")

    def test_pay_when_paid(self):
        self.assertIn("payment.pay_when_paid", rules("Contractor is paid only after Client has been paid by its own customer."))

    def test_no_late_fee_and_due_date(self):
        r = rules("The fee is $2,000.")
        self.assertIn("payment.no_due_date", r)
        self.assertIn("payment.no_late_fee", r)

    def test_deposit_on_signing_counts(self):
        self.assertNotIn("payment.no_deposit", rules("Fee $100: 50% on signing, 50% on delivery, payable within 14 days."))

    def test_late_fee_present(self):
        self.assertNotIn("payment.no_late_fee", rules("Fee $100 payable within 14 days. Late payments accrue interest."))


class NonCompete(unittest.TestCase):
    def test_industry_wide(self):
        t = "Contractor shall not provide similar services to any company in the Client's industry for 24 months."
        self.assertEqual(sev(t, "noncompete.noncompete"), "high")

    def test_exclusivity(self):
        self.assertIn("noncompete.exclusivity", rules("Contractor will work exclusively for the Client during the term."))

    def test_exclusive_license_is_not_exclusivity(self):
        self.assertNotIn("noncompete.exclusivity", rules("Contractor grants Client an exclusive license to the logo."))

    def test_nonsolicit_low(self):
        self.assertEqual(sev("Contractor shall not solicit Client's employees for 6 months.", "noncompete.nonsolicit"), "low")

    def test_romanian(self):
        self.assertIn("noncompete.noncompete", rules("Clauză de neconcurență pe o perioadă de 2 ani."))


class Liability(unittest.TestCase):
    def test_unlimited(self):
        self.assertEqual(sev("Contractor's liability is unlimited.", "liability.unlimited"), "high")

    def test_cap_suppresses_no_cap(self):
        t = "Each party's liability shall not exceed the fees paid."
        self.assertNotIn("liability.no_cap", rules(t))

    def test_mutual_exclusion_not_flagged(self):
        t = "Neither party is liable for consequential damages. Liability shall not exceed the fees paid."
        self.assertNotIn("liability.consequential", rules(t))

    def test_liable_for_consequential(self):
        self.assertIn("liability.consequential", rules("Contractor shall be liable for lost profits of the Client."))

    def test_broad_indemnity_without_cap_is_high(self):
        self.assertEqual(sev("Contractor shall indemnify Client against any and all claims.", "liability.indemnity"), "high")


class Other(unittest.TestCase):
    def test_termination_mutual_is_fine(self):
        t = "Either party may terminate at any time for any reason. Client pays for all work performed."
        r = rules(t)
        self.assertNotIn("termination.convenience", r)
        self.assertNotIn("termination.no_kill_fee", r)

    def test_client_only_termination(self):
        self.assertIn("termination.convenience", rules("Client may terminate this Agreement at any time."))

    def test_warranty(self):
        self.assertIn("warranty.absolute", rules("Contractor warrants the work will be error-free."))


class Typography(unittest.TestCase):
    def test_curly_apostrophe_and_dash(self):
        self.assertIn("revisions.satisfaction", rules("Work must be done to the Client\u2019s satisfaction."))
        self.assertEqual(sev("Payment terms: Net\u201190. Fee $500.", "payment.long_terms"), "high")

    def test_comma_separated_noncompete(self):
        t = "Contractor shall not, directly or indirectly, engage in any business that competes with Company."
        self.assertIn("noncompete.noncompete", rules(t))


class FalsePositives(unittest.TestCase):
    def test_other_day_counts_not_payment(self):
        t = "Client shall pay each invoice within 14 days. Client must notify defects within 60 days after delivery."
        self.assertNotIn("payment.long_terms", rules(t))

    def test_client_indemnity_not_flagged(self):
        t = "Client agrees to indemnify Contractor against third-party claims. Contractor's liability is limited to fees paid."
        self.assertNotIn("liability.indemnity", rules(t))

    def test_mutual_indemnity_not_flagged(self):
        self.assertNotIn("liability.indemnity", rules("Each party shall indemnify the other against third-party claims."))

    def test_work_done_is_paid_counts_as_kill_fee(self):
        self.assertNotIn("termination.no_kill_fee", rules("Either party may cancel with 7 days' notice; work done is paid."))

    def test_unlimited_users_is_not_revisions(self):
        self.assertNotIn("revisions.unlimited", rules("The licence covers an unlimited number of users."))

    def test_balanced_contract_is_clean(self):
        with open(os.path.join(ROOT, "examples", "balanced_en.txt"), encoding="utf-8") as fh:
            self.assertEqual([f.rule for f in scan(fh.read())], [])


class NewRules(unittest.TestCase):
    def test_delay_penalty(self):
        self.assertIn("delivery.penalty", rules("If Contractor misses a deadline, Contractor shall pay liquidated damages of $500 per day."))

    def test_control(self):
        self.assertIn("classification.control", rules("Contractor will be available during Client's normal business hours."))

    def test_portfolio(self):
        t = "Contractor assigns all copyright in the deliverables to Client."
        self.assertIn("ip.no_portfolio", rules(t))
        self.assertNotIn("ip.no_portfolio", rules(t + " Contractor may show the work in a portfolio."))

    def test_romanian_cession_scope(self):
        self.assertIn("ip.ro_cession_scope", rules("Prestatorul cesionează toate drepturile de autor asupra operelor."))
        t = "Prestatorul cesionează drepturile de autor pe o durată de 5 ani, pe teritoriul României."
        self.assertNotIn("ip.ro_cession_scope", rules(t))

    def test_realistic_contract(self):
        with open(os.path.join(ROOT, "examples", "realistic_en.txt"), encoding="utf-8") as fh:
            r = rules(fh.read())
        for expected in ("revisions.unlimited", "payment.long_terms", "ip.before_payment", "noncompete.noncompete",
                         "liability.indemnity", "delivery.penalty", "classification.control"):
            self.assertIn(expected, r)


class Language(unittest.TestCase):
    def test_detect(self):
        from redflag.text import detect_language
        self.assertEqual(detect_language("Prestatorul va livra serviciile către Beneficiar."), "ro")
        self.assertEqual(detect_language("The Contractor shall deliver the services."), "en")

    def test_auto_language_in_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            main([os.path.join(ROOT, "examples", "bad_ro.txt"), "--format", "json"])
        self.assertIn("Revizuiri nelimitate", buf.getvalue())


class Text(unittest.TestCase):
    def test_fold_preserves_length(self):
        s = "Plată înțeleasă ȘI Țară"
        self.assertEqual(len(fold(s)), len(s))
        self.assertEqual(fold(s), "plata inteleasa si tara")

    def test_clause_split_numbered(self):
        cl = split_clauses("1. First clause\ncontinues\n2. Second clause\n\nThird")
        self.assertEqual([(c.line, c.text) for c in cl], [(1, "1. First clause continues"), (3, "2. Second clause"), (5, "Third")])

    def test_docx_loading(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Contractor shall provide</w:t></w:r><w:r><w:t xml:space="preserve"> unlimited revisions.</w:t></w:r></w:p>'
               "</w:body></w:document>")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.docx")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("word/document.xml", xml)
            self.assertIn("revisions.unlimited", rules(load(path)))


class Examples(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(ROOT, "examples", name), encoding="utf-8") as fh:
            return fh.read()

    def test_bad_english_covers_all_five_headline_flags(self):
        r = rules(self.read("bad_en.txt"))
        for expected in ("revisions.unlimited", "ip.broad_scope", "payment.long_terms", "noncompete.noncompete", "liability.unlimited"):
            self.assertIn(expected, r)

    def test_bad_romanian(self):
        r = rules(self.read("bad_ro.txt"))
        for expected in ("revisions.unlimited", "ip.broad_scope", "payment.long_terms", "noncompete.noncompete", "liability.unlimited"):
            self.assertIn(expected, r)

    def test_fair_contract_is_clean(self):
        self.assertEqual([f.rule for f in scan(self.read("fair_en.txt"))], [])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(list(args))
        return code, buf.getvalue()

    def test_json_and_fail_on(self):
        path = os.path.join(ROOT, "examples", "bad_en.txt")
        code, out = self.run_cli(path, "--format", "json", "--fail-on", "high")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertGreater(data["summary"]["high"], 0)
        self.assertTrue(all(f["quote"] or f["category"] for f in data["findings"]))

    def test_clean_exit_zero(self):
        code, _ = self.run_cli(os.path.join(ROOT, "examples", "fair_en.txt"), "--fail-on", "low")
        self.assertEqual(code, 0)

    def test_min_severity(self):
        _, out = self.run_cli(os.path.join(ROOT, "examples", "bad_en.txt"), "--format", "json", "--min-severity", "high")
        self.assertEqual({f["severity"] for f in json.loads(out)["findings"]}, {"high"})

    def test_binary_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.dat")
            with open(path, "wb") as fh:
                fh.write(bytes(range(256)) * 20)
            self.assertEqual(self.run_cli(path)[0], 2)

    def test_missing_file(self):
        self.assertEqual(self.run_cli("/no/such/file.txt")[0], 2)


if __name__ == "__main__":
    unittest.main()
