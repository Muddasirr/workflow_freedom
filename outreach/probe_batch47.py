#!/usr/bin/env python3
"""Probe batch47: fresh hiring aliases + residual (2026-08-17)."""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "outreach"))
from smtp_verify import CACHE, _load_csv_map, bounced_emails, mx_hosts, verify_mailbox  # noqa: E402

TRY = ["careers", "hr", "jobs", "people", "recruiting", "talent", "hiring", "join", "recruitment", "career"]
GOOD_MX = (
    "google", "gmail", "googlemail", "aspmx",
    "larksuite", "lark", "feishu",
    "pphosted", "proofpoint", "mimecast",
)
SUFFIX = {"Soft", "Soft2", "Soft3", "Soft4", "HQ", "PK"}
BLOCKED = {
    "huggingface", "hugging face", "n8n", "openai", "anthropic", "vercel",
    "cloudflare", "airtable", "stripe", "gitlab", "canonical", "automattic",
    "toptal", "andela", "lemon.io", "launchdarkly", "character", "codet",
}
DEAD = {"catch-all", "no-mx", "probe-blocked"}
DONE = DEAD | {"invalid", "reject", "bounce", "accept-then-unknown", "strict-valid"}

NEW = [
    ("Contentful Soft", "contentful.com", "Europe", "Berlin"),
    ("SumUp Soft", "sumup.com", "Europe", "London"),
    ("GetYourGuide Soft", "getyourguide.com", "Europe", "Berlin"),
    ("HelloFresh Soft", "hellofresh.com", "Europe", "Berlin"),
    ("Flix Soft", "flixbus.com", "Europe", "Munich"),
    ("Too Good Soft", "toogoodtogo.com", "Europe", "Copenhagen"),
    ("Trustpilot Soft", "trustpilot.com", "Europe", "Copenhagen"),
    ("Leapwork Soft", "leapwork.com", "Europe", "Copenhagen"),
    ("Pleo Soft", "pleo.io", "Europe", "Copenhagen"),
    ("Capchase Soft", "capchase.com", "Europe", "Madrid"),
    ("Typeform Soft", "typeform.com", "Europe", "Barcelona"),
    ("Holded Soft", "holded.com", "Europe", "Barcelona"),
    ("Wallapop Soft", "wallapop.com", "Europe", "Barcelona"),
    ("Glovo Soft", "glovoapp.com", "Europe", "Barcelona"),
    ("Bnext Soft", "bnext.es", "Europe", "Madrid"),
    ("Starling Soft", "starlingbank.com", "Europe", "London"),
    ("Wise Soft", "wise.com", "Europe", "London"),
    ("GoCardless Soft", "gocardless.com", "Europe", "London"),
    ("OakNorth Soft", "oaknorth.com", "Europe", "London"),
    ("Curve Soft", "curve.com", "Europe", "London"),
    ("Nested Soft", "nested.com", "Europe", "London"),
    ("Habito Soft", "habito.com", "Europe", "London"),
    ("Zego Soft", "zego.com", "Europe", "London"),
    ("Vivino Soft", "vivino.com", "Europe", "Copenhagen"),
    ("Tooploox Soft", "tooploox.com", "Europe", "Wroclaw"),
    ("Docplanner Soft", "docplanner.com", "Europe", "Warsaw"),
    ("Allegro Soft", "allegro.pl", "Europe", "Poznan"),
    ("CD Projekt Soft", "cdprojekt.com", "Europe", "Warsaw"),
    ("Eleven Soft", "elevenlabs.io", "Europe", "Warsaw"),
    ("DeepL Soft", "deepl.com", "Europe", "Cologne"),
    ("Singular Soft", "singular.net", "Europe", "Tel Aviv"),
    ("Monday Soft", "monday.com", "Europe", "Tel Aviv"),
    ("Wix Soft", "wix.com", "Europe", "Tel Aviv"),
    ("Fiverr Soft", "fiverr.com", "Europe", "Tel Aviv"),
    ("Similarweb Soft", "similarweb.com", "Europe", "Tel Aviv"),
    ("Melio Soft", "meliopayments.com", "Europe", "Tel Aviv"),
    ("Pagaya Soft", "pagaya.com", "Europe", "Tel Aviv"),
    ("Hibob Soft", "hibob.com", "Europe", "Tel Aviv"),
    ("Gong Soft", "gong.io", "Europe", "Tel Aviv"),
    ("Walkme Soft", "walkme.com", "Europe", "Tel Aviv"),
    ("Yotpo Soft", "yotpo.com", "Europe", "Tel Aviv"),
    ("Next Soft", "nextinsurance.com", "Remote", "Worldwide"),
    ("Papaya Soft", "papayaglobal.com", "Europe", "Tel Aviv"),
    ("Lightricks Soft", "lightricks.com", "Europe", "Jerusalem"),
    ("Moon Active Soft", "moonactive.com", "Europe", "Tel Aviv"),
    ("Playtika Soft", "playtika.com", "Europe", "Tel Aviv"),
    ("IronSource Soft", "is.com", "Europe", "Tel Aviv"),
    ("King Soft", "king.com", "Europe", "Stockholm"),
    ("Spotify Soft", "spotify.com", "Europe", "Stockholm"),
    ("Klarna Soft", "klarna.com", "Europe", "Stockholm"),
    ("Truecaller Soft", "truecaller.com", "Europe", "Stockholm"),
    ("Epidemic Soft", "epidemicsound.com", "Europe", "Stockholm"),
    ("Tobii Soft", "tobii.com", "Europe", "Stockholm"),
    ("Meltwater Soft", "meltwater.com", "Europe", "Oslo"),
    ("Kahoot Soft", "kahoot.com", "Europe", "Oslo"),
    ("Vipps Soft", "vipps.no", "Europe", "Oslo"),
    ("Schibsted Soft", "schibsted.com", "Europe", "Oslo"),
    ("Vinted Soft", "vinted.com", "Europe", "Vilnius"),
    ("TransferGo Soft", "transfergo.com", "Europe", "Vilnius"),
    ("Paysera Soft", "paysera.com", "Europe", "Vilnius"),
    ("Nord Soft", "nordsecurity.com", "Europe", "Vilnius"),
    ("Tesonet Soft", "tesonet.com", "Europe", "Vilnius"),
    ("Hostinger Soft", "hostinger.com", "Europe", "Kaunas"),
    ("Oxylabs Soft", "oxylabs.io", "Europe", "Vilnius"),
    ("Surfshark Soft", "surfshark.com", "Europe", "Vilnius"),
    ("Pipedrive Soft", "pipedrive.com", "Europe", "Tallinn"),
    ("Veriff Soft", "veriff.com", "Europe", "Tallinn"),
    ("Skeleton Soft", "skeleton.tech", "Europe", "Tallinn"),
    ("Wise Soft2", "transferwise.com", "Europe", "London"),
    ("Adyen Soft", "adyen.com", "Europe", "Amsterdam"),
    ("MessageBird Soft", "messagebird.com", "Europe", "Amsterdam"),
    ("Bird Soft", "bird.com", "Europe", "Amsterdam"),
    ("Booking Soft", "booking.com", "Europe", "Amsterdam"),
    ("TomTom Soft", "tomtom.com", "Europe", "Amsterdam"),
    ("Exact Soft", "exact.com", "Europe", "Delft"),
    ("Sendcloud Soft", "sendcloud.com", "Europe", "Amsterdam"),
    ("Bol Soft", "bol.com", "Europe", "Utrecht"),
    ("Takeaway Soft", "justeattakeaway.com", "Europe", "Amsterdam"),
    ("Picnic Soft", "picnic.app", "Europe", "Amsterdam"),
    ("Backbase Soft", "backbase.com", "Europe", "Amsterdam"),
    ("Mambu Soft", "mambu.com", "Europe", "Amsterdam"),
    ("WeTransfer Soft", "wetransfer.com", "Europe", "Amsterdam"),
    ("Miro Soft", "miro.com", "Europe", "Amsterdam"),
    ("Catawiki Soft", "catawiki.com", "Europe", "Amsterdam"),
    ("Databricks Soft", "databricks.com", "Remote", "Worldwide"),
    ("Snowflake Soft", "snowflake.com", "Remote", "Worldwide"),
    ("Confluent Soft", "confluent.io", "Remote", "Worldwide"),
    ("Elastic Soft", "elastic.co", "Remote", "Worldwide"),
    ("Redis Soft", "redis.com", "Remote", "Worldwide"),
    ("Redis Soft2", "redis.io", "Remote", "Worldwide"),
    ("ClickHouse Soft", "clickhouse.com", "Remote", "Worldwide"),
    ("SingleStore Soft", "singlestore.com", "Remote", "Worldwide"),
    ("TigerData Soft", "tigerdata.com", "Remote", "Worldwide"),
    ("Materialize Soft", "materialize.com", "Remote", "Worldwide"),
    ("RisingWave Soft", "risingwave.com", "Remote", "Worldwide"),
    ("Redpanda Soft", "redpanda.com", "Remote", "Worldwide"),
    ("UpCloud Soft", "upcloud.com", "Europe", "Helsinki"),
    ("Smartly Soft", "smartly.io", "Europe", "Helsinki"),
    ("Wolt Soft", "wolt.com", "Europe", "Helsinki"),
    ("Supercell Soft", "supercell.com", "Europe", "Helsinki"),
    ("Relex Soft", "relexsolutions.com", "Europe", "Helsinki"),
    ("Varjo Soft", "varjo.com", "Europe", "Helsinki"),
    ("Iceye Soft", "iceye.com", "Europe", "Helsinki"),
    ("Oura Soft", "ouraring.com", "Europe", "Oulu"),
    ("Nightingale Soft", "nightingale.health", "Europe", "Helsinki"),
    ("Canva Soft", "canva.com", "Australia", "Sydney"),
    ("Atlassian Soft", "atlassian.com", "Australia", "Sydney"),
    ("Xero Soft", "xero.com", "Australia", "Wellington"),
    ("Afterpay Soft", "afterpay.com", "Australia", "Melbourne"),
    ("Zip Soft", "zip.co", "Australia", "Sydney"),
    ("Wisetech Soft", "wisetechglobal.com", "Australia", "Sydney"),
    ("Employment Soft", "employmenthero.com", "Australia", "Sydney"),
    ("Deputy Soft", "deputy.com", "Australia", "Sydney"),
    ("Envato Soft", "envato.com", "Australia", "Melbourne"),
    ("Linktree Soft", "linktr.ee", "Australia", "Melbourne"),
    ("Culture Amp Soft", "cultureamp.com", "Australia", "Melbourne"),
    ("Campaign Soft", "campaignmonitor.com", "Australia", "Sydney"),
    ("Brighte Soft", "brighte.com.au", "Australia", "Sydney"),
    ("Prospa Soft", "prospa.com", "Australia", "Sydney"),
    ("Airwallex Soft", "airwallex.com", "Australia", "Melbourne"),
    ("Judo Soft", "judo.bank", "Australia", "Melbourne"),
    ("Titan Soft", "titan.finance", "Australia", "Sydney"),
    ("Canva Soft2", "canva.dev", "Australia", "Sydney"),
    ("SafetyCulture Soft2", "safetyculture.io", "Australia", "Sydney"),
    ("Seek Soft", "seek.com.au", "Australia", "Melbourne"),
    ("REA Soft", "rea-group.com", "Australia", "Melbourne"),
    ("Carsales Soft", "carsales.com.au", "Australia", "Melbourne"),
    ("Kogan Soft", "kogan.com", "Australia", "Melbourne"),
    ("Atlassian Soft2", "trello.com", "Australia", "Sydney"),
    ("Expert360 Soft", "expert360.com", "Australia", "Sydney"),
    ("Urbanise Soft", "urbanise.com", "Australia", "Sydney"),
    ("Ninja Soft", "ninjatech.ai", "Australia", "Sydney"),
    ("Harrison Soft", "harrison.ai", "Australia", "Sydney"),
    ("Propeller Soft", "propelleraero.com", "Australia", "Sydney"),
    ("Nearmap Soft", "nearmap.com", "Australia", "Sydney"),
    ("Morse Soft", "morse.io", "Australia", "Sydney"),
    ("Quantium Soft", "quantium.com", "Australia", "Sydney"),
    ("Tyro Soft", "tyro.com", "Australia", "Sydney"),
    ("Splitit Soft", "splitit.com", "Australia", "Melbourne"),
    ("Brighte Soft2", "brighte.com", "Australia", "Sydney"),
    ("Tabby Soft", "tabby.ai", "UAE", "Dubai"),
    ("Lean Soft", "leantech.me", "KSA", "Riyadh"),
    ("Unifonic Soft", "unifonic.com", "KSA", "Riyadh"),
    ("Floward Soft", "floward.com", "KSA", "Riyadh"),
    ("Salla Soft", "salla.sa", "KSA", "Riyadh"),
    ("Zid Soft", "zid.sa", "KSA", "Riyadh"),
    ("Moyasar Soft", "moyasar.com", "KSA", "Riyadh"),
    ("Nearpay Soft", "nearpay.io", "KSA", "Riyadh"),
    ("Anghami Soft", "anghami.com", "UAE", "Dubai"),
    ("Noon Soft", "noon.com", "UAE", "Dubai"),
    ("Presight Soft", "presight.ai", "UAE", "Abu Dhabi"),
    ("Core42 Soft", "core42.ai", "UAE", "Abu Dhabi"),
    ("Instabug Soft", "instabug.com", "Egypt", "Cairo"),
    ("Paymob Soft", "paymob.com", "Egypt", "Cairo"),
    ("MoneyFellows Soft", "moneyfellows.com", "Egypt", "Cairo"),
    ("Vezeeta Soft", "vezeeta.com", "Egypt", "Cairo"),
    ("Yassir Soft", "yassir.com", "MENA", "Algiers"),
    ("MyFatoorah Soft", "myfatoorah.com", "Kuwait", "Kuwait"),
    ("Spotii Soft", "spotii.com", "UAE", "Dubai"),
    ("Shufti Soft", "shuftipro.com", "UAE", "Dubai"),
    ("Namshi Soft", "namshi.com", "UAE", "Dubai"),
    ("Mumzworld Soft", "mumzworld.com", "UAE", "Dubai"),
    ("Pure Harvest Soft", "pureharvest.ag", "UAE", "Abu Dhabi"),
    ("Magnati Soft", "magnati.com", "UAE", "Dubai"),
    ("Network Soft", "network.ae", "UAE", "Dubai"),
    ("Al Ansari Soft", "alansariexchange.com", "UAE", "Dubai"),
    ("Pyypl Soft", "pyypl.com", "UAE", "Dubai"),
    ("Rain Soft", "rain.bh", "Bahrain", "Manama"),
    ("Benefit Soft", "benefit.bh", "Bahrain", "Manama"),
    ("QPay Soft", "qpay.qa", "Qatar", "Doha"),
    ("Snoonu Soft", "snoonu.com", "Qatar", "Doha"),
    ("Rafeeq Soft", "rafeeq.qa", "Qatar", "Doha"),
    ("Jeebly Soft", "jeebly.com", "UAE", "Dubai"),
    ("Fetchr Soft", "fetchr.com", "UAE", "Dubai"),
    ("Hungry Soft", "hungry.dk", "Europe", "Copenhagen"),
    ("Barq Soft", "barq.com", "KSA", "Riyadh"),
    ("Hungerstation Soft", "hungerstation.com", "KSA", "Riyadh"),
    ("Mobily Soft", "mobily.com.sa", "KSA", "Riyadh"),
    ("Zain Soft", "sa.zain.com", "KSA", "Riyadh"),
    ("Aramco Soft", "aramco.com", "KSA", "Dhahran"),
    ("Neom Soft", "neom.com", "KSA", "Neom"),
    ("Red Soft", "redseaglobal.com", "KSA", "Jeddah"),
    ("Qiddiya Soft", "qiddiya.com", "KSA", "Riyadh"),
    ("Elm Soft", "elm.sa", "KSA", "Riyadh"),
    ("Tawuniya Soft", "tawuniya.com", "KSA", "Riyadh"),
    ("Alinma Soft", "alinma.com", "KSA", "Riyadh"),
    ("Al Rajhi Soft", "alrajhibank.com.sa", "KSA", "Riyadh"),
    ("Snb Soft", "alahli.com", "KSA", "Jeddah"),
    ("Riyad Soft", "riyadbank.com", "KSA", "Riyadh"),
    ("Netsol Soft", "netsoltech.com", "Pakistan", "Lahore"),
    ("Tkxel Soft", "tkxel.com", "Pakistan", "Lahore"),
    ("Confiz Soft", "confiz.com", "Pakistan", "Lahore"),
    ("Tintash Soft", "tintash.com", "Pakistan", "Lahore"),
    ("Securiti Soft", "securiti.ai", "Pakistan", "Karachi"),
    ("Techlogix Soft", "techlogix.com", "Pakistan", "Lahore"),
    ("Inbox Soft", "inboxbiz.com", "Pakistan", "Lahore"),
    ("PakWheels Soft", "pakwheels.com", "Pakistan", "Lahore"),
    ("Foodpanda Soft", "foodpanda.pk", "Pakistan", "Karachi"),
    ("Jazz Soft", "jazz.com.pk", "Pakistan", "Islamabad"),
    ("Telenor Soft", "telenor.com.pk", "Pakistan", "Islamabad"),
    ("Ufone Soft", "ufone.com", "Pakistan", "Islamabad"),
    ("Airlift Soft", "airlift.com", "Pakistan", "Karachi"),
    ("Finja Soft", "finja.pk", "Pakistan", "Lahore"),
    ("PayPro Soft", "paypro.com.pk", "Pakistan", "Karachi"),
    ("Tagada Soft", "tagada.pk", "Pakistan", "Lahore"),
    ("Educative Soft", "educative.io", "Pakistan", "Islamabad"),
    ("Plane Soft", "plane.so", "Remote", "Worldwide"),
    ("Clubhouse Soft", "clubhouse.io", "Remote", "Worldwide"),
    ("Basecamp Soft", "basecamp.com", "Remote", "Worldwide"),
    ("Hey Soft", "hey.com", "Remote", "Worldwide"),
    ("37signals Soft", "37signals.com", "Remote", "Worldwide"),
    ("Ghost Soft", "ghost.org", "Remote", "Worldwide"),
    ("Beehiiv Soft", "beehiiv.com", "Remote", "Worldwide"),
    ("Substack Soft", "substack.com", "Remote", "Worldwide"),
    ("Buttondown Soft", "buttondown.com", "Remote", "Worldwide"),
    ("Customer Soft", "customer.io", "Remote", "Worldwide"),
    ("Klaviyo Soft", "klaviyo.com", "Remote", "Worldwide"),
    ("Attentive Soft", "attentive.com", "Remote", "Worldwide"),
    ("Pushwoosh Soft", "pushwoosh.com", "Remote", "Worldwide"),
    ("MoEngage Soft", "moengage.com", "Remote", "Worldwide"),
    ("Mixpanel Soft", "mixpanel.com", "Remote", "Worldwide"),
    ("FullStory Soft", "fullstory.com", "Remote", "Worldwide"),
    ("Kameleoon Soft", "kameleoon.com", "Europe", "Paris"),
    ("Didomi Soft", "didomi.io", "Europe", "Paris"),
    ("Spendesk Soft", "spendesk.com", "Europe", "Paris"),
    ("Memo Soft", "memo.bank", "Europe", "Paris"),
    ("Shine Soft", "shine.fr", "Europe", "Paris"),
    ("Leboncoin Soft", "leboncoin.fr", "Europe", "Paris"),
    ("Veepee Soft", "veepee.com", "Europe", "Paris"),
    ("Dataiku Soft", "dataiku.com", "Europe", "Paris"),
    ("Criteo Soft", "criteo.com", "Europe", "Paris"),
    ("Datadog Soft", "datadoghq.com", "Europe", "Paris"),
    ("Intercom Soft", "intercom.com", "Remote", "Worldwide"),
    ("Zendesk Soft", "zendesk.com", "Remote", "Worldwide"),
    ("Freshworks Soft", "freshworks.com", "Remote", "Worldwide"),
    ("Kustomer Soft", "kustomer.com", "Remote", "Worldwide"),
    ("Dixa Soft", "dixa.com", "Europe", "Copenhagen"),
    ("Gladly Soft", "gladly.com", "Remote", "Worldwide"),
    ("Ada Soft", "ada.cx", "Remote", "Worldwide"),
    ("Forethought Soft", "forethought.ai", "Remote", "Worldwide"),
    ("Sierra Soft", "sierra.ai", "Remote", "Worldwide"),
    ("Decagon Soft", "decagon.ai", "Remote", "Worldwide"),
    ("Writer Soft", "writer.com", "Remote", "Worldwide"),
    ("Jasper Soft", "jasper.ai", "Remote", "Worldwide"),
    ("Copy Soft", "copy.ai", "Remote", "Worldwide"),
    ("Grammarly Soft", "grammarly.com", "Remote", "Worldwide"),
    ("Notion Soft", "notion.so", "Remote", "Worldwide"),
    ("Coda Soft", "coda.io", "Remote", "Worldwide"),
    ("Smartsheet Soft", "smartsheet.com", "Remote", "Worldwide"),
    ("Asana Soft", "asana.com", "Remote", "Worldwide"),
    ("Wrike Soft", "wrike.com", "Remote", "Worldwide"),
    ("Teamwork Soft", "teamwork.com", "Europe", "Cork"),
    ("Figma Soft", "figma.com", "Remote", "Worldwide"),
    ("Marvel Soft", "marvelapp.com", "Europe", "Dublin"),
    ("Penpot Soft", "penpot.app", "Europe", "Madrid"),
    ("Softr Soft", "softr.io", "Europe", "Berlin"),
    ("Appsmith Soft", "appsmith.com", "Remote", "Worldwide"),
    ("Tooljet Soft", "tooljet.com", "Remote", "Worldwide"),
    ("Superblocks Soft", "superblocks.com", "Remote", "Worldwide"),
    ("Internal Soft", "internal.io", "Remote", "Worldwide"),
    ("Airplane Soft", "airplane.dev", "Remote", "Worldwide"),
    ("Windmill Soft", "windmill.dev", "Europe", "Paris"),
    ("Trigger Soft", "trigger.dev", "Remote", "Worldwide"),
    ("Prefect Soft", "prefect.io", "Remote", "Worldwide"),
    ("Dagster Soft", "dagster.io", "Remote", "Worldwide"),
    ("Astronomer Soft", "astronomer.io", "Remote", "Worldwide"),
    ("dbt Soft", "getdbt.com", "Remote", "Worldwide"),
    ("Fivetran Soft", "fivetran.com", "Remote", "Worldwide"),
    ("Airbyte Soft", "airbyte.com", "Remote", "Worldwide"),
    ("Stitch Soft", "stitchdata.com", "Remote", "Worldwide"),
    ("Segment Soft", "segment.com", "Remote", "Worldwide"),
    ("Rudderstack Soft", "rudderstack.com", "Remote", "Worldwide"),
    ("Census Soft", "getcensus.com", "Remote", "Worldwide"),
    ("Hex Soft", "hex.tech", "Remote", "Worldwide"),
    ("Mode Soft", "mode.com", "Remote", "Worldwide"),
    ("Sigma Soft", "sigmacomputing.com", "Remote", "Worldwide"),
    ("ThoughtSpot Soft", "thoughtspot.com", "Remote", "Worldwide"),
    ("Superset Soft", "apachesuperset.com", "Remote", "Worldwide"),
    ("Lightdash Soft", "lightdash.com", "Remote", "Worldwide"),
    ("Evidence Soft", "evidence.dev", "Remote", "Worldwide"),
    ("Observable Soft", "observablehq.com", "Remote", "Worldwide"),
    ("Observable Soft2", "observable.dev", "Remote", "Worldwide"),
    ("Deepnote Soft", "deepnote.com", "Remote", "Worldwide"),
    ("Modal Soft", "modal.com", "Remote", "Worldwide"),
    ("Replicate Soft", "replicate.com", "Remote", "Worldwide"),
    ("Together Soft", "together.ai", "Remote", "Worldwide"),
    ("Anyscale Soft", "anyscale.com", "Remote", "Worldwide"),
    ("Baseten Soft", "baseten.co", "Remote", "Worldwide"),
    ("RunPod Soft", "runpod.io", "Remote", "Worldwide"),
    ("CoreWeave Soft", "coreweave.com", "Remote", "Worldwide"),
    ("Vast Soft", "vast.ai", "Remote", "Worldwide"),
    ("Paperspace Soft", "paperspace.com", "Remote", "Worldwide"),
    ("Hugging Soft", "huggingface.co", "Remote", "Worldwide"),
    ("Cohere Soft", "cohere.com", "Remote", "Worldwide"),
    ("Stability Soft", "stability.ai", "Europe", "London"),
    ("Luma Soft", "lumalabs.ai", "Remote", "Worldwide"),
    ("Suno Soft", "suno.com", "Remote", "Worldwide"),
    ("Udio Soft", "udio.com", "Remote", "Worldwide"),
    ("Fireflies Soft", "fireflies.ai", "Remote", "Worldwide"),
    ("Grain Soft", "grain.com", "Remote", "Worldwide"),
    ("Fathom Soft", "fathom.video", "Remote", "Worldwide"),
    ("tl;dv Soft", "tldv.io", "Europe", "Berlin"),
    ("Chorus Soft", "chorus.ai", "Remote", "Worldwide"),
    ("Clari Soft", "clari.com", "Remote", "Worldwide"),
    ("Salesloft Soft", "salesloft.com", "Remote", "Worldwide"),
    ("ZoomInfo Soft", "zoominfo.com", "Remote", "Worldwide"),
    ("Clearbit Soft", "clearbit.com", "Remote", "Worldwide"),
    ("Clay Soft", "clay.com", "Remote", "Worldwide"),
    ("Common Soft", "commonroom.io", "Remote", "Worldwide"),
    ("Pocus Soft", "pocus.com", "Remote", "Worldwide"),
    ("Warmly Soft", "warmly.ai", "Remote", "Worldwide"),
    ("6sense Soft", "6sense.com", "Remote", "Worldwide"),
    ("Bombora Soft", "bombora.com", "Remote", "Worldwide"),
    ("Drift Soft", "drift.com", "Remote", "Worldwide"),
    ("Qualified Soft", "qualified.com", "Remote", "Worldwide"),
    ("Calendly Soft", "calendly.com", "Remote", "Worldwide"),
    ("SavvyCal Soft", "savvycal.com", "Remote", "Worldwide"),
    ("Once Soft", "oncehub.com", "Remote", "Worldwide"),
    ("YouCanBook Soft", "youcanbook.me", "Europe", "London"),
    ("TidyCal Soft", "tidycal.com", "Remote", "Worldwide"),
    ("Superhuman Soft", "superhuman.com", "Remote", "Worldwide"),
    ("Shortwave Soft", "shortwave.com", "Remote", "Worldwide"),
    ("Missive Soft", "missiveapp.com", "Remote", "Worldwide"),
    ("Hiver Soft", "hiverhq.com", "Remote", "Worldwide"),
    ("Gmelius Soft", "gmelius.com", "Europe", "Geneva"),
    ("Boomerang Soft", "boomeranggmail.com", "Remote", "Worldwide"),
    ("SaneBox Soft", "sanebox.com", "Remote", "Worldwide"),
    ("Clean Soft", "clean.email", "Remote", "Worldwide"),
    ("Newton Soft", "newtonhq.com", "Remote", "Worldwide"),
    ("Tutanota Soft", "tutanota.com", "Europe", "Hannover"),
    ("Fastmail Soft", "fastmail.com", "Australia", "Melbourne"),
    ("Mailgun Soft", "mailgun.com", "Remote", "Worldwide"),
    ("SendGrid Soft", "sendgrid.com", "Remote", "Worldwide"),
    ("Amazon SES Soft", "amazonaws.com", "Remote", "Worldwide"),
    ("Loops Soft", "loops.so", "Remote", "Worldwide"),
    ("Mailchimp Soft", "mailchimp.com", "Remote", "Worldwide"),
    ("Drip Soft", "drip.com", "Remote", "Worldwide"),
    ("Active Soft", "activecampaign.com", "Remote", "Worldwide"),
    ("GetResponse Soft", "getresponse.com", "Europe", "Gdansk"),
    ("AWeber Soft", "aweber.com", "Remote", "Worldwide"),
    ("Wordpress Soft", "wordpress.com", "Remote", "Worldwide"),
    ("Kinsta Soft", "kinsta.com", "Remote", "Worldwide"),
    ("Flywheel Soft", "getflywheel.com", "Remote", "Worldwide"),
    ("Pantheon Soft", "pantheon.io", "Remote", "Worldwide"),
    ("Acquia Soft", "acquia.com", "Remote", "Worldwide"),
    ("Netlify Soft", "netlify.com", "Remote", "Worldwide"),
    ("Fastly Soft", "fastly.com", "Remote", "Worldwide"),
    ("KeyCDN Soft", "keycdn.com", "Europe", "Zug"),
    ("StackPath Soft", "stackpath.com", "Remote", "Worldwide"),
    ("DigitalOcean Soft", "digitalocean.com", "Remote", "Worldwide"),
    ("Linode Soft", "linode.com", "Remote", "Worldwide"),
    ("Vultr Soft", "vultr.com", "Remote", "Worldwide"),
    ("OVH Soft", "ovhcloud.com", "Europe", "Roubaix"),
    ("Scaleway Soft", "scaleway.com", "Europe", "Paris"),
    ("Exoscale Soft", "exoscale.com", "Europe", "Lausanne"),
    ("Railway Soft", "railway.app", "Remote", "Worldwide"),
    ("Porter Soft", "porter.run", "Remote", "Worldwide"),
    ("Doppler Soft", "doppler.com", "Remote", "Worldwide"),
    ("Infisical Soft", "infisical.com", "Remote", "Worldwide"),
    ("1Password Soft", "1password.com", "Remote", "Worldwide"),
    ("Bitwarden Soft", "bitwarden.com", "Remote", "Worldwide"),
    ("LastPass Soft", "lastpass.com", "Remote", "Worldwide"),
    ("Okta Soft", "okta.com", "Remote", "Worldwide"),
    ("Auth0 Soft", "auth0.com", "Remote", "Worldwide"),
    ("FusionAuth Soft", "fusionauth.io", "Remote", "Worldwide"),
    ("Descope Soft", "descope.com", "Remote", "Worldwide"),
    ("PropelAuth Soft", "propelauth.com", "Remote", "Worldwide"),
    ("PlanetScale Soft", "planetscale.com", "Remote", "Worldwide"),
    ("Xata Soft", "xata.io", "Remote", "Worldwide"),
    ("Fauna Soft", "fauna.com", "Remote", "Worldwide"),
    ("Appwrite Soft", "appwrite.io", "Remote", "Worldwide"),
    ("Hasura Soft", "hasura.io", "Remote", "Worldwide"),
    ("Prisma Soft", "prisma.io", "Remote", "Worldwide"),
    ("Drizzle Soft", "drizzle.team", "Remote", "Worldwide"),
    ("Convex Soft", "convex.dev", "Remote", "Worldwide"),
    ("Instant Soft", "instantdb.com", "Remote", "Worldwide"),
    ("Firebase Soft", "firebase.google.com", "Remote", "Worldwide"),
    ("Amplify Soft", "amplify.aws", "Remote", "Worldwide"),
    ("Appwrite Soft2", "cloud.appwrite.io", "Remote", "Worldwide"),
    ("Backendless Soft", "backendless.com", "Remote", "Worldwide"),
    ("Kinvey Soft", "progress.com", "Remote", "Worldwide"),
    ("OutSystems Soft", "outsystems.com", "Europe", "Lisbon"),
    ("Mendix Soft", "mendix.com", "Europe", "Rotterdam"),
    ("Betty Soft", "bettyblocks.com", "Europe", "Alkmaar"),
    ("Adalo Soft", "adalo.com", "Remote", "Worldwide"),
    ("Thunkable Soft", "thunkable.com", "Remote", "Worldwide"),
    ("FlutterFlow Soft", "flutterflow.io", "Remote", "Worldwide"),
    ("Draftbit Soft", "draftbit.com", "Remote", "Worldwide"),
    ("DronaHQ Soft", "dronahq.com", "Remote", "Worldwide"),
    ("NocoDB Soft", "nocodb.com", "Remote", "Worldwide"),
    ("Rowy Soft", "rowy.io", "Remote", "Worldwide"),
    ("Directus Soft", "directus.io", "Remote", "Worldwide"),
    ("Strapi Soft", "strapi.io", "Europe", "Paris"),
    ("Storyblok Soft", "storyblok.com", "Europe", "Linz"),
    ("Prismic Soft", "prismic.io", "Europe", "Paris"),
    ("Hygraph Soft", "hygraph.com", "Europe", "Berlin"),
    ("Tina Soft", "tina.io", "Remote", "Worldwide"),
    ("Keystatic Soft", "keystatic.com", "Remote", "Worldwide"),
    ("Payload Soft", "payloadcms.com", "Remote", "Worldwide"),
    ("Hashnode Soft", "hashnode.com", "Remote", "Worldwide"),
    ("Dev Soft", "dev.to", "Remote", "Worldwide"),
    ("Mirror Soft", "mirror.xyz", "Remote", "Worldwide"),
    ("Paragraph Soft", "paragraph.xyz", "Remote", "Worldwide"),
    ("Cascade Soft", "cascade.app", "Europe", "London"),
    ("Deel Soft", "deel.com", "Remote", "Worldwide"),
    ("Remote Soft", "remote.com", "Remote", "Worldwide"),
    ("Multiplier Soft", "usemultiplier.com", "Remote", "Worldwide"),
    ("Omnipresent Soft", "omnipresent.com", "Europe", "London"),
    ("Atlas Soft", "atlas.co", "Remote", "Worldwide"),
    ("Gusto Soft", "gusto.com", "Remote", "Worldwide"),
    ("TriNet Soft", "trinet.com", "Remote", "Worldwide"),
    ("ADP Soft", "adp.com", "Remote", "Worldwide"),
    ("Workday Soft", "workday.com", "Remote", "Worldwide"),
    ("BambooHR Soft", "bamboohr.com", "Remote", "Worldwide"),
    ("UKG Soft", "ukg.com", "Remote", "Worldwide"),
    ("Ceridian Soft", "ceridian.com", "Remote", "Worldwide"),
    ("Paychex Soft", "paychex.com", "Remote", "Worldwide"),
    ("Paylocity Soft", "paylocity.com", "Remote", "Worldwide"),
    ("Paycom Soft", "paycom.com", "Remote", "Worldwide"),
    ("Namely Soft", "namely.com", "Remote", "Worldwide"),
    ("15Five Soft", "15five.com", "Remote", "Worldwide"),
    ("Peakon Soft", "peakon.com", "Europe", "Copenhagen"),
    ("Officevibe Soft", "officevibe.com", "Remote", "Worldwide"),
    ("Leapsome Soft", "leapsome.com", "Europe", "Berlin"),
    ("Small Soft", "small-improvements.com", "Europe", "Berlin"),
    ("Impraise Soft", "impraise.com", "Europe", "Amsterdam"),
    ("Reflektive Soft", "reflektive.com", "Remote", "Worldwide"),
    ("CoachHub Soft", "coachhub.com", "Europe", "Berlin"),
    ("Torch Soft", "torch.io", "Remote", "Worldwide"),
    ("Sounding Soft", "soundingboardinc.com", "Remote", "Worldwide"),

]


