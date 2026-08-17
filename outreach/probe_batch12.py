#!/usr/bin/env python3
"""Probe a fresh company list for strict-valid hiring inboxes."""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.directory import COMPANY_DIRECTORY  # noqa: E402
from smtp_verify import CACHE, _load_csv_map, bounced_emails, mx_hosts, verify_mailbox  # noqa: E402

NEW = [
    ("Personio", "personio.com", "Europe", "Munich / remote"),
    ("Spendesk", "spendesk.com", "Europe", "Paris / remote"),
    ("Payhawk", "payhawk.com", "Europe", "Sofia / remote"),
    ("Soldo", "soldo.com", "Europe", "London / remote"),
    ("Moss", "getmoss.com", "Europe", "Berlin / remote"),
    ("Mambu", "mambu.com", "Europe", "Amsterdam / remote"),
    ("Solaris", "solarisgroup.com", "Europe", "Berlin / remote"),
    ("Vivid Money", "vivid.money", "Europe", "Berlin / remote"),
    ("Trade Republic", "traderepublic.com", "Europe", "Berlin / remote"),
    ("Scalable Capital", "scalable.capital", "Europe", "Munich / remote"),
    ("Bux", "getbux.com", "Europe", "Amsterdam / remote"),
    ("Kraken", "kraken.com", "Remote", "Worldwide remote"),
    ("Plum", "withplum.com", "Europe", "London / remote"),
    ("Moneybox", "moneyboxapp.com", "Europe", "London / remote"),
    ("Freetrade", "freetrade.io", "Europe", "London / remote"),
    ("eToro", "etoro.com", "Europe", "London / remote"),
    ("Octopus Energy", "octopus.energy", "Europe", "London / remote"),
    ("Gousto", "gousto.co.uk", "Europe", "London / remote"),
    ("Wolt", "wolt.com", "Europe", "Helsinki / remote"),
    ("Too Good To Go", "toogoodtogo.com", "Europe", "Copenhagen / remote"),
    ("Flink", "goflink.com", "Europe", "Berlin / remote"),
    ("Getir", "getir.com", "Europe", "London / remote"),
    ("Rohlik", "rohlik.cz", "Europe", "Prague / remote"),
    ("Calendly", "calendly.com", "Remote", "Worldwide remote"),
    ("SavvyCal", "savvycal.com", "Remote", "Worldwide remote"),
    ("Amie", "amie.so", "Europe", "Berlin / remote"),
    ("Morgen", "morgen.so", "Europe", "Berlin / remote"),
    ("Motion", "usemotion.com", "Remote", "Worldwide remote"),
    ("Reclaim", "reclaim.ai", "Remote", "Worldwide remote"),
    ("Clockwise", "clockwise.so", "Remote", "Worldwide remote"),
    ("Sanity", "sanity.io", "Remote", "Worldwide remote"),
    ("Payload", "payloadcms.com", "Remote", "Worldwide remote"),
    ("Kit", "kit.com", "Remote", "Worldwide remote"),
    ("Buttondown", "buttondown.com", "Remote", "Worldwide remote"),
    ("MailerLite", "mailerlite.com", "Europe", "Vilnius / remote"),
    ("Omnisend", "omnisend.com", "Europe", "Vilnius / remote"),
    ("Brevo", "brevo.com", "Europe", "Paris / remote"),
    ("Statsig", "statsig.com", "Remote", "Worldwide remote"),
    ("GrowthBook", "growthbook.io", "Remote", "Worldwide remote"),
    ("ConfigCat", "configcat.com", "Europe", "Budapest / remote"),
    ("Unleash", "getunleash.io", "Europe", "Oslo / remote"),
    ("Flagsmith", "flagsmith.com", "Remote", "Worldwide remote"),
    ("Svix", "svix.com", "Remote", "Worldwide remote"),
    ("Hookdeck", "hookdeck.com", "Remote", "Worldwide remote"),
    ("Knock", "knock.app", "Remote", "Worldwide remote"),
    ("Courier", "courier.com", "Remote", "Worldwide remote"),
    ("Polar", "polar.sh", "Remote", "Worldwide remote"),
    ("Lemon Squeezy", "lemonsqueezy.com", "Remote", "Worldwide remote"),
    ("Gumroad", "gumroad.com", "Remote", "Worldwide remote"),
    ("ChartMogul", "chartmogul.com", "Europe", "Berlin / remote"),
    ("Baremetrics", "baremetrics.com", "Remote", "Worldwide remote"),
    ("Fathom Analytics", "usefathom.com", "Remote", "Worldwide remote"),
    ("Simple Analytics", "simpleanalytics.com", "Europe", "Amsterdam / remote"),
    ("LogRocket", "logrocket.com", "Remote", "Worldwide remote"),
    ("Grafana", "grafana.com", "Europe", "Stockholm / remote"),
    ("Better Stack", "betterstack.com", "Europe", "Prague / remote"),
    ("Checkly", "checklyhq.com", "Europe", "Amsterdam / remote"),
    ("Smartlook", "smartlook.com", "Europe", "Brno / remote"),
    ("AB Tasty", "abtasty.com", "Europe", "Paris / remote"),
    ("Nosto", "nosto.com", "Europe", "Helsinki / remote"),
    ("Pinecone", "pinecone.io", "Remote", "Worldwide remote"),
    ("Upstash", "upstash.com", "Remote", "Worldwide remote"),
    ("ClickHouse", "clickhouse.com", "Remote", "Worldwide remote"),
    ("Prefect", "prefect.io", "Remote", "Worldwide remote"),
    ("Dagster", "dagster.io", "Remote", "Worldwide remote"),
    ("Make", "make.com", "Europe", "Prague / remote"),
    ("Pipedream", "pipedream.com", "Remote", "Worldwide remote"),
    ("Windmill", "windmill.dev", "Europe", "Paris / remote"),
    ("Kestra", "kestra.io", "Europe", "Paris / remote"),
    ("Restate", "restate.dev", "Europe", "Berlin / remote"),
    ("Tamara", "tamara.co", "KSA", "Riyadh / remote"),
    ("Postpay", "postpay.io", "UAE", "Dubai / remote"),
    ("Paymob", "paymob.com", "Egypt", "Cairo / remote"),
    ("PayTabs", "paytabs.com", "KSA", "Riyadh / remote"),
    ("Tap Payments", "tap.company", "KSA", "Riyadh / remote"),
    ("Moyasar", "moyasar.com", "KSA", "Riyadh / remote"),
    ("Telr", "telr.com", "UAE", "Dubai / remote"),
    ("Namshi", "namshi.com", "UAE", "Dubai / remote"),
    ("Mumzworld", "mumzworld.com", "UAE", "Dubai / remote"),
    ("Jumia", "jumia.com", "Egypt", "Cairo / remote"),
    ("Breadfast", "breadfast.com", "Egypt", "Cairo / remote"),
    ("Elmenus", "elmenus.com", "Egypt", "Cairo / remote"),
    ("Snoonu", "snoonu.com", "Qatar", "Doha / remote"),
    ("Tarabut", "tarabut.com", "Bahrain", "Manama / remote"),
    ("Cafu", "cafu.com", "UAE", "Dubai / remote"),
    ("Lean Technologies", "leantech.me", "KSA", "Riyadh / remote"),
    ("Ninja Van", "ninjavan.co", "Singapore", "Singapore / remote"),
    ("Atome", "atome.sg", "Singapore", "Singapore / remote"),
    ("ShopBack", "shopback.com", "Singapore", "Singapore / remote"),
    ("Grab", "grab.com", "Singapore", "Singapore / remote"),
    ("Garena", "garena.com", "Singapore", "Singapore / remote"),
    ("Heetch", "heetch.com", "Europe", "Paris / remote"),
    ("Omio", "omio.com", "Europe", "Berlin / remote"),
    ("Contentsquare", "contentsquare.com", "Europe", "Paris / remote"),
    ("Fillout", "fillout.com", "Remote", "Worldwide remote"),
    ("Jotform", "jotform.com", "Remote", "Worldwide remote"),
    ("Typesense", "typesense.org", "Remote", "Worldwide remote"),
    ("Xata", "xata.io", "Remote", "Worldwide remote"),
    ("Turso", "turso.tech", "Remote", "Worldwide remote"),
    ("MotherDuck", "motherduck.com", "Remote", "Worldwide remote"),
    ("Hatchet", "hatchet.run", "Remote", "Worldwide remote"),
]

