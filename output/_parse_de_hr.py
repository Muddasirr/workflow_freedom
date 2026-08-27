#!/usr/bin/env python3
"""Parse published German HR emails, SMTP-verify, write send CSV."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SKIP_LOCAL,
    already_sent,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

RAW = """
careers@sap.com
contact@siemens.com
bewerber.service@bmw.de
recruiting@volkswagen.de
careers@mercedes-benz.com
recruiting@porsche.de
karriere@audi.de
jobs@basf.com
careers@allianz.com
jobs@telekom.de
jobs@dhl.com
recruiting@bayer.com
kontakt@bosch.de
karriere@continental.com
karriere@dlh.de
careers@adidas-group.com
careers@puma.com
jobs@henkel.com
jobs@eon.com
karriere@fresenius.com
recruiting@merckgroup.com
info@heidelbergmaterials.com
career@beiersdorf.com
careers@deliveryhero.com
jobs@zalando.de
jobs@deutschepost.de
karriere@deutschebahn.com
careers@infineon.com
karriere@evonik.com
karriere@thyssenkrupp.com
recruiting@covestro.com
info@kiongroup.com
corporate.communications@brenntag.de
info@sartorius.com
careers@symrise.com
karriere@vonovia.de
info@mtu.de
recruiting@puma.com
career@zeiss.com
karriere@knorr-bremse.com
contact@siemens-energy.com
careers@deutsche-boerse.com
karriere@commerzbank.com
careers.db@db.com
careers@pumaenergy.com
recruiting@traton.com
contact@daimlertruck.com
careers@ceconomy.de
karriere@metro.de
careers@kiongroup.com
info@evotec.com
careers@biontech.de
careers@qiagen.com
karriere@gea.com
karriere@lanxess.com
info@wacker.com
karriere@k-plus-s.com
careers@nordex-online.com
karriere@sma.de
karriere@encavis.com
careers@uniper.energy
kontakt@enbw.com
karriere@fraport.de
careers@hlag.com
karriere@hhla.de
careers@tui.com
karriere@fielmann.com
jobs@prosiebensat1.com
karriere@bertelsmann.de
careers@axelspringer.de
karriere@eventim.de
careers@nemetschek.com
careers@softwareag.com
careers@teamviewer.com
jobs@united-internet.de
jobs@11.de
karriere@cancom.de
karriere@bechtle.com
karriere@cgm.com
karriere@rational-online.com
karriere@durr.com
karriere@jungheinrich.de
karriere@salzgitter-ag.de
karriere@kloeckner.com
karriere@krones.com
info@duerrdental.com
careers@gerresheimer.com
careers@morphosys.com
karriere@stroeer.de
karriere@hornbach.com
careers@sixt.com
careers@vitesco.com
karriere@normagroup.com
karriere@deutz.com
karriere@wackerneuson.com
careers@sglcarbon.com
karriere@hella.com
karriere@elringklinger.com
karriere@indus.de
jobs@sma.de
"""

NAMES = {
    "sap.com": "SAP",
    "siemens.com": "Siemens",
    "bmw.de": "BMW",
    "volkswagen.de": "Volkswagen",
    "mercedes-benz.com": "Mercedes-Benz",
    "porsche.de": "Porsche",
    "audi.de": "Audi",
    "basf.com": "BASF",
    "allianz.com": "Allianz",
    "telekom.de": "Deutsche Telekom",
    "dhl.com": "DHL",
    "bayer.com": "Bayer",
    "bosch.de": "Bosch",
    "continental.com": "Continental",
    "dlh.de": "Lufthansa",
    "adidas-group.com": "adidas",
    "puma.com": "PUMA",
    "henkel.com": "Henkel",
    "eon.com": "E.ON",
    "fresenius.com": "Fresenius",
    "merckgroup.com": "Merck",
    "heidelbergmaterials.com": "Heidelberg Materials",
    "beiersdorf.com": "Beiersdorf",
    "deliveryhero.com": "Delivery Hero",
    "zalando.de": "Zalando",
    "deutschepost.de": "Deutsche Post",
    "deutschebahn.com": "Deutsche Bahn",
    "infineon.com": "Infineon",
    "evonik.com": "Evonik",
    "thyssenkrupp.com": "thyssenkrupp",
    "covestro.com": "Covestro",
    "kiongroup.com": "KION Group",
    "brenntag.de": "Brenntag",
    "sartorius.com": "Sartorius",
    "symrise.com": "Symrise",
    "vonovia.de": "Vonovia",
    "mtu.de": "MTU Aero Engines",
    "zeiss.com": "ZEISS",
    "knorr-bremse.com": "Knorr-Bremse",
    "siemens-energy.com": "Siemens Energy",
    "deutsche-boerse.com": "Deutsche Börse",
    "commerzbank.com": "Commerzbank",
    "db.com": "Deutsche Bank",
    "pumaenergy.com": "Puma Energy",
    "traton.com": "TRATON",
    "daimlertruck.com": "Daimler Truck",
    "ceconomy.de": "Ceconomy",
    "metro.de": "METRO",
    "evotec.com": "Evotec",
    "biontech.de": "BioNTech",
    "qiagen.com": "QIAGEN",
    "gea.com": "GEA",
    "lanxess.com": "LANXESS",
    "wacker.com": "Wacker",
    "k-plus-s.com": "K+S",
    "nordex-online.com": "Nordex",
    "sma.de": "SMA",
    "encavis.com": "Encavis",
    "uniper.energy": "Uniper",
    "enbw.com": "EnBW",
    "fraport.de": "Fraport",
    "hlag.com": "Hapag-Lloyd",
    "hhla.de": "HHLA",
    "tui.com": "TUI",
    "fielmann.com": "Fielmann",
    "prosiebensat1.com": "ProSiebenSat.1",
    "bertelsmann.de": "Bertelsmann",
    "axelspringer.de": "Axel Springer",
    "eventim.de": "EVENTIM",
    "nemetschek.com": "Nemetschek",
    "softwareag.com": "Software AG",
    "teamviewer.com": "TeamViewer",
    "united-internet.de": "United Internet",
    "11.de": "1&1",
    "cancom.de": "CANCOM",
    "bechtle.com": "Bechtle",
    "cgm.com": "CompuGroup Medical",
    "rational-online.com": "RATIONAL",
    "durr.com": "Dürr",
    "jungheinrich.de": "Jungheinrich",
    "salzgitter-ag.de": "Salzgitter",
    "kloeckner.com": "Klöckner",
    "krones.com": "Krones",
    "duerrdental.com": "Dürr Dental",
    "gerresheimer.com": "Gerresheimer",
    "morphosys.com": "MorphoSys",
    "stroeer.de": "Ströer",
    "hornbach.com": "HORNBACH",
    "sixt.com": "Sixt",
    "vitesco.com": "Vitesco",
    "normagroup.com": "NORMA Group",
    "deutz.com": "DEUTZ",
    "wackerneuson.com": "Wacker Neuson",
    "sglcarbon.com": "SGL Carbon",
    "hella.com": "HELLA",
    "elringklinger.com": "ElringKlinger",
    "indus.de": "INDUS",
}

HIRING_RANK = (
    "karriere",
    "careers",
    "career",
    "recruiting",
    "jobs",
    "job",
    "bewerber.service",
    "bewerber",
    "careers.db",
    "kontakt",
    "contact",
    "info",
)


def rank(local: str) -> int:
    local = local.lower()
    try:
        return HIRING_RANK.index(local)
    except ValueError:
        return 50


def company_for(domain: str) -> str:
    return NAMES.get(domain, domain.split(".")[0].replace("-", " ").title())


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()

    best: dict[str, tuple[int, str, str]] = {}
    skipped: list[tuple[str, str]] = []

    for raw in RAW.strip().splitlines():
        email = raw.strip().lower()
        if "@" not in email:
            continue
        local, _, domain = email.partition("@")
        company = company_for(domain)
        company_key = company.lower()
        if local in SKIP_LOCAL or "communication" in local:
            skipped.append((email, "junk local"))
            continue
        if domain in BLOCKED_DOMAINS:
            skipped.append((email, "blocked domain"))
            continue
        if any(b == company_key or b in company_key for b in BLOCKED_COMPANIES):
            skipped.append((email, "blocked company"))
            continue
        if email in sent_e or email in bounced:
            skipped.append((email, "already sent/bounced"))
            continue
        if company_key in sent_c:
            skipped.append((email, "already sent company"))
            continue
        if domain in sent_d:
            skipped.append((email, "already sent domain"))
            continue
        item = (rank(local), email, company)
        prev = best.get(domain)
        if prev is None or item[0] < prev[0]:
            best[domain] = item

    rows = []
    for domain, (_r, email, company) in sorted(best.items(), key=lambda x: x[1][2].lower()):
        rows.append(
            {
                "Company": company,
                "Region": "Germany",
                "City": "",
                "HR / Recruiter Email": email,
                "Email Source": "known company contact",
                "Other Emails": "",
                "Domain": domain,
                "Careers / Apply URL": "",
                "Sample Role": "",
                "Location Clause": "",
                "Letter": "",
                "SMTP Verification": "",
            }
        )

    print(f"unique new to probe: {len(rows)}  skipped {len(skipped)}", flush=True)
    ready = []
    for r in rows:
        email = r["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        r["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} {email:48} {r['Company'][:22]:22} {detail[:70]}", flush=True)
        if ok:
            ready.append(r)

    out = ROOT / "output" / "emails_de_hr_2026-08-19.csv"
    fields = list(ready[0].keys()) if ready else [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Other Emails", "Domain", "Careers / Apply URL", "Sample Role",
        "Location Clause", "Letter", "SMTP Verification",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {out}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)


if __name__ == "__main__":
    main()
