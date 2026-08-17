#!/usr/bin/env python3
"""Probe batch43: fresh Google/Proofpoint hiring aliases for 2026-08-16 evening send."""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "outreach"))
from smtp_verify import CACHE, _load_csv_map, bounced_emails, mx_hosts, verify_mailbox  # noqa: E402

TRY = ["careers", "hr", "jobs", "people", "recruiting", "talent", "hiring", "join"]
GOOD_MX = (
    "google",
    "gmail",
    "googlemail",
    "aspmx",
    "larksuite",
    "lark",
    "feishu",
    "pphosted",
    "proofpoint",
    "mimecast",
)
SUFFIX = {"Soft", "Soft2", "Soft3", "HQ"}
BLOCKED = {
    "huggingface",
    "hugging face",
    "n8n",
    "openai",
    "anthropic",
    "vercel",
    "cloudflare",
    "airtable",
    "stripe",
    "gitlab",
    "canonical",
    "automattic",
    "toptal",
    "andela",
    "lemon.io",
    "launchdarkly",
    "character",
}
DEAD = {"catch-all", "no-mx", "probe-blocked"}
DONE = DEAD | {"invalid", "reject", "bounce", "accept-then-unknown", "strict-valid"}

NEW = [
    ("Systems Soft", "systems.ltd", "Pakistan", "Karachi"),
    ("Netsol Soft", "netsoltech.com", "Pakistan", "Lahore"),
    ("10Pearls Soft", "10pearls.com", "Pakistan", "Karachi"),
    ("Arbisoft Soft", "arbisoft.com", "Pakistan", "Lahore"),
    ("Tkxel Soft", "tkxel.com", "Pakistan", "Lahore"),
    ("Folio Soft", "folio3.com", "Pakistan", "Karachi"),
    ("Confiz Soft", "confiz.com", "Pakistan", "Lahore"),
    ("Venture Soft", "venturedive.com", "Pakistan", "Karachi"),
    ("Tintash Soft", "tintash.com", "Pakistan", "Lahore"),
    ("Emumba Soft", "emumba.com", "Pakistan", "Islamabad"),
    ("Securiti Soft", "securiti.ai", "Pakistan", "Karachi"),
    ("Afiniti Soft", "afiniti.com", "Pakistan", "Islamabad"),
    ("Careem Soft", "careem.com", "UAE", "Dubai"),
    ("Tabby Soft", "tabby.ai", "UAE", "Dubai"),
    ("Tamara Soft", "tamara.co", "KSA", "Riyadh"),
    ("Bayzat Soft", "bayzat.com", "UAE", "Dubai"),
    ("Foodics Soft", "foodics.com", "KSA", "Riyadh"),
    ("Noon Soft", "noon.com", "UAE", "Dubai"),
    ("Anghami Soft", "anghami.com", "UAE", "Dubai"),
    ("Jahez Soft", "jahez.net", "KSA", "Riyadh"),
    ("Mrsool Soft", "mrsool.com", "KSA", "Riyadh"),
    ("Sary Soft", "sary.com", "KSA", "Riyadh"),
    ("Lean Soft", "leantech.me", "KSA", "Riyadh"),
    ("Unifonic Soft", "unifonic.com", "KSA", "Riyadh"),
    ("Floward Soft", "floward.com", "KSA", "Riyadh"),
    ("Salla Soft", "salla.sa", "KSA", "Riyadh"),
    ("Zid Soft", "zid.sa", "KSA", "Riyadh"),
    ("Moyasar Soft", "moyasar.com", "KSA", "Riyadh"),
    ("Nearpay Soft", "nearpay.io", "KSA", "Riyadh"),
    ("Talabat Soft", "talabat.com", "UAE", "Dubai"),
    ("G42 Soft", "g42.ai", "UAE", "Abu Dhabi"),
    ("Presight Soft", "presight.ai", "UAE", "Abu Dhabi"),
    ("Core42 Soft", "core42.ai", "UAE", "Abu Dhabi"),
    ("Instabug Soft", "instabug.com", "Egypt", "Cairo"),
    ("Paymob Soft", "paymob.com", "Egypt", "Cairo"),
    ("Telda Soft", "telda.com", "Egypt", "Cairo"),
    ("Halan Soft", "halan.com", "Egypt", "Cairo"),
    ("Swvl Soft", "swvl.com", "Egypt", "Cairo"),
    ("MoneyFellows Soft", "moneyfellows.com", "Egypt", "Cairo"),
    ("Vezeeta Soft", "vezeeta.com", "Egypt", "Cairo"),
    ("MaxAB Soft", "maxab.com", "Egypt", "Cairo"),
    ("Breadfast Soft", "breadfast.com", "Egypt", "Cairo"),
    ("Yassir Soft", "yassir.com", "MENA", "Algiers"),
    ("Paystack Soft", "paystack.com", "MENA", "Lagos"),
    ("Jumia Soft", "jumia.com", "MENA", "Lagos"),
    ("MyFatoorah Soft", "myfatoorah.com", "Kuwait", "Kuwait"),
    ("Tap Soft", "tap.company", "Kuwait", "Kuwait"),
    ("Canva Soft", "canva.com", "Australia", "Sydney"),
    ("Atlassian Soft", "atlassian.com", "Australia", "Sydney"),
    ("Xero Soft", "xero.com", "Australia", "Wellington"),
    ("Afterpay Soft", "afterpay.com", "Australia", "Melbourne"),
    ("Zip Soft", "zip.co", "Australia", "Sydney"),
    ("Wisetech Soft", "wisetechglobal.com", "Australia", "Sydney"),
    ("Iress Soft", "iress.com", "Australia", "Melbourne"),
    ("Carsales Soft", "carsales.com.au", "Australia", "Melbourne"),
    ("Domain Soft", "domain.com.au", "Australia", "Sydney"),
    ("Qantas Soft", "qantas.com", "Australia", "Sydney"),
    ("Telstra Soft", "telstra.com.au", "Australia", "Melbourne"),
    ("Optus Soft", "optus.com.au", "Australia", "Sydney"),
    ("CBA Soft", "commbank.com.au", "Australia", "Sydney"),
    ("NAB Soft", "nab.com.au", "Australia", "Melbourne"),
    ("ANZ Soft", "anz.com.au", "Australia", "Melbourne"),
    ("Westpac Soft", "westpac.com.au", "Australia", "Sydney"),
    ("Employment Soft", "employmenthero.com", "Australia", "Sydney"),
    ("Deputy Soft", "deputy.com", "Australia", "Sydney"),
    ("Safety Soft", "safetyculture.com", "Australia", "Sydney"),
    ("Buildkite Soft", "buildkite.com", "Australia", "Melbourne"),
    ("Envato Soft", "envato.com", "Australia", "Melbourne"),
    ("Linktree Soft", "linktr.ee", "Australia", "Melbourne"),
    ("Immutable Soft", "immutable.com", "Australia", "Sydney"),
    ("SiteMinder Soft", "siteminder.com", "Australia", "Sydney"),
    ("Airtasker Soft", "airtasker.com", "Australia", "Sydney"),
    ("Up Soft", "up.com.au", "Australia", "Melbourne"),
    ("Judo Soft", "judo.bank", "Australia", "Melbourne"),
    ("Revolut Soft", "revolut.com", "Europe", "London"),
    ("Wise Soft", "wise.com", "Europe", "London"),
    ("Monzo Soft", "monzo.com", "Europe", "London"),
    ("Starling Soft", "starlingbank.com", "Europe", "London"),
    ("Checkout Soft", "checkout.com", "Europe", "London"),
    ("Klarna Soft", "klarna.com", "Europe", "Stockholm"),
    ("Spotify Soft", "spotify.com", "Europe", "Stockholm"),
    ("N26 Soft", "n26.com", "Europe", "Berlin"),
    ("Trade Soft", "traderepublic.com", "Europe", "Berlin"),
    ("Celonis Soft", "celonis.com", "Europe", "Munich"),
    ("Personio Soft", "personio.com", "Europe", "Munich"),
    ("Delivery Soft", "deliveryhero.com", "Europe", "Berlin"),
    ("HelloFresh Soft", "hellofresh.com", "Europe", "Berlin"),
    ("Zalando Soft", "zalando.com", "Europe", "Berlin"),
    ("Adyen Soft", "adyen.com", "Europe", "Amsterdam"),
    ("Mollie Soft", "mollie.com", "Europe", "Amsterdam"),
    ("Miro Soft", "miro.com", "Europe", "Amsterdam"),
    ("Bolt Soft", "bolt.eu", "Europe", "Tallinn"),
    ("Veriff Soft", "veriff.com", "Europe", "Tallinn"),
    ("Pipedrive Soft", "pipedrive.com", "Europe", "Tallinn"),
    ("Vinted Soft", "vinted.com", "Europe", "Vilnius"),
    ("Wolt Soft", "wolt.com", "Europe", "Helsinki"),
    ("Aiven Soft", "aiven.io", "Europe", "Helsinki"),
    ("DeepL Soft", "deepl.com", "Europe", "Cologne"),
    ("Typeform Soft", "typeform.com", "Europe", "Barcelona"),
    ("Glovo Soft", "glovoapp.com", "Europe", "Barcelona"),
    ("Travelperk Soft", "travelperk.com", "Europe", "Barcelona"),
    ("Factorial Soft", "factorialhr.com", "Europe", "Barcelona"),
    ("Alan Soft", "alan.com", "Europe", "Paris"),
    ("Doctolib Soft", "doctolib.com", "Europe", "Paris"),
    ("Qonto Soft", "qonto.com", "Europe", "Paris"),
    ("Ledger Soft", "ledger.com", "Europe", "Paris"),
    ("BlaBlaCar Soft", "blablacar.com", "Europe", "Paris"),
    ("Back Market Soft", "backmarket.com", "Europe", "Paris"),
    ("Photoroom Soft", "photoroom.com", "Europe", "Paris"),
    ("Mistral Soft", "mistral.ai", "Europe", "Paris"),
    ("Hibob Soft", "hibob.com", "Europe", "London"),
    ("Synthesia Soft", "synthesia.io", "Europe", "London"),
    ("Wayve Soft", "wayve.ai", "Europe", "London"),
    ("Stability Soft", "stability.ai", "Europe", "London"),
    ("GoCardless Soft", "gocardless.com", "Europe", "London"),
    ("TrueLayer Soft", "truelayer.com", "Europe", "London"),
    ("Codat Soft", "codat.io", "Europe", "London"),
    ("Form3 Soft", "form3.tech", "Europe", "London"),
    ("Tide Soft", "tide.co", "Europe", "London"),
    ("OakNorth Soft", "oaknorth.com", "Europe", "London"),
    ("Curve Soft", "curve.com", "Europe", "London"),
    ("Skyscanner Soft", "skyscanner.net", "Europe", "Edinburgh"),
    ("Trainline Soft", "thetrainline.com", "Europe", "London"),
    ("Citymapper Soft", "citymapper.com", "Europe", "London"),
    ("GetYourGuide Soft", "getyourguide.com", "Europe", "Berlin"),
    ("Contentful Soft", "contentful.com", "Europe", "Berlin"),
    ("Adjust Soft", "adjust.com", "Europe", "Berlin"),
    ("Flix Soft", "flixbus.com", "Europe", "Munich"),
    ("Sennder Soft", "sennder.com", "Europe", "Berlin"),
    ("Auto1 Soft", "auto1.com", "Europe", "Berlin"),
    ("Omio Soft", "omio.com", "Europe", "Berlin"),
    ("Wefox Soft", "wefox.com", "Europe", "Berlin"),
    ("JetBrains Soft", "jetbrains.com", "Europe", "Prague"),
    ("Kiwi Soft", "kiwi.com", "Europe", "Prague"),
    ("Rohlik Soft", "rohlik.cz", "Europe", "Prague"),
    ("Make Soft", "make.com", "Europe", "Prague"),
    ("Bitpanda Soft", "bitpanda.com", "Europe", "Vienna"),
    ("GoStudent Soft", "gostudent.org", "Europe", "Vienna"),
    ("TourRadar Soft", "tourradar.com", "Europe", "Vienna"),
    ("Beekeeper Soft", "beekeeper.io", "Europe", "Zurich"),
    ("Scandit Soft", "scandit.com", "Europe", "Zurich"),
    ("Proton Soft", "proton.me", "Europe", "Geneva"),
    ("Sonar Soft", "sonarsource.com", "Europe", "Geneva"),
    ("Kahoot Soft", "kahoot.com", "Europe", "Oslo"),
    ("Sanity Soft", "sanity.io", "Europe", "Oslo"),
    ("Schibsted Soft", "schibsted.com", "Europe", "Oslo"),
    ("Oda Soft", "oda.com", "Europe", "Oslo"),
    ("Allegro Soft", "allegro.pl", "Europe", "Warsaw"),
    ("Docplanner Soft", "docplanner.com", "Europe", "Warsaw"),
    ("Booksy Soft", "booksy.com", "Europe", "Warsaw"),
    ("Brainly Soft", "brainly.com", "Europe", "Krakow"),
    ("Endava Soft", "endava.com", "Europe", "London"),
    ("Elliptic Soft", "elliptic.co", "Europe", "London"),
    ("Graphcore Soft", "graphcore.ai", "Europe", "Bristol"),
    ("Iwoca Soft", "iwoca.co.uk", "Europe", "London"),
    ("Pleo Soft", "pleo.io", "Europe", "Copenhagen"),
    ("Trustpilot Soft", "trustpilot.com", "Europe", "Copenhagen"),
    ("Too Good Soft", "toogoodtogo.com", "Europe", "Copenhagen"),
    ("Vivino Soft", "vivino.com", "Europe", "Copenhagen"),
    ("Lunar Soft", "lunar.app", "Europe", "Aarhus"),
    ("Northvolt Soft", "northvolt.com", "Europe", "Stockholm"),
    ("Epidemic Soft", "epidemicsound.com", "Europe", "Stockholm"),
    ("Trustly Soft", "trustly.com", "Europe", "Stockholm"),
    ("Tink Soft", "tink.com", "Europe", "Stockholm"),
    ("Voi Soft", "voi.com", "Europe", "Stockholm"),
    ("TransferGo Soft", "transfergo.com", "Europe", "Vilnius"),
    ("Nord Soft", "nordsecurity.com", "Europe", "Vilnius"),
    ("Iceye Soft", "iceye.com", "Europe", "Helsinki"),
    ("Relex Soft", "relexsolutions.com", "Europe", "Helsinki"),
    ("Smartly Soft", "smartly.io", "Europe", "Helsinki"),
    ("Supercell Soft", "supercell.com", "Europe", "Helsinki"),
    ("MessageBird Soft", "messagebird.com", "Europe", "Amsterdam"),
    ("Bunq Soft", "bunq.com", "Europe", "Amsterdam"),
    ("Picnic Soft", "picnic.app", "Europe", "Amsterdam"),
    ("WeTransfer Soft", "wetransfer.com", "Europe", "Amsterdam"),
    ("TomTom Soft", "tomtom.com", "Europe", "Amsterdam"),
    ("Backbase Soft", "backbase.com", "Europe", "Amsterdam"),
    ("Mambu Soft", "mambu.com", "Europe", "Amsterdam"),
    ("Criteo Soft", "criteo.com", "Europe", "Paris"),
    ("PayFit Soft", "payfit.com", "Europe", "Paris"),
    ("Spendesk Soft", "spendesk.com", "Europe", "Paris"),
    ("Sorare Soft", "sorare.com", "Europe", "Paris"),
    ("Pigment Soft", "pigment.com", "Europe", "Paris"),
    ("Aircall Soft", "aircall.io", "Europe", "Paris"),
    ("Contentsquare Soft", "contentsquare.com", "Europe", "Paris"),
    ("Mirakl Soft", "mirakl.com", "Europe", "Paris"),
    ("ManoMano Soft", "manomano.com", "Europe", "Paris"),
    ("Swile Soft", "swile.co", "Europe", "Paris"),
    ("Pennylane Soft", "pennylane.com", "Europe", "Paris"),
    ("Deezer Soft", "deezer.com", "Europe", "Paris"),
    ("Strapi Soft", "strapi.io", "Europe", "Paris"),
    ("Bending Soft", "bendingspoons.com", "Europe", "Milan"),
    ("Satispay Soft", "satispay.com", "Europe", "Milan"),
    ("Musixmatch Soft", "musixmatch.com", "Europe", "Bologna"),
    ("Scalapay Soft", "scalapay.com", "Europe", "Milan"),
    ("Cabify Soft", "cabify.com", "Europe", "Madrid"),
    ("Wallapop Soft", "wallapop.com", "Europe", "Barcelona"),
    ("Holded Soft", "holded.com", "Europe", "Barcelona"),
    ("Gett Soft", "gett.com", "Europe", "London"),
    ("UiPath Soft", "uipath.com", "Europe", "Bucharest"),
    ("Bitdefender Soft", "bitdefender.com", "Europe", "Bucharest"),
    ("eMAG Soft", "emag.ro", "Europe", "Bucharest"),
    ("Bunnyshell Soft", "bunnyshell.com", "Europe", "Bucharest"),
    ("SoftServe Soft", "softserveinc.com", "Europe", "Lviv"),
    ("Intellias Soft", "intellias.com", "Europe", "Lviv"),
    ("ELEKS Soft", "eleks.com", "Europe", "Lviv"),
    ("DataArt Soft", "dataart.com", "Europe", "London"),
    ("Andersen Soft", "andersenlab.com", "Europe", "Warsaw"),
    ("Yalantis Soft", "yalantis.com", "Europe", "Dnipro"),
    ("MacPaw Soft", "macpaw.com", "Europe", "Kyiv"),
    ("Ajax Soft", "ajax.systems", "Europe", "Kyiv"),
    ("Reface Soft", "reface.ai", "Europe", "Kyiv"),
    ("Grammarly Soft", "grammarly.com", "Remote", "Worldwide"),
    ("Notion Soft", "notion.so", "Remote", "Worldwide"),
    ("Figma Soft", "figma.com", "Remote", "Worldwide"),
    ("Linear Soft", "linear.app", "Remote", "Worldwide"),
    ("Retool Soft", "retool.com", "Remote", "Worldwide"),
    ("Coda Soft", "coda.io", "Remote", "Worldwide"),
    ("Asana Soft", "asana.com", "Remote", "Worldwide"),
    ("ClickUp Soft", "clickup.com", "Remote", "Worldwide"),
    ("Monday Soft", "monday.com", "Remote", "Worldwide"),
    ("Webflow Soft", "webflow.com", "Remote", "Worldwide"),
    ("Framer Soft", "framer.com", "Remote", "Worldwide"),
    ("Lovable Soft", "lovable.dev", "Remote", "Worldwide"),
    ("Replit Soft", "replit.com", "Remote", "Worldwide"),
    ("Supabase Soft", "supabase.com", "Remote", "Worldwide"),
    ("Neon Soft", "neon.tech", "Remote", "Worldwide"),
    ("PlanetScale Soft", "planetscale.com", "Remote", "Worldwide"),
    ("Railway Soft", "railway.app", "Remote", "Worldwide"),
    ("Render Soft", "render.com", "Remote", "Worldwide"),
    ("Fly Soft", "fly.io", "Remote", "Worldwide"),
    ("Netlify Soft", "netlify.com", "Remote", "Worldwide"),
    ("Hashicorp Soft", "hashicorp.com", "Remote", "Worldwide"),
    ("Databricks Soft", "databricks.com", "Remote", "Worldwide"),
    ("Snowflake Soft", "snowflake.com", "Remote", "Worldwide"),
    ("dbt Soft", "getdbt.com", "Remote", "Worldwide"),
    ("Fivetran Soft", "fivetran.com", "Remote", "Worldwide"),
    ("Airbyte Soft", "airbyte.com", "Remote", "Worldwide"),
    ("Amplitude Soft", "amplitude.com", "Remote", "Worldwide"),
    ("Mixpanel Soft", "mixpanel.com", "Remote", "Worldwide"),
    ("Pendo Soft", "pendo.io", "Remote", "Worldwide"),
    ("Hotjar Soft", "hotjar.com", "Remote", "Worldwide"),
    ("Heap Soft", "heap.io", "Remote", "Worldwide"),
    ("PostHog Soft", "posthog.com", "Remote", "Worldwide"),
    ("Twilio Soft", "twilio.com", "Remote", "Worldwide"),
    ("Klaviyo Soft", "klaviyo.com", "Remote", "Worldwide"),
    ("Intercom Soft", "intercom.com", "Remote", "Worldwide"),
    ("Zendesk Soft", "zendesk.com", "Remote", "Worldwide"),
    ("Freshworks Soft", "freshworks.com", "Remote", "Worldwide"),
    ("Gong Soft", "gong.io", "Remote", "Worldwide"),
    ("Apollo Soft", "apollo.io", "Remote", "Worldwide"),
    ("Clay Soft", "clay.com", "Remote", "Worldwide"),
    ("Cognism Soft", "cognism.com", "Remote", "Worldwide"),
    ("Plaid Soft", "plaid.com", "Remote", "Worldwide"),
    ("Rippling Soft", "rippling.com", "Remote", "Worldwide"),
    ("Gusto Soft", "gusto.com", "Remote", "Worldwide"),
    ("Deel Soft", "deel.com", "Remote", "Worldwide"),
    ("Remote Soft", "remote.com", "Remote", "Worldwide"),
    ("Oyster Soft", "oysterhr.com", "Remote", "Worldwide"),
    ("Lattice Soft", "lattice.com", "Remote", "Worldwide"),
    ("Duolingo Soft", "duolingo.com", "Remote", "Worldwide"),
    ("Coursera Soft", "coursera.org", "Remote", "Worldwide"),
    ("Raycast Soft", "raycast.com", "Remote", "Worldwide"),
    ("Warp Soft", "warp.dev", "Remote", "Worldwide"),
    ("Sourcegraph Soft", "sourcegraph.com", "Remote", "Worldwide"),
    ("Snyk Soft", "snyk.io", "Remote", "Worldwide"),
    ("Wiz Soft", "wiz.io", "Remote", "Worldwide"),
    ("Orca Soft", "orca.security", "Remote", "Worldwide"),
    ("Okta Soft", "okta.com", "Remote", "Worldwide"),
    ("1Password Soft", "1password.com", "Remote", "Worldwide"),
    ("Bitwarden Soft", "bitwarden.com", "Remote", "Worldwide"),
    ("Kraken Soft", "kraken.com", "Remote", "Worldwide"),
    ("Coinbase Soft", "coinbase.com", "Remote", "Worldwide"),
    ("Robinhood Soft", "robinhood.com", "Remote", "Worldwide"),
    ("SoFi Soft", "sofi.com", "Remote", "Worldwide"),
    ("Chime Soft", "chime.com", "Remote", "Worldwide"),
    ("Nubank Soft", "nubank.com.br", "Remote", "Worldwide"),
    ("Rappi Soft", "rappi.com", "Remote", "Worldwide"),
    ("InDrive Soft", "indrive.com", "Remote", "Worldwide"),
    ("Moovit Soft", "moovit.com", "Remote", "Worldwide"),
    ("Crypto Soft", "crypto.com", "Remote", "Worldwide"),
    ("Bybit Soft", "bybit.com", "Remote", "Worldwide"),
    ("OKX Soft", "okx.com", "Remote", "Worldwide"),
    ("Chainalysis Soft", "chainalysis.com", "Remote", "Worldwide"),
    ("Fireblocks Soft", "fireblocks.com", "Remote", "Worldwide"),
    ("Alchemy Soft", "alchemy.com", "Remote", "Worldwide"),
    ("Consensys Soft", "consensys.net", "Remote", "Worldwide"),
    ("OpenSea Soft", "opensea.io", "Remote", "Worldwide"),
    ("Dune Soft", "dune.com", "Remote", "Worldwide"),
    ("Aptos Soft", "aptoslabs.com", "Remote", "Worldwide"),
    ("Worldcoin Soft", "worldcoin.org", "Remote", "Worldwide"),
    ("Perplexity Soft", "perplexity.ai", "Remote", "Worldwide"),
    ("Cohere Soft", "cohere.com", "Remote", "Worldwide"),
    ("Scale Soft", "scale.com", "Remote", "Worldwide"),
    ("Labelbox Soft", "labelbox.com", "Remote", "Worldwide"),
    ("Weights Soft", "wandb.ai", "Remote", "Worldwide"),
    ("Together Soft", "together.ai", "Remote", "Worldwide"),
    ("Fireworks Soft", "fireworks.ai", "Remote", "Worldwide"),
    ("Groq Soft", "groq.com", "Remote", "Worldwide"),
    ("Runway Soft", "runwayml.com", "Remote", "Worldwide"),
    ("Eleven Soft", "elevenlabs.io", "Remote", "Worldwide"),
    ("Descript Soft", "descript.com", "Remote", "Worldwide"),
    ("Fireflies Soft", "fireflies.ai", "Remote", "Worldwide"),
    ("Calendly Soft", "calendly.com", "Remote", "Worldwide"),
    ("Loom Soft", "loom.com", "Remote", "Worldwide"),
    ("Superhuman Soft", "superhuman.com", "Remote", "Worldwide"),
    ("Front Soft", "front.com", "Remote", "Worldwide"),
    ("Prisma Soft", "prisma.io", "Remote", "Worldwide"),
    ("Convex Soft", "convex.dev", "Remote", "Worldwide"),
    ("Inngest Soft", "inngest.com", "Remote", "Worldwide"),
    ("Prefect Soft", "prefect.io", "Remote", "Worldwide"),
    ("Dagster Soft", "dagster.io", "Remote", "Worldwide"),
    ("Metabase Soft", "metabase.com", "Remote", "Worldwide"),
    ("ThoughtSpot Soft", "thoughtspot.com", "Remote", "Worldwide"),
    ("Sigma Soft", "sigmacomputing.com", "Remote", "Worldwide"),
    ("Sentry Soft", "sentry.io", "Remote", "Worldwide"),
    ("New Relic Soft", "newrelic.com", "Remote", "Worldwide"),
    ("Elastic Soft", "elastic.co", "Remote", "Worldwide"),
    ("Grafana Soft", "grafana.com", "Remote", "Worldwide"),
    ("Honeycomb Soft", "honeycomb.io", "Remote", "Worldwide"),
    ("Timescale Soft", "timescale.com", "Remote", "Worldwide"),
    ("ClickHouse Soft", "clickhouse.com", "Remote", "Worldwide"),
    ("Cockroach Soft", "cockroachlabs.com", "Remote", "Worldwide"),
    ("Yugabyte Soft", "yugabyte.com", "Remote", "Worldwide"),
    ("MongoDB Soft", "mongodb.com", "Remote", "Worldwide"),
    ("Upstash Soft", "upstash.com", "Remote", "Worldwide"),
    ("Dragonfly Soft", "dragonflydb.io", "Remote", "Worldwide"),
    ("Pinecone Soft", "pinecone.io", "Remote", "Worldwide"),
    ("Weaviate Soft", "weaviate.io", "Europe", "Amsterdam"),
    ("Qdrant Soft", "qdrant.tech", "Europe", "Berlin"),
    ("Chroma Soft", "trychroma.com", "Remote", "Worldwide"),
    ("Algolia Soft", "algolia.com", "Europe", "Paris"),
    ("Meilisearch Soft", "meilisearch.com", "Europe", "Paris"),
    ("Typesense Soft", "typesense.org", "Remote", "Worldwide"),
    ("Bright Soft", "brightdata.com", "Europe", "Tel Aviv"),
    ("Oxylabs Soft", "oxylabs.io", "Europe", "Vilnius"),
    ("BrowserStack Soft", "browserstack.com", "Remote", "Worldwide"),
    ("Sauce Soft", "saucelabs.com", "Remote", "Worldwide"),
    ("Cypress Soft", "cypress.io", "Remote", "Worldwide"),
    ("Payload Soft", "payloadcms.com", "Remote", "Worldwide"),
    ("Directus Soft", "directus.io", "Remote", "Worldwide"),
    ("Ghost Soft", "ghost.org", "Remote", "Worldwide"),
    ("Hashnode Soft", "hashnode.com", "Remote", "Worldwide"),
    ("Beehiiv Soft", "beehiiv.com", "Remote", "Worldwide"),
    ("ConvertKit Soft", "convertkit.com", "Remote", "Worldwide"),
    ("Braze Soft", "braze.com", "Remote", "Worldwide"),
    ("Iterable Soft", "iterable.com", "Remote", "Worldwide"),
    ("OneSignal Soft", "onesignal.com", "Remote", "Worldwide"),
    ("CleverTap Soft", "clevertap.com", "Remote", "Worldwide"),
    ("MoEngage Soft", "moengage.com", "Remote", "Worldwide"),
    ("Insider Soft", "useinsider.com", "Europe", "Istanbul"),
    ("Novu Soft", "novu.co", "Remote", "Worldwide"),
    ("Resend Soft", "resend.com", "Remote", "Worldwide"),
    ("Postmark Soft", "postmarkapp.com", "Remote", "Worldwide"),
    ("Mailgun Soft", "mailgun.com", "Remote", "Worldwide"),
    ("Brevo Soft", "brevo.com", "Europe", "Paris"),
    ("Close Soft", "close.com", "Remote", "Worldwide"),
    ("Attio Soft", "attio.com", "Europe", "London"),
    ("Folk Soft", "folk.app", "Europe", "Paris"),
    ("Affinity Soft", "affinity.co", "Remote", "Worldwide"),
    ("Noco Soft", "nocodb.com", "Remote", "Worldwide"),
    ("Smartsheet Soft", "smartsheet.com", "Remote", "Worldwide"),
    ("Plane Soft", "plane.so", "Remote", "Worldwide"),
    ("Taiga Soft", "taiga.io", "Europe", "Madrid"),
    ("Codeium Soft", "codeium.com", "Remote", "Worldwide"),
    ("Tabnine Soft", "tabnine.com", "Europe", "Tel Aviv"),
    ("Gitpod Soft", "gitpod.io", "Europe", "Kiel"),
    ("Coder Soft", "coder.com", "Remote", "Worldwide"),
    ("Stack Soft", "stackblitz.com", "Remote", "Worldwide"),
    ("CodeSandbox Soft", "codesandbox.io", "Europe", "Amsterdam"),
    ("Bubble Soft", "bubble.io", "Remote", "Worldwide"),
    ("Softr Soft", "softr.io", "Europe", "Berlin"),
    ("Glide Soft", "glideapps.com", "Remote", "Worldwide"),
    ("Teleport Soft", "goteleport.com", "Remote", "Worldwide"),
    ("Tailscale Soft", "tailscale.com", "Remote", "Worldwide"),
    ("Twingate Soft", "twingate.com", "Remote", "Worldwide"),
    ("Kong Soft", "konghq.com", "Remote", "Worldwide"),
    ("Tyk Soft", "tyk.io", "Europe", "London"),
    ("Postman Soft", "postman.com", "Remote", "Worldwide"),
    ("DigitalOcean Soft", "digitalocean.com", "Remote", "Worldwide"),
    ("Vultr Soft", "vultr.com", "Remote", "Worldwide"),
    ("Hetzner Soft", "hetzner.com", "Europe", "Gunzenhausen"),
    ("Fastly Soft", "fastly.com", "Remote", "Worldwide"),
    ("Bunny Soft", "bunny.net", "Europe", "Ljubljana"),
    ("Datadog Soft", "datadoghq.com", "Remote", "Worldwide"),
    ("Splunk Soft", "splunk.com", "Remote", "Worldwide"),
    ("Chronosphere Soft", "chronosphere.io", "Remote", "Worldwide"),
    ("LogRocket Soft", "logrocket.com", "Remote", "Worldwide"),
    ("FullStory Soft", "fullstory.com", "Remote", "Worldwide"),
    ("Fathom Soft", "usefathom.com", "Remote", "Worldwide"),
    ("Umami Soft", "umami.is", "Remote", "Worldwide"),
    ("Zapier Soft", "zapier.com", "Remote", "Worldwide"),
    ("Workato Soft", "workato.com", "Remote", "Worldwide"),
    ("Tray Soft", "tray.io", "Remote", "Worldwide"),
    ("Pipedream Soft", "pipedream.com", "Remote", "Worldwide"),
    ("Windmill Soft", "windmill.dev", "Europe", "Paris"),
    ("Greenhouse Soft", "greenhouse.io", "Remote", "Worldwide"),
    ("Ashby Soft", "ashbyhq.com", "Remote", "Worldwide"),
    ("Lever Soft", "lever.co", "Remote", "Worldwide"),
    ("Gem Soft", "gem.com", "Remote", "Worldwide"),
    ("Eightfold Soft", "eightfold.ai", "Remote", "Worldwide"),
    ("Teamtailor Soft", "teamtailor.com", "Europe", "Stockholm"),
    ("Recruitee Soft", "recruitee.com", "Europe", "Amsterdam"),
    ("Workable Soft", "workable.com", "Europe", "London"),
    ("Beam Soft", "beamery.com", "Europe", "London"),
    ("Bamboo Soft", "bamboohr.com", "Remote", "Worldwide"),
    ("Multiplier Soft", "multiplier.com", "Remote", "Worldwide"),
    ("Lucid Soft", "lucid.co", "Remote", "Worldwide"),
    ("Mural Soft", "mural.co", "Remote", "Worldwide"),
    ("Whimsical Soft", "whimsical.com", "Remote", "Worldwide"),
    ("Penpot Soft", "penpot.app", "Europe", "Madrid"),
    ("Slite Soft", "slite.com", "Europe", "Paris"),
    ("Nuclino Soft", "nuclino.com", "Europe", "Munich"),
    ("Guru Soft", "getguru.com", "Remote", "Worldwide"),
    ("Help Scout Soft", "helpscout.com", "Remote", "Worldwide"),
    ("Tidio Soft", "tidio.com", "Europe", "Szczecin"),
    ("LiveChat Soft", "livechat.com", "Europe", "Wroclaw"),
    ("Chatwoot Soft", "chatwoot.com", "Remote", "Worldwide"),
    ("Lusha Soft", "lusha.com", "Europe", "Tel Aviv"),
    ("Hunter Soft", "hunter.io", "Europe", "Paris"),
    ("Snov Soft", "snov.io", "Europe", "Kyiv"),
    ("Lemlist Soft", "lemlist.com", "Europe", "Paris"),
    ("Woodpecker Soft", "woodpecker.co", "Europe", "Wroclaw"),
    ("Reply Soft", "reply.io", "Europe", "Kyiv"),
    ("Instantly Soft", "instantly.ai", "Remote", "Worldwide"),
    ("Smartlead Soft", "smartlead.ai", "Remote", "Worldwide"),
    ("Expandi Soft", "expandi.io", "Europe", "Amsterdam"),
    ("Waalaxy Soft", "waalaxy.com", "Europe", "Paris"),
    ("Phantom Soft", "phantombuster.com", "Europe", "Paris"),
    ("Bardeen Soft", "bardeen.ai", "Remote", "Worldwide"),
    ("Artlist Soft", "artlist.io", "Europe", "Tel Aviv"),
    ("Pexels Soft", "pexels.com", "Europe", "Berlin"),
    ("Shutterstock Soft", "shutterstock.com", "Remote", "Worldwide"),
    ("Getty Soft", "gettyimages.com", "Remote", "Worldwide"),
    ("Pond5 Soft", "pond5.com", "Remote", "Worldwide"),
    ("TuneCore Soft", "tunecore.com", "Remote", "Worldwide"),
    ("SoundCloud Soft", "soundcloud.com", "Europe", "Berlin"),
    ("Tidal Soft", "tidal.com", "Europe", "Oslo"),
    ("Netflix Soft", "netflix.com", "Remote", "Worldwide"),
    ("Discord Soft", "discord.com", "Remote", "Worldwide"),
    ("Slack Soft", "slack.com", "Remote", "Worldwide"),
    ("Zoom Soft", "zoom.us", "Remote", "Worldwide"),
    ("Dropbox Soft", "dropbox.com", "Remote", "Worldwide"),
    ("Box Soft", "box.com", "Remote", "Worldwide"),
    ("Adobe Soft", "adobe.com", "Remote", "Worldwide"),
    ("Autodesk Soft", "autodesk.com", "Remote", "Worldwide"),
    ("ServiceNow Soft", "servicenow.com", "Remote", "Worldwide"),
    ("Palantir Soft", "palantir.com", "Remote", "Worldwide"),
    ("Uber Soft", "uber.com", "Remote", "Worldwide"),
    ("Lyft Soft", "lyft.com", "Remote", "Worldwide"),
    ("DoorDash Soft", "doordash.com", "Remote", "Worldwide"),
    ("Instacart Soft", "instacart.com", "Remote", "Worldwide"),
    ("Airbnb Soft", "airbnb.com", "Remote", "Worldwide"),
    ("Expedia Soft", "expedia.com", "Remote", "Worldwide"),
    ("Tripadvisor Soft", "tripadvisor.com", "Remote", "Worldwide"),
    ("Kayak Soft", "kayak.com", "Remote", "Worldwide"),
    ("Hopper Soft", "hopper.com", "Remote", "Worldwide"),
    ("SeatGeek Soft", "seatgeek.com", "Remote", "Worldwide"),
    ("StubHub Soft", "stubhub.com", "Remote", "Worldwide"),
    ("Ticketmaster Soft", "ticketmaster.com", "Remote", "Worldwide"),
    ("Brex Soft", "brex.com", "Remote", "Worldwide"),
    ("Ramp Soft", "ramp.com", "Remote", "Worldwide"),
    ("Mercury Soft", "mercury.com", "Remote", "Worldwide"),
    ("Affirm Soft", "affirm.com", "Remote", "Worldwide"),
    ("Block Soft", "block.xyz", "Remote", "Worldwide"),
    ("Faire Soft", "faire.com", "Remote", "Worldwide"),
    ("Flexport Soft", "flexport.com", "Remote", "Worldwide"),
    ("ShipBob Soft", "shipbob.com", "Remote", "Worldwide"),
    ("Navan Soft", "navan.com", "Remote", "Worldwide"),
    ("Expensify Soft", "expensify.com", "Remote", "Worldwide"),
    ("Tipalti Soft", "tipalti.com", "Remote", "Worldwide"),
    ("Melio Soft", "meliopayments.com", "Remote", "Worldwide"),
    ("Unit Soft", "unit.co", "Remote", "Worldwide"),
    ("Column Soft", "column.com", "Remote", "Worldwide"),
    ("Marqeta Soft", "marqeta.com", "Remote", "Worldwide"),
    ("Public Soft", "public.com", "Remote", "Worldwide"),
    ("Wealthfront Soft", "wealthfront.com", "Remote", "Worldwide"),
    ("Betterment Soft", "betterment.com", "Remote", "Worldwide"),
    ("Replicate Soft", "replicate.com", "Remote", "Worldwide"),
    ("Modal Soft", "modal.com", "Remote", "Worldwide"),
    ("Anyscale Soft", "anyscale.com", "Remote", "Worldwide"),
    ("Baseten Soft", "baseten.co", "Remote", "Worldwide"),
    ("Cerebras Soft", "cerebras.net", "Remote", "Worldwide"),
    ("SambaNova Soft", "sambanova.ai", "Remote", "Worldwide"),
    ("HeyGen Soft", "heygen.com", "Remote", "Worldwide"),
    ("Pika Soft", "pika.art", "Remote", "Worldwide"),
    ("Luma Soft", "lumalabs.ai", "Remote", "Worldwide"),
    ("Gamma Soft", "gamma.app", "Remote", "Worldwide"),
    ("Tome Soft", "tome.app", "Remote", "Worldwide"),
    ("Beautiful Soft", "beautiful.ai", "Remote", "Worldwide"),
    ("Pitch Soft", "pitch.com", "Europe", "Berlin"),
    ("Felt Soft", "felt.com", "Remote", "Worldwide"),
    ("Esri Soft", "esri.com", "Remote", "Worldwide"),
    ("Mapbox Soft", "mapbox.com", "Remote", "Worldwide"),
    ("Clerk Soft", "clerk.com", "Remote", "Worldwide"),
    ("Stytch Soft", "stytch.com", "Remote", "Worldwide"),
    ("WorkOS Soft", "workos.com", "Remote", "Worldwide"),
    ("Descope Soft", "descope.com", "Remote", "Worldwide"),
    ("FusionAuth Soft", "fusionauth.io", "Remote", "Worldwide"),
    ("Auth0 Soft", "auth0.com", "Remote", "Worldwide"),
    ("Dashlane Soft", "dashlane.com", "Europe", "Paris"),
    ("LastPass Soft", "lastpass.com", "Remote", "Worldwide"),
    ("Xata Soft", "xata.io", "Remote", "Worldwide"),
    ("Fauna Soft", "fauna.com", "Remote", "Worldwide"),
    ("Appwrite Soft", "appwrite.io", "Remote", "Worldwide"),
    ("Hasura Soft", "hasura.io", "Remote", "Worldwide"),
    ("Drizzle Soft", "drizzle.team", "Remote", "Worldwide"),
    ("Turso Soft", "turso.tech", "Remote", "Worldwide"),
    ("Milvus Soft", "zilliz.com", "Remote", "Worldwide"),
    ("Marqo Soft", "marqo.ai", "Australia", "Melbourne"),
    ("Firecrawl Soft", "firecrawl.dev", "Remote", "Worldwide"),
    ("Browserless Soft", "browserless.io", "Remote", "Worldwide"),
    ("Percy Soft", "percy.io", "Remote", "Worldwide"),
    ("Chromatic Soft", "chromatic.com", "Remote", "Worldwide"),
    ("Tricentis Soft", "tricentis.com", "Europe", "Vienna"),
    ("TestRail Soft", "testrail.com", "Remote", "Worldwide"),
    ("SmartBear Soft", "smartbear.com", "Remote", "Worldwide"),
    ("Courier Soft", "courier.com", "Remote", "Worldwide"),
    ("Knock Soft", "knock.app", "Remote", "Worldwide"),
    ("Magic Soft", "magicbell.com", "Remote", "Worldwide"),
    ("Loops Soft", "loops.so", "Remote", "Worldwide"),
    ("Active Soft", "activecampaign.com", "Remote", "Worldwide"),
    ("Zoho Soft", "zoho.com", "Remote", "Worldwide"),
    ("Salesforce Soft", "salesforce.com", "Remote", "Worldwide"),
    ("HubSpot Soft", "hubspot.com", "Remote", "Worldwide"),
    ("Unity Soft", "unity.com", "Europe", "Copenhagen"),
    ("Roblox Soft", "roblox.com", "Remote", "Worldwide"),
    ("Epic Soft", "epicgames.com", "Remote", "Worldwide"),
    ("Riot Soft", "riotgames.com", "Remote", "Worldwide"),
    ("Ubisoft Soft", "ubisoft.com", "Europe", "Paris"),
    ("EA Soft", "ea.com", "Remote", "Worldwide"),
    ("CD Soft", "cdprojekt.com", "Europe", "Warsaw"),
    ("Embracer Soft", "embracer.com", "Europe", "Stockholm"),
    ("Paradox Soft", "paradoxinteractive.com", "Europe", "Stockholm"),
    ("King Soft", "king.com", "Europe", "Stockholm"),
    ("Zynga Soft", "zynga.com", "Remote", "Worldwide"),
    ("Scopely Soft", "scopely.com", "Remote", "Worldwide"),
    ("Bungie Soft", "bungie.net", "Remote", "Worldwide"),
    ("Blizzard Soft", "blizzard.com", "Remote", "Worldwide"),
    ("Activision Soft", "activision.com", "Remote", "Worldwide"),
    ("Bethesda Soft", "bethesda.net", "Remote", "Worldwide"),
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
            if region in {"Karachi", "Pakistan"}
            else -1
            if region
            in {"Kuwait", "Australia", "UAE", "KSA", "Egypt", "Jordan", "Bahrain", "Qatar", "MENA"}
            else 0
        )
        plan.append((pri, region, name, domain, city, locs))
    plan = sorted(plan)
    print("plan", len(plan), flush=True)

    residual = []
    for dom, locs in probed.items():
        if dom in dead or dom in sent_d or any(p[3] == dom for p in plan):
            continue
        if any(cache.get(f"{l}@{dom}") == "catch-all" for l in list(locs) + TRY):
            continue
        missing = [
            loc
            for loc in TRY
            if loc not in locs
            and f"{loc}@{dom}" not in sent_e
            and f"{loc}@{dom}" not in bounces
            and cache.get(f"{loc}@{dom}") not in DONE
        ]
        if not missing:
            continue
        if not any(cache.get(f"{l}@{dom}") in {"invalid", "reject", "bounce"} for l in locs):
            continue
        try:
            hosts = mx_hosts(dom)
        except Exception:
            hosts = []
        mxblob = " ".join(hosts).lower()
        if not any(t in mxblob for t in GOOD_MX):
            continue
        residual.append(("Remote", dom.split(".")[0].replace("-", " ").title(), dom, "Worldwide", missing[:3]))
    print("residual", len(residual), flush=True)
    for region, name, domain, city, locs in residual:
        plan.append((1, region, name, domain, city, locs))

    found = []
    stats: Counter[str] = Counter()
    target = 40
    for i, (_, region, name, domain, city, locs) in enumerate(plan, 1):
        if len(found) >= target:
            print("hit", target, flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(plan)}] {email}", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.3)
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
                break
            tag = "catch-all" if "catch-all" in detail.lower() else "fail"
            stats[tag] += 1
            print(f"  NO {tag}", flush=True)
            if tag == "catch-all":
                break

    out = ROOT / "output/emails_shortlist_batch43_2026-08-16.csv"
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
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(found)
    print("STATS", dict(stats), "rows", len(found), flush=True)
    for r in found:
        print(f"  {r['HR / Recruiter Email']:40} {r['Company']} [{r['Region']}]", flush=True)


if __name__ == "__main__":
    main()
