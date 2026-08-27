#!/usr/bin/env python3
"""Probe HIT emails from prior scrape that look hiring-ish; also scrape more small .io/.dev sites."""
from __future__ import annotations

import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "outreach"))

from job_hunter.config import PK_CONTACT_PATHS  # noqa: E402
from job_hunter.emails import pick_hr_email  # noqa: E402
from job_hunter.http import HttpClient  # noqa: E402
from job_hunter.textutil import extract_emails, html_to_text  # noqa: E402
from send_emails import BLOCKED_COMPANIES, BLOCKED_DOMAINS, SKIP_LOCAL, already_sent  # noqa: E402
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

OUT = ROOT / "output" / "emails_batch50c_2026-08-20.csv"

# From hunter HITs + more small product companies not yet mailed
EXTRA = [
    ("Conio", "conio.com", "jobs@conio.com"),
    ("Better Stack", "betterstack.com", "hello@betterstack.com"),
    ("Leapsome", "leapsome.com", "talent@leapsome.com"),
    ("Meilisearch", "meilisearch.com", "contact@meilisearch.com"),
    ("Nord Security", "nordsec.com", "career@nordsec.com"),
    ("OutSystems", "outsystems.com", "careers@outsystems.com"),
    ("Pleo", "pleo.io", "info@pleo.io"),
    ("Remote", "remote.com", "hiring@remote.com"),
    ("Teamwork", "teamwork.com", "jobs@teamwork.com"),
    ("Tally", "tally.so", "hello@tally.so"),
    ("Truecaller", "truecaller.com", "andreas.frid@truecaller.com"),
    ("Voodoo", "voodoo.io", "contact@voodoo.io"),
    ("Weaviate", "weaviate.io", "hello@weaviate.io"),
    ("Windmill", "windmill.dev", "jobs@windmill.dev"),
    ("Baremetrics", "baremetrics.com", "hello@baremetrics.com"),
    ("Cloudinary", "cloudinary.com", "hr.operations@cloudinary.com"),
    ("Close", "close.com", "talent@close.com"),
    ("Knock", "knock.app", "hello@knock.app"),
    ("Linear", "linear.app", "hello@linear.app"),
    ("Loops", "loops.so", "chris@loops.so"),
    ("LiveKit", "livekit.io", "recruiting@livekit.io"),
    ("Freshworks", "freshworks.com", "careers@freshworks.com"),
    ("Mux", "mux.com", "careers@mux.com"),
    ("Softr", "softr.io", "contact@softr.io"),
    ("Raycast", "raycast.com", "jobs@raycast.com"),
    ("Plane", "plane.so", "hello@plane.so"),
    ("Sourcegraph", "sourcegraph.com", "hi@sourcegraph.com"),
    ("Reclaim", "reclaim.ai", "careers@reclaim.ai"),
    ("Substack", "substackinc.com", "recruiting@substackinc.com"),
    ("Standard Notes", "standardnotes.com", "jobs@standardnotes.com"),
    ("Zapier", "zapier.com", "recruiting@zapier.com"),
    ("Xendit", "xendit.co", "hr-global@xendit.co"),
    ("Xero", "xero.com", "careers@xero.com"),
    ("Mistral AI", "mistral.ai", "contact@mistral.ai"),
    ("CoverManager", "covermanager.com", "hospitality.latam@covermanager.com"),
]

