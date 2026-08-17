#!/usr/bin/env python3
"""Probe batch28 — real unsent PK/MENA/AU/Europe/remote domains."""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from smtp_verify import CACHE, _load_csv_map, bounced_emails, mx_hosts, verify_mailbox  # noqa: E402

NEW = [('Teikametrics Soft', 'teikametrics.com', 'Remote', 'Worldwide remote'), ('ShipBob Soft', 'shipbob.com', 'Remote', 'Worldwide remote'), ('Faire Soft', 'faire.com', 'Remote', 'Worldwide remote'), ('Flexport Soft', 'flexport.com', 'Remote', 'Worldwide remote'), ('Brex Soft', 'brex.com', 'Remote', 'Worldwide remote'), ('Ramp Soft', 'ramp.com', 'Remote', 'Worldwide remote'), ('Mercury Soft', 'mercury.com', 'Remote', 'Worldwide remote'), ('Block Soft', 'block.xyz', 'Remote', 'Worldwide remote'), ('Affirm Soft', 'affirm.com', 'Remote', 'Worldwide remote'), ('Klarna Soft', 'klarna.com', 'Europe', 'Stockholm / remote'), ('Starling Soft', 'starlingbank.com', 'Europe', 'London / remote'), ('GoCardless Soft', 'gocardless.com', 'Europe', 'London / remote'), ('Graphcore Soft', 'graphcore.ai', 'Europe', 'Bristol / remote'), ('Photoroom Soft', 'photoroom.com', 'Europe', 'Paris / remote'), ('Crew Soft', 'crew.work', 'Europe', 'Paris / remote'), ('Pigment Soft', 'pigment.com', 'Europe', 'Paris / remote'), ('Sorare Soft', 'sorare.com', 'Europe', 'Paris / remote'), ('Spendesk Soft', 'spendesk.com', 'Europe', 'Paris / remote'), ('Contentful Soft', 'contentful.com', 'Europe', 'Berlin / remote'), ('SumUp Soft', 'sumup.com', 'Europe', 'London / remote'), ('Gravitee Soft', 'gravitee.io', 'Europe', 'Lille / remote'), ('Picnic Soft', 'picnic.app', 'Europe', 'Amsterdam / remote'), ('Booking Soft', 'booking.com', 'Europe', 'Amsterdam / remote'), ('King Soft', 'king.com', 'Europe', 'Stockholm / remote'), ('Culture Amp Soft', 'cultureamp.com', 'Australia', 'Melbourne / remote'), ('Airwallex Soft', 'airwallex.com', 'Australia', 'Melbourne / remote'), ('Tyro Soft', 'tyro.com', 'Australia', 'Sydney / remote'), ('Prospa Soft', 'prospa.com', 'Australia', 'Sydney / remote'), ('Brighte Soft', 'brighte.com.au', 'Australia', 'Sydney / remote'), ('Carsales Soft', 'carsales.com.au', 'Australia', 'Melbourne / remote'), ('REA Soft', 'rea-group.com', 'Australia', 'Melbourne / remote'), ('Seek Soft', 'seek.com.au', 'Australia', 'Melbourne / remote'), ('MYOB Soft', 'myob.com', 'Australia', 'Melbourne / remote'), ('Nitro Soft', 'gonitro.com', 'Australia', 'Sydney / remote'), ('Nearmap Soft', 'nearmap.com', 'Australia', 'Sydney / remote'), ('Zid Soft', 'zid.sa', 'KSA', 'Riyadh / remote'), ('Jahez Soft', 'jahez.net', 'KSA', 'Riyadh / remote'), ('Bayut Soft', 'bayut.com', 'UAE', 'Dubai / remote'), ('Instabug Soft', 'instabug.com', 'Egypt', 'Cairo / remote'), ('Fawry Soft', 'fawry.com', 'Egypt', 'Cairo / remote'), ('PakWheels Soft', 'pakwheels.com', 'Pakistan', 'Karachi'), ('Dawaai Soft', 'dawaai.com', 'Karachi', 'Karachi'), ('Sofizar Soft', 'sofizar.com', 'Pakistan', 'Lahore'), ('Logicose Soft', 'logicose.com', 'Pakistan', 'Lahore'), ('WebHR Soft', 'webhr.co', 'Pakistan', 'Lahore / remote'), ('Shippo Soft', 'shippo.com', 'Remote', 'Worldwide remote'), ('EasyPost Soft', 'easypost.com', 'Remote', 'Worldwide remote'), ('Veeva Soft', 'veeva.com', 'Remote', 'Worldwide remote'), ('ServiceTitan Soft', 'servicetitan.com', 'Remote', 'Worldwide remote'), ('Procore Soft', 'procore.com', 'Remote', 'Worldwide remote'), ('Toast Soft', 'toasttab.com', 'Remote', 'Worldwide remote'), ('Olo Soft', 'olo.com', 'Remote', 'Worldwide remote'), ('ChowNow Soft', 'chownow.com', 'Remote', 'Worldwide remote'), ('DoorDash Soft', 'doordash.com', 'Remote', 'Worldwide remote'), ('Lyft Soft', 'lyft.com', 'Remote', 'Worldwide remote'), ('Instacart Soft', 'instacart.com', 'Remote', 'Worldwide remote'), ('Gopuff Soft', 'gopuff.com', 'Remote', 'Worldwide remote'), ('Nuro Soft', 'nuro.ai', 'Remote', 'Worldwide remote'), ('Cruise Soft', 'getcruise.com', 'Remote', 'Worldwide remote'), ('Waymo Soft', 'waymo.com', 'Remote', 'Worldwide remote'), ('Rivian Soft', 'rivian.com', 'Remote', 'Worldwide remote'), ('Lucid Motors Soft', 'lucidmotors.com', 'Remote', 'Worldwide remote'), ('Samsara Soft', 'samsara.com', 'Remote', 'Worldwide remote'), ('Nylas Soft', 'nylas.com', 'Remote', 'Worldwide remote'), ('Atomic Soft', 'atomic.finance', 'Remote', 'Worldwide remote'), ('Modern Treasury Soft', 'moderntreasury.com', 'Remote', 'Worldwide remote'), ('Coinbase Soft', 'coinbase.com', 'Remote', 'Worldwide remote'), ('Gemini Soft', 'gemini.com', 'Remote', 'Worldwide remote'), ('BitGo Soft', 'bitgo.com', 'Remote', 'Worldwide remote'), ('Fireblocks Soft', 'fireblocks.com', 'Remote', 'Worldwide remote'), ('Chainalysis Soft', 'chainalysis.com', 'Remote', 'Worldwide remote'), ('Elliptic Soft', 'elliptic.co', 'Europe', 'London / remote'), ('Alchemy Soft', 'alchemy.com', 'Remote', 'Worldwide remote'), ('Infura Soft', 'infura.io', 'Remote', 'Worldwide remote'), ('QuickNode Soft', 'quicknode.com', 'Remote', 'Worldwide remote'), ('Moralis Soft', 'moralis.io', 'Remote', 'Worldwide remote'), ('Thirdweb Soft', 'thirdweb.com', 'Remote', 'Worldwide remote'), ('OpenSea Soft', 'opensea.io', 'Remote', 'Worldwide remote'), ('Magic Eden Soft', 'magiceden.io', 'Remote', 'Worldwide remote'), ('Dapper Soft', 'dapperlabs.com', 'Remote', 'Worldwide remote'), ('Figment Soft', 'figment.io', 'Remote', 'Worldwide remote'), ('Anchorage Soft', 'anchoragedigital.com', 'Remote', 'Worldwide remote'), ('Ripio Soft', 'ripio.com', 'Remote', 'Worldwide remote'), ('Bitso Soft', 'bitso.com', 'Remote', 'Worldwide remote'), ('Mercado Soft', 'mercadolibre.com', 'Remote', 'Worldwide remote'), ('Rappi Soft', 'rappi.com', 'Remote', 'Worldwide remote'), ('Globant Soft', 'globant.com', 'Remote', 'Worldwide remote'), ('Endava Soft', 'endava.com', 'Europe', 'London / remote'), ('EPAM Soft', 'epam.com', 'Remote', 'Worldwide remote'), ('SoftServe Soft', 'softserveinc.com', 'Europe', 'Lviv / remote'), ('Grid Dynamics Soft', 'griddynamics.com', 'Remote', 'Worldwide remote'), ('Luxoft Soft', 'luxoft.com', 'Europe', 'Zug / remote'), ('DataArt Soft', 'dataart.com', 'Europe', 'New York / remote'), ('Intellias Soft', 'intellias.com', 'Europe', 'Lviv / remote'), ('Ciklum Soft', 'ciklum.com', 'Europe', 'London / remote'), ('ELEKS Soft', 'eleks.com', 'Europe', 'Lviv / remote'), ('N-iX Soft', 'n-ix.com', 'Europe', 'Lviv / remote'), ('Sigma Soft', 'sigma.software', 'Europe', 'Kyiv / remote'), ('Andersen Soft', 'andersenlab.com', 'Europe', 'Warsaw / remote'), ('Codementor Soft', 'codementor.io', 'Remote', 'Worldwide remote'), ('Gun.io Soft', 'gun.io', 'Remote', 'Worldwide remote'), ('Arc.dev Soft', 'arc.dev', 'Remote', 'Worldwide remote'), ('Thoughtworks Soft', 'thoughtworks.com', 'Remote', 'Worldwide remote'), ('Slalom Soft', 'slalom.com', 'Remote', 'Worldwide remote'), ('Capgemini Soft', 'capgemini.com', 'Europe', 'Paris / remote'), ('Yalantis Soft', 'yalantis.com', 'Europe', 'Dnipro / remote'), ('Celonis Soft', 'celonis.com', 'Europe', 'Munich / remote'), ('Sanity Soft', 'sanity.io', 'Europe', 'Oslo / remote'), ('Prismic Soft', 'prismic.io', 'Europe', 'Paris / remote'), ('Storyblok Soft', 'storyblok.com', 'Europe', 'Linz / remote'), ('Strapi Soft', 'strapi.io', 'Europe', 'Paris / remote'), ('Directus Soft', 'directus.io', 'Remote', 'Worldwide remote'), ('Payload Soft', 'payloadcms.com', 'Remote', 'Worldwide remote'), ('CircleCI Soft', 'circleci.com', 'Remote', 'Worldwide remote'), ('Harness Soft', 'harness.io', 'Remote', 'Worldwide remote'), ('Spacelift Soft', 'spacelift.io', 'Remote', 'Worldwide remote'), ('Teleport Soft', 'goteleport.com', 'Remote', 'Worldwide remote'), ('Tailscale Soft', 'tailscale.com', 'Remote', 'Worldwide remote'), ('1Password Soft', '1password.com', 'Remote', 'Worldwide remote'), ('Bitwarden Soft', 'bitwarden.com', 'Remote', 'Worldwide remote'), ('Proton Soft', 'proton.me', 'Europe', 'Geneva / remote'), ('Fastmail Soft', 'fastmail.com', 'Australia', 'Melbourne / remote'), ('Superhuman Soft', 'superhuman.com', 'Remote', 'Worldwide remote'), ('Help Scout Soft', 'helpscout.com', 'Remote', 'Worldwide remote'), ('Crisp Soft', 'crisp.chat', 'Europe', 'Nantes / remote'), ('LiveChat Soft', 'livechat.com', 'Europe', 'Wroclaw / remote'), ('Chatwoot Soft', 'chatwoot.com', 'Remote', 'Worldwide remote'), ('Mattermost Soft', 'mattermost.com', 'Remote', 'Worldwide remote'), ('Rocket Chat Soft', 'rocket.chat', 'Remote', 'Worldwide remote'), ('Element Soft', 'element.io', 'Europe', 'London / remote'), ('JetBrains Soft', 'jetbrains.com', 'Europe', 'Prague / remote'), ('Unity Soft', 'unity.com', 'Remote', 'Worldwide remote'), ('Discord Soft', 'discord.com', 'Remote', 'Worldwide remote'), ('Docker Soft', 'docker.com', 'Remote', 'Worldwide remote'), ('Snowflake Soft', 'snowflake.com', 'Remote', 'Worldwide remote'), ('Databricks Soft', 'databricks.com', 'Remote', 'Worldwide remote'), ('Shopify Soft', 'shopify.com', 'Remote', 'Worldwide remote'), ('BigCommerce Soft', 'bigcommerce.com', 'Remote', 'Worldwide remote'), ('Twilio Soft', 'twilio.com', 'Remote', 'Worldwide remote'), ('dbt Labs Soft', 'getdbt.com', 'Remote', 'Worldwide remote'), ('Buildkite Soft', 'buildkite.com', 'Australia', 'Melbourne / remote'), ('Nord Soft', 'nordsecurity.com', 'Europe', 'Vilnius / remote')]
TRY = ["careers", "hr", "jobs", "people", "recruiting", "talent", "hiring", "join"]
GOOGLEISH = ("google", "gmail", "googlemail", "aspmx", "larksuite", "lark", "feishu")
TARGET = {
    "Karachi", "Pakistan", "UAE", "KSA", "Qatar", "Bahrain", "Kuwait", "Oman",
    "Egypt", "Jordan", "Lebanon", "Singapore", "Malaysia", "Europe", "Australia",
}
DONE = {
    "invalid", "reject", "bounce", "no-mx", "catch-all", "accept-then-unknown",
    "probe-blocked", "strict-valid",
}
DEAD = {"catch-all", "no-mx", "probe-blocked"}
SUFFIXES = {
    "PK", "KW", "QA", "AE", "SA", "EG", "JO", "BH", "SG", "MY", "AU", "EU", "RM",
    "Soft", "Soft2", "Soft3", "Soft4", "Digital", "Tech", "Careers", "HQ", "Labs", "Motors",
}