TRY = ("careers", "hr", "recruiting", "jobs", "people", "hiring", "recruitment")
GOOGLEISH = ("google", "gmail", "aspmx", "googlemail", "larksuite", "smtp.goog")
TARGET = {
    "Karachi",
    "Pakistan",
    "MENA",
    "UAE",
    "KSA",
    "Qatar",
    "Bahrain",
    "Kuwait",
    "Oman",
    "Egypt",
    "Jordan",
    "Lebanon",
    "Singapore",
    "Malaysia",
    "Europe",
}
DONE = {
    "invalid",
    "reject",
    "bounce",
    "no-mx",
    "catch-all",
    "accept-then-unknown",
    "probe-blocked",
    "strict-valid",
}
DEAD = {"catch-all", "no-mx", "probe-blocked"}


def main() -> int:
    existing_domains = {d.lower() for _, d, *_ in COMPANY_DIRECTORY}
    sent_e: set[str] = set()
    sent_c: set[str] = set()
    sent_d: set[str] = set()
    with (ROOT / "outreach" / "sent_log.csv").open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "sent":
                continue
            email = (row.get("email") or "").lower()
            company = (row.get("company") or "").strip().lower()
            sent_e.add(email)
            if company and company != "test":
                sent_c.add(company)
            if "@" in email:
                sent_d.add(email.split("@", 1)[1])

    cache = _load_csv_map(CACHE)
    bounces = bounced_emails()
    dead_domains = {e.split("@", 1)[1] for e, st in cache.items() if "@" in e and st in DEAD}
    probed_locals: dict[str, set[str]] = defaultdict(set)
    for email in cache:
        if "@" in email:
            local, domain = email.split("@", 1)
            probed_locals[domain].add(local)

    seen: set[str] = set()
    fresh: list[tuple[str, str, str, str, list[str]]] = []
    for name, domain, region, city in NEW:
        domain = domain.lower().strip()
        if not domain or domain in existing_domains or domain in sent_d or domain in dead_domains:
            continue
        if domain in seen or name.strip().lower() in sent_c:
            continue
        seen.add(domain)
        missing = []
        for loc in TRY:
            email = f"{loc}@{domain}"
            if loc in probed_locals[domain] or email in sent_e or email in bounces or cache.get(email) in DONE:
                continue
            missing.append(loc)
        if missing:
            fresh.append((name, domain, region, city, missing[:3]))

    print(f"fresh companies after filters: {len(fresh)}", flush=True)

    google = []
    other = 0
    for name, domain, region, city, locs in fresh:
        try:
            hosts = mx_hosts(domain)
        except Exception:
            hosts = []
        mxblob = " ".join(hosts).lower()
        if any(token in mxblob for token in GOOGLEISH):
            pri = -1 if region in {"Karachi", "Pakistan"} else (0 if region in TARGET else 1)
            google.append((pri, region, name, domain, city, locs))
        else:
            other += 1
    google.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    print(f"google/lark: {len(google)}  other mx skipped: {other}", flush=True)
    print("regions", Counter(item[1] for item in google), flush=True)
    for item in google[:18]:
        print(f"  plan {item[3]:28} try={item[5]}  {item[2]} [{item[1]}]", flush=True)

    found: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    for i, (_pri, region, name, domain, city, locs) in enumerate(google, 1):
        if len(found) >= 16:
            print("hit 16, stop", flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(google)}] probe {email} ({name} / {region})", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.2)
            if ok:
                stats["ok"] += 1
                print(f"  OK  {email}  {detail[:110]}", flush=True)
                found.append(
                    {
                        "Company": name,
                        "Region": region,
                        "City": city,
                        "HR / Recruiter Email": email,
                        "Email Source": "guessed pattern (verify before sending)",
                        "Other Emails": "",
                        "Domain": domain,
                        "Careers / Apply URL": f"https://{domain}/careers",
                        "Sample Role": "",
                        "SMTP Verification": detail[:400],
                    }
                )
                break
            tag = "catch-all" if "catch-all" in detail.lower() else "fail"
            stats[tag] += 1
            print(f"  NO  {email}  {detail[:130]}", flush=True)
            if "catch-all" in detail.lower():
                break

    out = ROOT / "output" / "emails_shortlist_batch12_2026-08-13.csv"
    fields = [
        "Company",
        "Region",
        "City",
        "HR / Recruiter Email",
        "Email Source",
        "Other Emails",
        "Domain",
        "Careers / Apply URL",
        "Sample Role",
        "SMTP Verification",
    ]
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(found)
    print("\nSTATS", dict(stats), flush=True)
    print("WROTE", out, "rows", len(found), flush=True)
    for row in found:
        print(f"  {row['HR / Recruiter Email']:40} {row['Company']} [{row['Region']}]", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