# More product companies likely Google MX, not in prior sends
MORE_DOMAINS = [
    ("Cal.com", "cal.com"),
    ("Resend", "resend.com"),
    ("Trigger.dev", "trigger.dev"),
    ("Inngest", "inngest.com"),
    ("Clerk", "clerk.com"),
    ("Supabase", "supabase.com"),
    ("Neon", "neon.tech"),
    ("PlanetScale", "planetscale.com"),
    ("Turso", "turso.tech"),
    ("Drizzle", "orm.drizzle.team"),
    ("tRPC", "trpc.io"),
    ("Bun", "bun.sh"),
    ("Deno", "deno.com"),
    ("Astro", "astro.build"),
    ("Remix", "remix.run"),
    ("Expo", "expo.dev"),
    ("Sanity", "sanity.io"),
    ("Contentful", "contentful.com"),
    ("Storyblok", "storyblok.com"),
    ("Builder.io", "builder.io"),
    ("Webflow", "webflow.com"),
    ("Framer", "framer.com"),
    ("Notion", "notion.so"),
    ("Coda", "coda.io"),
    ("Height", "height.app"),
    ("Motion", "usemotion.com"),
    ("Superhuman", "superhuman.com"),
    ("Shortwave", "shortwave.com"),
    ("Mimestream", "mimestream.com"),
    ("Cron", "cron.com"),
    ("Amplitude", "amplitude.com"),
    ("Mixpanel", "mixpanel.com"),
    ("PostHog", "posthog.com"),
    ("Heap", "heap.io"),
    ("FullStory", "fullstory.com"),
    ("Hotjar", "hotjar.com"),
    ("Crazy Egg", "crazyegg.com"),
    ("Customer.io", "customer.io"),
    ("CustomerIO", "customer.io"),
    ("Braze", "braze.com"),
    ("Iterable", "iterable.com"),
    ("OneSignal", "onesignal.com"),
    ("Pusher", "pusher.com"),
    ("Ably", "ably.com"),
    ("Stream", "getstream.io"),
    ("CometChat", "cometchat.com"),
    ("Sendbird", "sendbird.com"),
    ("Twilio", "twilio.com"),
    ("MessageBird", "messagebird.com"),
    ("Vonage", "vonage.com"),
    ("Deepgram", "deepgram.com"),
    ("AssemblyAI", "assemblyai.com"),
    ("ElevenLabs", "elevenlabs.io"),
    ("Runway", "runwayml.com"),
    ("Midjourney", "midjourney.com"),
    ("Perplexity", "perplexity.ai"),
    ("Cohere", "cohere.com"),
    ("Together AI", "together.ai"),
    ("Fireworks", "fireworks.ai"),
    ("Groq", "groq.com"),
    ("Anyscale", "anyscale.com"),
    ("Modal", "modal.com"),
    ("Replicate", "replicate.com"),
    ("Hugging Face", "huggingface.co"),  # blocked
    ("Weights & Biases", "wandb.ai"),
    ("Labelbox", "labelbox.com"),
    ("Scale AI", "scale.com"),
    ("Snorkel", "snorkel.ai"),
    ("Robust Intelligence", "robustintelligence.com"),
    ("Prefect", "prefect.io"),
    ("Dagster", "dagster.io"),
    ("Airbyte", "airbyte.com"),
    ("Fivetran", "fivetran.com"),
    ("dbt Labs", "getdbt.com"),
    ("Census", "getcensus.com"),
    ("Hightouch", "hightouch.com"),
    ("Segment", "segment.com"),
    ("RudderStack", "rudderstack.com"),
    ("Snowplow", "snowplow.io"),
    ("ClickHouse", "clickhouse.com"),
    ("Tinybird", "tinybird.co"),
    ("Materialize", "materialize.com"),
    ("Timescale", "timescale.com"),
    ("Cockroach Labs", "cockroachlabs.com"),
    ("Yugabyte", "yugabyte.com"),
    ("SingleStore", "singlestore.com"),
    ("MongoDB", "mongodb.com"),
    ("Redis", "redis.io"),
    ("Elastic", "elastic.co"),
    ("DataStax", "datastax.com"),
    ("Hasura", "hasura.io"),
    ("Grafbase", "grafbase.com"),
    ("Apollo GraphQL", "apollographql.com"),
    ("WunderGraph", "wundergraph.com"),
    ("StepZen", "stepzen.com"),
]