def main() -> int:
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
        if not domain or domain in sent_d or domain in dead_domains:
            continue
        if domain in seen:
            continue
        parts = name.split()
        while parts and parts[-1] in SUFFIXES:
            parts.pop()
        base = " ".join(parts).lower().strip()
        if name.strip().lower() in sent_c or any(
            base == c or (len(base) > 4 and (base in c or c in base)) for c in sent_c
        ):
            continue
        seen.add(domain)
        missing = []
        for loc in TRY:
            email = f"{loc}@{domain}"
            if loc in probed_locals[domain] or email in sent_e or email in bounces or cache.get(email) in DONE:
                continue
            missing.append(loc)
        if missing:
            fresh.append((name, domain, region, city, missing[:4]))

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
            pri = (
                -2
                if region in {"Karachi", "Pakistan"}
                else -1
                if region in {"Kuwait", "Qatar", "Australia", "UAE", "KSA", "Egypt", "MENA", "Jordan", "Bahrain"}
                else (0 if region in TARGET else 1)
            )
            google.append((pri, region, name, domain, city, locs))
        else:
            other += 1
    google.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    print(f"google/lark: {len(google)}  other mx skipped: {other}", flush=True)
    print("regions", Counter(item[1] for item in google), flush=True)
    for item in google[:40]:
        print(f"  plan {item[3]:32} try={item[5]}  {item[2]} [{item[1]}]", flush=True)

    found: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    target_hits = 20
    for i, (_pri, region, name, domain, city, locs) in enumerate(google, 1):
        if len(found) >= target_hits:
            print(f"hit {target_hits}, stop", flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(google)}] probe {email} ({name} / {region})", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.35)
            if ok:
                stats["ok"] += 1
                print(f"  OK  {email}  {detail[:110]}", flush=True)
                parts = name.split()
                while parts and parts[-1] in SUFFIXES:
                    parts.pop()
                clean = " ".join(parts) if parts else name
                found.append(
                    {
                        "Company": clean,
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

    out = ROOT / "output" / "emails_shortlist_batch28_2026-08-15.csv"
    fields = [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Other Emails", "Domain", "Careers / Apply URL", "Sample Role", "SMTP Verification",
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