def clean_name(name: str) -> str:
    parts = name.split()
    while parts and parts[-1] in SUFFIX:
        parts.pop()
    return " ".join(parts) if parts else name


def main() -> None:
    sent_e: set[str] = set()
    sent_c: set[str] = set()
    sent_d: set[str] = set()
    for r in csv.DictReader(open(ROOT / "outreach/sent_log.csv", encoding="utf-8-sig")):
        if r.get("status") != "sent":
            continue
        e = (r.get("email") or "").lower()
        c = (r.get("company") or "").strip().lower()
        sent_e.add(e)
        if c and c != "test":
            sent_c.add(c)
        if "@" in e:
            sent_d.add(e.split("@", 1)[1])
    for p in (
        ROOT / "output/emails_shortlist_batch45_2026-08-17.csv",
        ROOT / "output/emails_shortlist_batch46_2026-08-17.csv",
    ):
        if not p.exists():
            continue
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            e = (r.get("HR / Recruiter Email") or "").lower()
            c = (r.get("Company") or "").strip().lower()
            sent_e.add(e)
            sent_c.add(c)
            if "@" in e:
                sent_d.add(e.split("@", 1)[1])

    cache = _load_csv_map(CACHE)
    dead = {e.split("@", 1)[1] for e, st in cache.items() if "@" in e and st in DEAD}
    probed: dict[str, set[str]] = defaultdict(set)
    for email in cache:
        if "@" in email:
            loc, dom = email.split("@", 1)
            probed[dom].add(loc)
    bounces = bounced_emails()

    seen: set[str] = set()
    fresh = []
    for name, domain, region, city in NEW:
        domain = domain.lower()
        if domain in sent_d or domain in dead or domain in seen:
            continue
        base = clean_name(name).lower()
        if any(b in base for b in BLOCKED):
            continue
        if base in sent_c or any(
            base == c or (len(base) > 4 and (base in c or c in base)) for c in sent_c
        ):
            continue
        seen.add(domain)
        missing = [
            loc
            for loc in TRY
            if loc not in probed[domain]
            and f"{loc}@{domain}" not in sent_e
            and f"{loc}@{domain}" not in bounces
            and cache.get(f"{loc}@{domain}") not in DONE
        ]
        if not missing:
            continue
        fresh.append((region, name, domain, city, missing[:5]))

    print("pre-mx", len(fresh), flush=True)
    plan = []
    for region, name, domain, city, locs in fresh:
        try:
            hosts = mx_hosts(domain)
        except Exception:
            hosts = []
        mxblob = " ".join(hosts).lower()
        if not any(t in mxblob for t in GOOD_MX):
            continue
        pri = (
            -2
            if region in {"Pakistan"}
            else -1
            if region in {"Kuwait", "Australia", "UAE", "KSA", "Egypt", "Jordan", "Bahrain", "Qatar", "MENA"}
            else 0
        )
        plan.append((pri, region, name, domain, city, locs))
    plan = sorted(plan)
    print("plan", len(plan), flush=True)

    out = ROOT / "output/emails_shortlist_batch47_2026-08-17.csv"
    fields = [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Other Emails", "Domain", "Careers / Apply URL", "Sample Role", "SMTP Verification",
    ]
    found = []
    stats: Counter[str] = Counter()

    def flush() -> None:
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(found)

    target = 40
    for i, (_, region, name, domain, city, locs) in enumerate(plan, 1):
        if len(found) >= target:
            print("hit", target, flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(plan)}] {email}", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.28)
            if ok:
                stats["ok"] += 1
                print("  OK", flush=True)
                found.append(
                    {
                        "Company": clean_name(name),
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
                flush()
                break
            tag = "catch-all" if "catch-all" in detail.lower() else "fail"
            stats[tag] += 1
            print(f"  NO {tag}", flush=True)
            if tag == "catch-all":
                break

    flush()
    print("STATS", dict(stats), "rows", len(found), flush=True)
    for r in found:
        print(f"  {r['HR / Recruiter Email']:40} {r['Company']} [{r['Region']}]", flush=True)


if __name__ == "__main__":
    main()