def cf_decode(encoded: str) -> str:
    key = int(encoded[:2], 16)
    return "".join(chr(int(encoded[n : n + 2], 16) ^ key) for n in range(2, len(encoded), 2))


def cf_emails(html: str) -> list[str]:
    out = []
    for encoded in re.findall(r"(?:data-cfemail|email-protection#)(?:=|\")?([0-9a-f]{6,})", html):
        try:
            decoded = cf_decode(encoded).lower()
        except Exception:
            continue
        if "@" in decoded and " " not in decoded:
            out.append(decoded)
    return out


def scrape(domain: str) -> list[str]:
    client = HttpClient(timeout=10.0)
    found = []
    try:
        for path in (
            "/impressum",
            "/imprint",
            "/contact",
            "/contact-us",
            "/careers",
            "/jobs",
            "/about",
            "/about-us",
            "/",
            "/company",
            "/legal",
        ):
            html = client.get_html(f"https://www.{domain}{path}") or client.get_html(f"https://{domain}{path}")
            if not html:
                continue
            emails = extract_emails(html_to_text(html) + " " + html) + cf_emails(html)
            for e in emails:
                local, _, host = e.partition("@")
                if local in SKIP_LOCAL:
                    continue
                if host == domain or host.endswith("." + domain):
                    found.append(e.lower())
                elif any(t in local for t in ("career", "recruit", "talent", "hiring", "hr", "job", "people")):
                    found.append(e.lower())
            if found:
                break
    finally:
        client.close()
    return list(dict.fromkeys(found))


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()
    blocked = BLOCKED_COMPANIES | {"huggingface", "hugging face"}

    candidates = {}

    def add(company, email, domain, source="company website"):
        email = email.lower().strip()
        domain = domain.lower()
        if not email or "@" not in email:
            return
        local = email.split("@", 1)[0]
        if local in SKIP_LOCAL or email in sent_e or email in bounced or email in candidates:
            return
        if company.lower() in sent_c or any(b == company.lower() or b in company.lower() for b in blocked):
            return
        if domain in sent_d or domain in BLOCKED_DOMAINS:
            return
        if any(r["Domain"] == domain for r in candidates.values()):
            return
        candidates[email] = {
            "Company": company,
            "Region": "Remote",
            "City": "",
            "HR / Recruiter Email": email,
            "Email Source": source,
            "Other Emails": "",
            "Domain": domain,
            "Careers / Apply URL": f"https://{domain}/careers",
            "Sample Role": "",
            "Location Clause": " (remote)",
            "Letter": "",
            "SMTP Verification": "",
        }

    print("Loading prior HITs…", flush=True)
    for company, domain, email in EXTRA:
        add(company, email, domain)

    print(f"Scraping {len(MORE_DOMAINS)} product companies…", flush=True)

    def one(item):
        name, domain = item
        return name, domain, scrape(domain)

    with ThreadPoolExecutor(max_workers=16) as pool:
        futs = [pool.submit(one, t) for t in MORE_DOMAINS]
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, domain, emails = fut.result()
            picked = pick_hr_email(emails)
            if picked:
                add(name, picked, domain)
                print(f"  [{done}] HIT {name:24} {picked}", flush=True)
            elif done % 15 == 0:
                print(f"  [{done}/{len(MORE_DOMAINS)}] candidates={len(candidates)}", flush=True)

    print(f"candidates {len(candidates)} — SMTP…", flush=True)
    ready = []
    rows = list(candidates.values())
    for i, row in enumerate(rows, 1):
        email = row["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        row["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} [{i}/{len(rows)}] {email:42} {row['Company'][:18]:18} {detail[:50]}", flush=True)
        if ok:
            ready.append(row)
        if len(ready) >= 55:
            break

    fields = list(ready[0].keys()) if ready else list(rows[0].keys()) if rows else []
    with OUT.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {OUT}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)


if __name__ == "__main__":
    main()
