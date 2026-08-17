#!/usr/bin/env python3
"""Probe fresh PK / MENA / Kuwait / Qatar / Europe / Australia hiring inboxes."""
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

# Unique domains only — skip anything already in COMPANY_DIRECTORY baseline by name reuse.
NEW = [
    # Pakistan software / product
    ("Sofizar", "sofizar.com", "Pakistan", "Lahore"),
    ("SoftPyramid", "softpyramid.com", "Pakistan", "Lahore"),
    ("WebHR", "webhr.co", "Pakistan", "Lahore / remote"),
    ("VTeams", "vteams.com", "Pakistan", "Lahore / remote"),
    ("CyberVision", "cybervisiontech.com", "Pakistan", "Islamabad"),
    ("Arrivy", "arrivy.com", "Pakistan", "Lahore / remote"),
    ("Markaz", "markaz.app", "Pakistan", "Lahore / remote"),
    ("Softinlays", "softinlays.com", "Pakistan", "Lahore"),
    ("Logicose", "logicose.com", "Pakistan", "Lahore"),
    ("Appxolute", "appxolute.com", "Pakistan", "Islamabad"),
    ("Dastgyr", "dastgyr.com", "Karachi", "Karachi"),
    ("Tez Financial Services", "tezfinancialservices.com", "Pakistan", "Lahore"),
    ("Golootlo", "golootlo.pk", "Karachi", "Karachi"),
    ("Synergy-IT", "synergy-it.com", "Pakistan", "Lahore"),
    ("Softsquare", "softsquare.biz", "Pakistan", "Lahore"),
    ("TechVista Systems", "techvistasystems.com", "Pakistan", "Lahore"),
    ("SoftAct", "softact.com", "Pakistan", "Islamabad"),
    ("Codehouse", "codehouse.pk", "Pakistan", "Islamabad"),
    ("Techverce", "techverce.com", "Pakistan", "Lahore"),
    ("Devathon", "devathon.com", "Pakistan", "Lahore / remote"),
    ("Codility Solutions", "codilitysolutions.com", "Pakistan", "Lahore"),
    ("ApexSoft", "apexsoft.net", "Pakistan", "Lahore"),
    ("FolioSoft", "foliosoft.com", "Pakistan", "Lahore"),
    ("CresTech", "crestechsoftware.com", "Pakistan", "Lahore"),
    ("Ebryx", "ebryx.com", "Pakistan", "Lahore / remote"),
    ("Fermat Commerce", "fermatcommerce.com", "Pakistan", "Lahore / remote"),
    ("Retailistan", "retailistan.com", "Karachi", "Karachi"),
    ("BankIslami Digital", "bankislami.com.pk", "Karachi", "Karachi"),
    ("JS Bank Digital", "jsbl.com", "Karachi", "Karachi"),
    ("Soneri Bank Digital", "soneribank.com", "Karachi", "Karachi"),
    ("Silkbank Digital", "silkbank.com.pk", "Karachi", "Karachi"),
    ("DIB Pakistan Digital", "dibpak.com", "Karachi", "Karachi"),
    # Kuwait
    ("UPayments", "upayments.com", "Kuwait", "Kuwait / remote"),
    ("SkipCash", "skipcash.com", "Kuwait", "Kuwait / remote"),
    ("Xcite Alghanim", "xcite.com", "Kuwait", "Kuwait"),
    ("Warba Bank Digital", "warbabank.com", "Kuwait", "Kuwait"),
    ("KIB Digital", "kib.com.kw", "Kuwait", "Kuwait"),
    ("Burgan Bank Digital", "burgan.com", "Kuwait", "Kuwait"),
    ("Jazeera Airways Digital", "jazeeraairways.com", "Kuwait", "Kuwait"),
    ("Kuwait Airways Digital", "kuwaitairways.com", "Kuwait", "Kuwait"),
    ("CBK Digital", "cbk.com", "Kuwait", "Kuwait"),
    ("KAMCO Invest Digital", "kamcoinvest.com", "Kuwait", "Kuwait"),
    ("Markaz Kuwait", "markaz.com", "Kuwait", "Kuwait"),
    ("Alghanim Industries Digital", "alghanim.com", "Kuwait", "Kuwait"),
    ("Equate Digital", "equate.com", "Kuwait", "Kuwait"),
    # Qatar
    ("iHorizons", "ihorizons.com", "Qatar", "Doha / remote"),
    ("Qatar Islamic Bank Digital", "qib.com.qa", "Qatar", "Doha"),
    ("Dukhan Bank Digital", "dukhanbank.com", "Qatar", "Doha"),
    ("Ahli Bank Qatar Digital", "ahlibank.com.qa", "Qatar", "Doha"),
    ("QIIB Digital", "qiib.com.qa", "Qatar", "Doha"),
    ("Hamad Medical Digital", "hamad.qa", "Qatar", "Doha"),
    ("Msheireb Properties Digital", "msheireb.com", "Qatar", "Doha"),
    ("Estithmar Holding Digital", "estithmarholding.com", "Qatar", "Doha"),
    ("GWC Digital", "gwclogistics.com", "Qatar", "Doha"),
    ("QTerminals Digital", "qterminals.qa", "Qatar", "Doha"),
    ("Mwani Qatar Digital", "mwani.com.qa", "Qatar", "Doha"),
    ("Qatar Post Digital", "qatarpost.qa", "Qatar", "Doha"),
    ("Aspire Zone Digital", "aspirezone.qa", "Qatar", "Doha"),
    ("Barwa Digital", "barwa.com.qa", "Qatar", "Doha"),
    ("UDC Digital", "udcqatar.com", "Qatar", "Doha"),
    ("Qatari Diar Digital", "qataridiar.com", "Qatar", "Doha"),
    # Australia
    ("Atlassian", "atlassian.com", "Australia", "Sydney / remote"),
    ("Culture Amp", "cultureamp.com", "Australia", "Melbourne / remote"),
    ("SafetyCulture", "safetyculture.com", "Australia", "Sydney / remote"),
    ("Deputy", "deputy.com", "Australia", "Sydney / remote"),
    ("Employment Hero", "employmenthero.com", "Australia", "Sydney / remote"),
    ("Linktree", "linktr.ee", "Australia", "Melbourne / remote"),
    ("Immutable", "immutable.com", "Australia", "Sydney / remote"),
    ("Airwallex", "airwallex.com", "Australia", "Melbourne / remote"),
    ("Envato", "envato.com", "Australia", "Melbourne / remote"),
    ("Campaign Monitor", "campaignmonitor.com", "Australia", "Sydney / remote"),
    ("REA Group", "rea-group.com", "Australia", "Melbourne / remote"),
    ("SEEK", "seek.com.au", "Australia", "Melbourne / remote"),
    ("Carsales", "carsales.com.au", "Australia", "Melbourne / remote"),
    ("Domain Group", "domain.com.au", "Australia", "Sydney / remote"),
    ("Tyro", "tyro.com", "Australia", "Sydney / remote"),
    ("Zip Co", "zip.co", "Australia", "Sydney / remote"),
    ("Afterpay", "afterpay.com", "Australia", "Melbourne / remote"),
    ("Brighte", "brighte.com.au", "Australia", "Sydney / remote"),
    ("Expert360", "expert360.com", "Australia", "Sydney / remote"),
    ("Hipages", "hipages.com.au", "Australia", "Sydney / remote"),
    ("Airtasker", "airtasker.com", "Australia", "Sydney / remote"),
    ("Buildkite", "buildkite.com", "Australia", "Melbourne / remote"),
    ("Prospa", "prospa.com", "Australia", "Sydney / remote"),
    ("Judo Bank", "judo.bank", "Australia", "Melbourne / remote"),
    ("Up Banking", "up.com.au", "Australia", "Melbourne / remote"),
    ("Wisetech Global", "wisetechglobal.com", "Australia", "Sydney / remote"),
    ("TechnologyOne", "technologyonecorp.com", "Australia", "Brisbane / remote"),
    ("NextDC", "nextdc.com", "Australia", "Sydney / remote"),
    ("SiteMinder", "siteminder.com", "Australia", "Sydney / remote"),
    ("Rokt", "rokt.com", "Australia", "Sydney / remote"),
    ("Finder", "finder.com.au", "Australia", "Sydney / remote"),
    ("Xero", "xero.com", "Australia", "Melbourne / remote"),
    ("MYOB", "myob.com", "Australia", "Melbourne / remote"),
    # Europe / remote fresh
    ("Soldo", "soldo.com", "Europe", "London / remote"),
    ("Mambu", "mambu.com", "Europe", "Amsterdam / remote"),
    ("Solaris", "solarisgroup.com", "Europe", "Berlin / remote"),
    ("Vivid Money", "vivid.money", "Europe", "Berlin / remote"),
    ("Bux", "getbux.com", "Europe", "Amsterdam / remote"),
    ("Plum", "withplum.com", "Europe", "London / remote"),
    ("Moneybox", "moneyboxapp.com", "Europe", "London / remote"),
    ("Octopus Energy", "octopus.energy", "Europe", "London / remote"),
    ("Gousto", "gousto.co.uk", "Europe", "London / remote"),
    ("Flink", "goflink.com", "Europe", "Berlin / remote"),
    ("Getir", "getir.com", "Europe", "London / remote"),
    ("Amie", "amie.so", "Europe", "Berlin / remote"),
    ("Morgen", "morgen.so", "Europe", "Berlin / remote"),
    ("MailerLite", "mailerlite.com", "Europe", "Vilnius / remote"),
    ("Brevo", "brevo.com", "Europe", "Paris / remote"),
    ("ConfigCat", "configcat.com", "Europe", "Budapest / remote"),
    ("Unleash", "getunleash.io", "Europe", "Oslo / remote"),
    ("ChartMogul", "chartmogul.com", "Europe", "Berlin / remote"),
    ("Simple Analytics", "simpleanalytics.com", "Europe", "Amsterdam / remote"),
    ("Better Stack", "betterstack.com", "Europe", "Prague / remote"),
    ("Checkly", "checklyhq.com", "Europe", "Amsterdam / remote"),
    ("Smartlook", "smartlook.com", "Europe", "Brno / remote"),
    ("Make", "make.com", "Europe", "Prague / remote"),
    ("Windmill", "windmill.dev", "Europe", "Paris / remote"),
    ("Heetch", "heetch.com", "Europe", "Paris / remote"),
    ("Jumia", "jumia.com", "Egypt", "Cairo / remote"),
    ("Atome", "atome.sg", "Singapore", "Singapore / remote"),
    ("Garena", "garena.com", "Singapore", "Singapore / remote"),
    ("Payload", "payloadcms.com", "Remote", "Worldwide remote"),
    ("Kit", "kit.com", "Remote", "Worldwide remote"),
    ("Buttondown", "buttondown.com", "Remote", "Worldwide remote"),
    ("Statsig", "statsig.com", "Remote", "Worldwide remote"),
    ("Svix", "svix.com", "Remote", "Worldwide remote"),
    ("Knock", "knock.app", "Remote", "Worldwide remote"),
    ("Courier", "courier.com", "Remote", "Worldwide remote"),
    ("Polar", "polar.sh", "Remote", "Worldwide remote"),
    ("Lemon Squeezy", "lemonsqueezy.com", "Remote", "Worldwide remote"),
    ("Gumroad", "gumroad.com", "Remote", "Worldwide remote"),
    ("Baremetrics", "baremetrics.com", "Remote", "Worldwide remote"),
    ("Fathom Analytics", "usefathom.com", "Remote", "Worldwide remote"),
    ("LogRocket", "logrocket.com", "Remote", "Worldwide remote"),
    ("Upstash", "upstash.com", "Remote", "Worldwide remote"),
    ("ClickHouse", "clickhouse.com", "Remote", "Worldwide remote"),
    ("Prefect", "prefect.io", "Remote", "Worldwide remote"),
    ("Dagster", "dagster.io", "Remote", "Worldwide remote"),
    ("Pipedream", "pipedream.com", "Remote", "Worldwide remote"),
    ("Fillout", "fillout.com", "Remote", "Worldwide remote"),
    ("Jotform", "jotform.com", "Remote", "Worldwide remote"),
    ("Typesense", "typesense.org", "Remote", "Worldwide remote"),
    ("Xata", "xata.io", "Remote", "Worldwide remote"),
    ("Turso", "turso.tech", "Remote", "Worldwide remote"),
    ("MotherDuck", "motherduck.com", "Remote", "Worldwide remote"),
    ("Hatchet", "hatchet.run", "Remote", "Worldwide remote"),
    ("Calendly", "calendly.com", "Remote", "Worldwide remote"),
    ("SavvyCal", "savvycal.com", "Remote", "Worldwide remote"),
    ("Motion", "usemotion.com", "Remote", "Worldwide remote"),
    ("Reclaim", "reclaim.ai", "Remote", "Worldwide remote"),
    ("Clockwise", "clockwise.so", "Remote", "Worldwide remote"),
    ("Kraken", "kraken.com", "Remote", "Worldwide remote"),
    # more Europe product
    ("Personio Careers", "personio.de", "Europe", "Munich / remote"),
    ("SumUp Careers", "sumup.de", "Europe", "London / remote"),
    ("Klarna Careers", "klarna.se", "Europe", "Stockholm / remote"),
    ("Wise Careers", "wise.com", "Europe", "London / remote"),
    ("Revolut Careers", "revolut.com", "Europe", "London / remote"),
    ("Monzo Careers", "monzo.com", "Europe", "London / remote"),
    ("Starling Careers", "starlingbank.com", "Europe", "London / remote"),
    ("Tide Careers", "tide.co", "Europe", "London / remote"),
    ("Curve Careers", "curve.com", "Europe", "London / remote"),
    ("Cleo Careers", "meetcleo.com", "Europe", "London / remote"),
    ("Marshmallow Careers", "marshmallow.com", "Europe", "London / remote"),
    ("Zepz Careers", "zepz.com", "Europe", "London / remote"),
    ("Rapyd Careers", "rapyd.net", "Europe", "London / remote"),
    ("Onfido Careers", "onfido.com", "Europe", "London / remote"),
    ("Attio Careers", "attio.com", "Europe", "London / remote"),
    ("Faculty Careers", "faculty.ai", "Europe", "London / remote"),
    ("Tractable Careers", "tractable.ai", "Europe", "London / remote"),
    ("Darktrace Careers", "darktrace.com", "Europe", "Cambridge / remote"),
    ("Featurespace Careers", "featurespace.com", "Europe", "Cambridge / remote"),
    ("Thought Machine Careers", "thoughtmachine.net", "Europe", "London / remote"),
    ("OakNorth Careers", "oaknorth.com", "Europe", "London / remote"),
    ("GoCardless Careers", "gocardless.com", "Europe", "London / remote"),
    ("Paddle Careers", "paddle.com", "Europe", "London / remote"),
    ("Deliveroo Careers", "deliveroo.com", "Europe", "London / remote"),
    ("Trainline Careers", "thetrainline.com", "Europe", "London / remote"),
    ("Skyscanner Careers", "skyscanner.net", "Europe", "Edinburgh / remote"),
    ("N26 Careers", "n26.com", "Europe", "Berlin / remote"),
    ("Trade Republic Careers", "traderepublic.com", "Europe", "Berlin / remote"),
    ("Contentful Careers", "contentful.com", "Europe", "Berlin / remote"),
    ("GetYourGuide Careers", "getyourguide.com", "Europe", "Berlin / remote"),
    ("SoundCloud Careers", "soundcloud.com", "Europe", "Berlin / remote"),
    ("Zalando Careers", "zalando.com", "Europe", "Berlin / remote"),
    ("HelloFresh Careers", "hellofresh.com", "Europe", "Berlin / remote"),
    ("AUTO1 Careers", "auto1-group.com", "Europe", "Berlin / remote"),
    ("Wefox Careers", "wefox.com", "Europe", "Berlin / remote"),
    ("Flix Careers", "flix.com", "Europe", "Munich / remote"),
    ("Celonis Careers", "celonis.com", "Europe", "Munich / remote"),
    ("Personio GmbH", "personio.com", "Europe", "Munich / remote"),
    ("Miro Careers", "miro.com", "Europe", "Amsterdam / remote"),
    ("Adyen Careers", "adyen.com", "Europe", "Amsterdam / remote"),
    ("Mollie Careers", "mollie.com", "Europe", "Amsterdam / remote"),
    ("Bird Careers", "bird.com", "Europe", "Amsterdam / remote"),
    ("TomTom Careers", "tomtom.com", "Europe", "Amsterdam / remote"),
    ("WeTransfer Careers", "wetransfer.com", "Europe", "Amsterdam / remote"),
    ("Picnic Careers", "picnic.app", "Europe", "Amsterdam / remote"),
    ("Bunq Careers", "bunq.com", "Europe", "Amsterdam / remote"),
    ("Backbase Careers", "backbase.com", "Europe", "Amsterdam / remote"),
    ("Booking Careers", "booking.com", "Europe", "Amsterdam / remote"),
    ("Doctolib Careers", "doctolib.com", "Europe", "Paris / remote"),
    ("BlaBlaCar Careers", "blablacar.com", "Europe", "Paris / remote"),
    ("Ledger Careers", "ledger.com", "Europe", "Paris / remote"),
    ("Alan Careers", "alan.com", "Europe", "Paris / remote"),
    ("Qonto Careers", "qonto.com", "Europe", "Paris / remote"),
    ("Dataiku Careers", "dataiku.com", "Europe", "Paris / remote"),
    ("Mistral Careers", "mistral.ai", "Europe", "Paris / remote"),
    ("Photoroom Careers", "photoroom.com", "Europe", "Paris / remote"),
    ("Back Market Careers", "backmarket.com", "Europe", "Paris / remote"),
    ("Glovo Careers", "glovoapp.com", "Europe", "Barcelona / remote"),
    ("Factorial Careers", "factorialhr.com", "Europe", "Barcelona / remote"),
    ("Typeform Careers", "typeform.com", "Europe", "Barcelona / remote"),
    ("TravelPerk Careers", "travelperk.com", "Europe", "Barcelona / remote"),
    ("Remote.com Careers", "remote.com", "Europe", "Lisbon / remote"),
    ("Talkdesk Careers", "talkdesk.com", "Europe", "Lisbon / remote"),
    ("Feedzai Careers", "feedzai.com", "Europe", "Lisbon / remote"),
    ("OutSystems Careers", "outsystems.com", "Europe", "Lisbon / remote"),
    ("Intercom Careers", "intercom.com", "Europe", "Dublin / remote"),
    ("Klarna Careers2", "klarna.com", "Europe", "Stockholm / remote"),
    ("Spotify Careers", "spotify.com", "Europe", "Stockholm / remote"),
    ("Trustpilot Careers", "trustpilot.com", "Europe", "Copenhagen / remote"),
    ("Pleo Careers", "pleo.io", "Europe", "Copenhagen / remote"),
    ("Wolt Careers", "wolt.com", "Europe", "Helsinki / remote"),
    ("Aiven Careers", "aiven.io", "Europe", "Helsinki / remote"),
    ("Bolt Careers", "bolt.eu", "Europe", "Tallinn / remote"),
    ("Pipedrive Careers", "pipedrive.com", "Europe", "Tallinn / remote"),
    ("Veriff Careers", "veriff.com", "Europe", "Tallinn / remote"),
    ("Preply Careers", "preply.com", "Europe", "Kyiv / remote"),
    ("Qdrant Careers", "qdrant.tech", "Europe", "Berlin / remote"),
    ("Weaviate Careers", "weaviate.io", "Europe", "Amsterdam / remote"),
    ("deepset Careers", "deepset.ai", "Europe", "Berlin / remote"),
    ("ElevenLabs Careers", "elevenlabs.io", "Europe", "London / remote"),
    ("Synthesia Careers", "synthesia.io", "Europe", "London / remote"),
    ("Stability AI Careers", "stability.ai", "Europe", "London / remote"),
    ("DeepL Careers", "deepl.com", "Europe", "Cologne / remote"),
    ("Aleph Alpha Careers", "aleph-alpha.com", "Europe", "Heidelberg / remote"),
    ("PostHog Careers", "posthog.com", "Europe", "Europe / remote"),
    ("Langfuse Careers", "langfuse.com", "Europe", "Berlin / remote"),
    ("Cal.com Careers", "cal.com", "Europe", "Europe / remote"),
    ("Plausible Careers", "plausible.io", "Europe", "Europe / remote"),
    ("Strapi Careers", "strapi.io", "Europe", "Paris / remote"),
    ("Framer Careers", "framer.com", "Europe", "Amsterdam / remote"),
    ("Doist Careers", "doist.com", "Europe", "Europe / remote"),
    ("Toggl Careers", "toggl.com", "Europe", "Tallinn / remote"),
    ("Hotjar Careers", "hotjar.com", "Europe", "Malta / remote"),
    ("GitBook Careers", "gitbook.com", "Europe", "Europe / remote"),
    ("Hetzner Careers", "hetzner.com", "Europe", "Germany / remote"),
    ("Nextcloud Careers", "nextcloud.com", "Europe", "Stuttgart / remote"),
    ("Proton Careers", "proton.me", "Europe", "Geneva / remote"),
    ("Element Careers", "element.io", "Europe", "London / remote"),
    ("Nord Security Careers", "nordsecurity.com", "Europe", "Vilnius / remote"),
    ("Mullvad Careers", "mullvad.net", "Europe", "Gothenburg / remote"),
    ("Vivaldi Careers", "vivaldi.com", "Europe", "Oslo / remote"),
    ("Ecosia Careers", "ecosia.org", "Europe", "Berlin / remote"),
    ("Bitdefender Careers", "bitdefender.com", "Europe", "Bucharest / remote"),
    ("Grafana Careers", "grafana.com", "Europe", "Stockholm / remote"),
    ("Supabase Careers", "supabase.com", "Remote", "Worldwide remote"),
    ("Sentry Careers", "sentry.io", "Remote", "Worldwide remote"),
    ("Neon Careers", "neon.tech", "Remote", "Worldwide remote"),
    ("Railway Careers", "railway.app", "Remote", "Worldwide remote"),
    ("Render Careers", "render.com", "Remote", "Worldwide remote"),
    ("Fly.io Careers", "fly.io", "Remote", "Worldwide remote"),
    ("Resend Careers", "resend.com", "Remote", "Worldwide remote"),
    ("Clerk Careers", "clerk.com", "Remote", "Worldwide remote"),
    ("WorkOS Careers", "workos.com", "Remote", "Worldwide remote"),
    ("Linear Careers", "linear.app", "Remote", "Worldwide remote"),
    ("Raycast Careers", "raycast.com", "Remote", "Worldwide remote"),
    ("Notion Careers", "notion.so", "Remote", "Worldwide remote"),
    ("Retool Careers", "retool.com", "Remote", "Worldwide remote"),
    ("Hasura Careers", "hasura.io", "Remote", "Worldwide remote"),
    ("PlanetScale Careers", "planetscale.com", "Remote", "Worldwide remote"),
    ("Vercel Careers", "vercel.com", "Remote", "Worldwide remote"),
    ("Netlify Careers", "netlify.com", "Remote", "Worldwide remote"),
    ("HashiCorp Careers", "hashicorp.com", "Remote", "Worldwide remote"),
    ("Datadog Careers", "datadoghq.com", "Remote", "Worldwide remote"),
    ("New Relic Careers", "newrelic.com", "Remote", "Worldwide remote"),
    ("PagerDuty Careers", "pagerduty.com", "Remote", "Worldwide remote"),
    ("Amplitude Careers", "amplitude.com", "Remote", "Worldwide remote"),
    ("Mixpanel Careers", "mixpanel.com", "Remote", "Worldwide remote"),
    ("Webflow Careers", "webflow.com", "Remote", "Worldwide remote"),
    ("Figma Careers", "figma.com", "Remote", "Worldwide remote"),
    ("ClickUp Careers", "clickup.com", "Remote", "Worldwide remote"),
    ("Asana Careers", "asana.com", "Remote", "Worldwide remote"),
    ("Zapier Careers", "zapier.com", "Remote", "Worldwide remote"),
    ("Buffer Careers", "buffer.com", "Remote", "Worldwide remote"),
    ("Basecamp Careers", "basecamp.com", "Remote", "Worldwide remote"),
    ("Help Scout Careers", "helpscout.com", "Remote", "Worldwide remote"),
    ("Close Careers", "close.com", "Remote", "Worldwide remote"),
    ("Beehiiv Careers", "beehiiv.com", "Remote", "Worldwide remote"),
    ("Substack Careers", "substack.com", "Remote", "Worldwide remote"),
    ("Twilio Careers", "twilio.com", "Remote", "Worldwide remote"),
    ("Plaid Careers", "plaid.com", "Remote", "Worldwide remote"),
    ("Stripe Careers", "stripe.com", "Remote", "Worldwide remote"),
    ("Deel Careers", "deel.com", "Remote", "Worldwide remote"),
    ("Rippling Careers", "rippling.com", "Remote", "Worldwide remote"),
    ("Ashby Careers", "ashbyhq.com", "Remote", "Worldwide remote"),
    ("Apollo Careers", "apollo.io", "Remote", "Worldwide remote"),
    ("Clay Careers", "clay.com", "Remote", "Worldwide remote"),
    ("BrowserStack Careers", "browserstack.com", "Remote", "Worldwide remote"),
    ("Freshworks Careers", "freshworks.com", "Remote", "Worldwide remote"),
    ("Zoho Careers", "zoho.com", "Remote", "Worldwide remote"),
    ("Chargebee Careers", "chargebee.com", "Remote", "Worldwide remote"),
    ("Razorpay Careers", "razorpay.com", "Remote", "Worldwide remote"),
    ("Postman Careers", "postman.com", "Remote", "Worldwide remote"),
    ("Airbyte Careers", "airbyte.com", "Remote", "Worldwide remote"),
    ("dbt Labs Careers", "getdbt.com", "Remote", "Worldwide remote"),
    ("Fivetran Careers", "fivetran.com", "Remote", "Worldwide remote"),
    ("Segment Careers", "segment.com", "Remote", "Worldwide remote"),
    ("RudderStack Careers", "rudderstack.com", "Remote", "Worldwide remote"),
    ("Metabase Careers", "metabase.com", "Remote", "Worldwide remote"),
    ("Hex Careers", "hex.tech", "Remote", "Worldwide remote"),
    ("AssemblyAI Careers", "assemblyai.com", "Remote", "Worldwide remote"),
    ("RunPod Careers", "runpod.io", "Remote", "Worldwide remote"),
    ("Together AI Careers", "together.ai", "Remote", "Worldwide remote"),
    ("Fireworks AI Careers", "fireworks.ai", "Remote", "Worldwide remote"),
    ("Anyscale Careers", "anyscale.com", "Remote", "Worldwide remote"),
    ("Weights & Biases Careers", "wandb.ai", "Remote", "Worldwide remote"),
    ("Labelbox Careers", "labelbox.com", "Remote", "Worldwide remote"),
    ("Lovable Careers", "lovable.dev", "Remote", "Worldwide remote"),
    ("Replicate Careers", "replicate.com", "Remote", "Worldwide remote"),
    ("Modal Careers", "modal.com", "Remote", "Worldwide remote"),
    ("Tinybird Careers", "tinybird.co", "Remote", "Worldwide remote"),
    ("Inngest Careers", "inngest.com", "Remote", "Worldwide remote"),
    ("Trigger.dev Careers", "trigger.dev", "Remote", "Worldwide remote"),
    ("Liveblocks Careers", "liveblocks.io", "Remote", "Worldwide remote"),
    ("Novu Careers", "novu.co", "Remote", "Worldwide remote"),
    ("Dub.co Careers", "dub.co", "Remote", "Worldwide remote"),
    ("Twenty Careers", "twenty.com", "Remote", "Worldwide remote"),
    ("Plane Careers", "plane.so", "Remote", "Worldwide remote"),
    ("AppSmith Careers", "appsmith.com", "Remote", "Worldwide remote"),
    ("Tooljet Careers", "tooljet.com", "Remote", "Worldwide remote"),
    ("Budibase Careers", "budibase.com", "Remote", "Worldwide remote"),
    ("NocoDB Careers", "nocodb.com", "Remote", "Worldwide remote"),
    ("Baserow Careers", "baserow.io", "Remote", "Worldwide remote"),
    ("Bitwarden Careers", "bitwarden.com", "Remote", "Worldwide remote"),
    ("1Password Careers", "1password.com", "Remote", "Worldwide remote"),
    ("Tailscale Careers", "tailscale.com", "Remote", "Worldwide remote"),
    ("Fastly Careers", "fastly.com", "Remote", "Worldwide remote"),
    ("DigitalOcean Careers", "digitalocean.com", "Remote", "Worldwide remote"),
    ("Cloudinary Careers", "cloudinary.com", "Remote", "Worldwide remote"),
    ("Mux Careers", "mux.com", "Remote", "Worldwide remote"),
    ("LiveKit Careers", "livekit.io", "Remote", "Worldwide remote"),
    ("Customer.io Careers", "customer.io", "Remote", "Worldwide remote"),
    ("Braze Careers", "braze.com", "Remote", "Worldwide remote"),
    ("OneSignal Careers", "onesignal.com", "Remote", "Worldwide remote"),
    ("CleverTap Careers", "clevertap.com", "Remote", "Worldwide remote"),
    ("MoEngage Careers", "moengage.com", "Remote", "Worldwide remote"),
    ("Chatwoot Careers", "chatwoot.com", "Remote", "Worldwide remote"),
    ("Crisp Careers", "crisp.chat", "Remote", "Worldwide remote"),
    ("incident.io Careers", "incident.io", "Remote", "Worldwide remote"),
    ("Rootly Careers", "rootly.com", "Remote", "Worldwide remote"),
    ("Honeycomb Careers", "honeycomb.io", "Remote", "Worldwide remote"),
    ("Sourcegraph Careers", "sourcegraph.com", "Remote", "Worldwide remote"),
    ("Codecov Careers", "codecov.io", "Remote", "Worldwide remote"),
    ("SonarSource Careers", "sonarsource.com", "Europe", "Geneva / remote"),
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
    "Australia",
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
    # Domains already successfully mailed — skip.
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

    # Prefer domains that are new to the probe list OR still have untried locals.
    existing_in_dir = {d.lower() for _, d, *_ in COMPANY_DIRECTORY}
    seen: set[str] = set()
    fresh: list[tuple[str, str, str, str, list[str]]] = []
    for name, domain, region, city in NEW:
        domain = domain.lower().strip()
        if not domain or domain in sent_d or domain in dead_domains:
            continue
        if domain in seen or name.strip().lower() in sent_c:
            continue
        # Also skip if any close company name already mailed.
        base = name.lower().replace(" careers", "").replace(" digital", "").replace(" tech", "").replace(" au", "")
        if any(base == c or base in c or c in base for c in sent_c):
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

    print(f"fresh companies after filters: {len(fresh)} (dir has {len(existing_in_dir)} domains)", flush=True)

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
                if region in {"Kuwait", "Qatar", "Australia", "UAE", "KSA", "Egypt", "MENA"}
                else (0 if region in TARGET else 1)
            )
            google.append((pri, region, name, domain, city, locs))
        else:
            other += 1
    google.sort(key=lambda item: (item[0], item[1], item[2].lower()))
    print(f"google/lark: {len(google)}  other mx skipped: {other}", flush=True)
    print("regions", Counter(item[1] for item in google), flush=True)
    for item in google[:25]:
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
            time.sleep(0.25)
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

    out = ROOT / "output" / "emails_shortlist_batch13_2026-08-14.csv"
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
