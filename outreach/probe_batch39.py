#!/usr/bin/env python3
"""Probe batch39: fresh Google/Proofpoint/Mimecast domains for 2026-08-16 send."""
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
    ("Revolut Soft", "revolut.com", "Europe", "London"),
    ("Wise Soft", "wise.com", "Europe", "London"),
    ("Checkout Soft", "checkout.com", "Europe", "London"),
    ("SumUp Soft", "sumup.com", "Europe", "London"),
    ("Deliveroo Soft", "deliveroo.com", "Europe", "London"),
    ("Darktrace Soft", "darktrace.com", "Europe", "Cambridge"),
    ("Featurespace Soft", "featurespace.com", "Europe", "Cambridge"),
    ("Improbable Soft", "improbable.io", "Europe", "London"),
    ("Multiverse Soft", "multiverse.io", "Europe", "London"),
    ("Onfido Soft", "onfido.com", "Europe", "London"),
    ("Thought Machine Soft", "thoughtmachine.net", "Europe", "London"),
    ("Pleo Soft", "pleo.io", "Europe", "Copenhagen"),
    ("Too Good To Go Soft", "toogoodtogo.com", "Europe", "Copenhagen"),
    ("Vivino Soft", "vivino.com", "Europe", "Copenhagen"),
    ("Leapwork Soft", "leapwork.com", "Europe", "Copenhagen"),
    ("Supercell Soft", "supercell.com", "Europe", "Helsinki"),
    ("Aiven Soft", "aiven.io", "Europe", "Helsinki"),
    ("Relex Soft", "relexsolutions.com", "Europe", "Helsinki"),
    ("Iceye Soft", "iceye.com", "Europe", "Helsinki"),
    ("Wolt Soft", "wolt.com", "Europe", "Helsinki"),
    ("Smartly Soft", "smartly.io", "Europe", "Helsinki"),
    ("Vinted Soft", "vinted.com", "Europe", "Vilnius"),
    ("Nord Soft", "nordsecurity.com", "Europe", "Vilnius"),
    ("TransferGo Soft", "transfergo.com", "Europe", "Vilnius"),
    ("Bolt Soft", "bolt.eu", "Europe", "Tallinn"),
    ("Veriff Soft", "veriff.com", "Europe", "Tallinn"),
    ("Pipedrive Soft", "pipedrive.com", "Europe", "Tallinn"),
    ("Lunar Soft", "lunar.app", "Europe", "Aarhus"),
    ("Trustpilot Soft", "trustpilot.com", "Europe", "Copenhagen"),
    ("Getir Soft", "getir.com", "Europe", "London"),
    ("Flink Soft", "goflink.com", "Europe", "Berlin"),
    ("Delivery Hero Soft", "deliveryhero.com", "Europe", "Berlin"),
    ("HelloFresh Soft", "hellofresh.com", "Europe", "Berlin"),
    ("Zalando Soft", "zalando.com", "Europe", "Berlin"),
    ("N26 Soft", "n26.com", "Europe", "Berlin"),
    ("Trade Republic Soft", "traderepublic.com", "Europe", "Berlin"),
    ("GetYourGuide Soft", "getyourguide.com", "Europe", "Berlin"),
    ("Auto1 Soft", "auto1.com", "Europe", "Berlin"),
    ("Wefox Soft", "wefox.com", "Europe", "Berlin"),
    ("Omio Soft", "omio.com", "Europe", "Berlin"),
    ("Contentful Soft", "contentful.com", "Europe", "Berlin"),
    ("Personio Soft", "personio.com", "Europe", "Munich"),
    ("Celonis Soft", "celonis.com", "Europe", "Munich"),
    ("Flix Soft", "flixbus.com", "Europe", "Munich"),
    ("Sennder Soft", "sennder.com", "Europe", "Berlin"),
    ("Adjust Soft", "adjust.com", "Europe", "Berlin"),
    ("Miro Soft", "miro.com", "Europe", "Amsterdam"),
    ("Adyen Soft", "adyen.com", "Europe", "Amsterdam"),
    ("Mollie Soft", "mollie.com", "Europe", "Amsterdam"),
    ("MessageBird Soft", "messagebird.com", "Europe", "Amsterdam"),
    ("Bunq Soft", "bunq.com", "Europe", "Amsterdam"),
    ("Picnic Soft", "picnic.app", "Europe", "Amsterdam"),
    ("WeTransfer Soft", "wetransfer.com", "Europe", "Amsterdam"),
    ("TomTom Soft", "tomtom.com", "Europe", "Amsterdam"),
    ("Backbase Soft", "backbase.com", "Europe", "Amsterdam"),
    ("Mambu Soft", "mambu.com", "Europe", "Amsterdam"),
    ("Weaviate Soft", "weaviate.io", "Europe", "Amsterdam"),
    ("Qdrant Soft", "qdrant.tech", "Europe", "Berlin"),
    ("Gitpod Soft", "gitpod.io", "Europe", "Kiel"),
    ("DeepL Soft", "deepl.com", "Europe", "Cologne"),
    ("TeamViewer Soft", "teamviewer.com", "Europe", "Goppingen"),
    ("About You Soft", "aboutyou.com", "Europe", "Hamburg"),
    ("Klarna Soft", "klarna.com", "Europe", "Stockholm"),
    ("Spotify Soft", "spotify.com", "Europe", "Stockholm"),
    ("Epidemic Soft", "epidemicsound.com", "Europe", "Stockholm"),
    ("Trustly Soft", "trustly.com", "Europe", "Stockholm"),
    ("Tink Soft", "tink.com", "Europe", "Stockholm"),
    ("Northvolt Soft", "northvolt.com", "Europe", "Stockholm"),
    ("Einride Soft", "einride.tech", "Europe", "Stockholm"),
    ("Voi Soft", "voi.com", "Europe", "Stockholm"),
    ("Monzo Soft", "monzo.com", "Europe", "London"),
    ("Starling Soft", "starlingbank.com", "Europe", "London"),
    ("OakNorth Soft", "oaknorth.com", "Europe", "London"),
    ("Tide Soft", "tide.co", "Europe", "London"),
    ("Curve Soft", "curve.com", "Europe", "London"),
    ("Iwoca Soft", "iwoca.co.uk", "Europe", "London"),
    ("GoCardless Soft", "gocardless.com", "Europe", "London"),
    ("TrueLayer Soft", "truelayer.com", "Europe", "London"),
    ("Codat Soft", "codat.io", "Europe", "London"),
    ("Form3 Soft", "form3.tech", "Europe", "London"),
    ("Token Soft", "token.io", "Europe", "London"),
    ("Yapily Soft", "yapily.com", "Europe", "London"),
    ("Wayve Soft", "wayve.ai", "Europe", "London"),
    ("Synthesia Soft", "synthesia.io", "Europe", "London"),
    ("Stability Soft", "stability.ai", "Europe", "London"),
    ("PolyAI Soft", "poly.ai", "Europe", "London"),
    ("Faculty Soft", "faculty.ai", "Europe", "London"),
    ("Graphcore Soft", "graphcore.ai", "Europe", "Bristol"),
    ("Skyscanner Soft", "skyscanner.net", "Europe", "Edinburgh"),
    ("Trainline Soft", "thetrainline.com", "Europe", "London"),
    ("Citymapper Soft", "citymapper.com", "Europe", "London"),
    ("Just Eat Soft", "justeat.com", "Europe", "London"),
    ("Takeaway Soft", "takeaway.com", "Europe", "Amsterdam"),
    ("Typeform Soft", "typeform.com", "Europe", "Barcelona"),
    ("Travelperk Soft", "travelperk.com", "Europe", "Barcelona"),
    ("Glovo Soft", "glovoapp.com", "Europe", "Barcelona"),
    ("Wallapop Soft", "wallapop.com", "Europe", "Barcelona"),
    ("Cabify Soft", "cabify.com", "Europe", "Madrid"),
    ("Factorial Soft", "factorialhr.com", "Europe", "Barcelona"),
    ("Holded Soft", "holded.com", "Europe", "Barcelona"),
    ("Bending Soft", "bendingspoons.com", "Europe", "Milan"),
    ("Satispay Soft", "satispay.com", "Europe", "Milan"),
    ("Musixmatch Soft", "musixmatch.com", "Europe", "Bologna"),
    ("Scalapay Soft", "scalapay.com", "Europe", "Milan"),
    ("Alan Soft", "alan.com", "Europe", "Paris"),
    ("Doctolib Soft", "doctolib.com", "Europe", "Paris"),
    ("Ledger Soft", "ledger.com", "Europe", "Paris"),
    ("Aircall Soft", "aircall.io", "Europe", "Paris"),
    ("Algolia Soft", "algolia.com", "Europe", "Paris"),
    ("Qonto Soft", "qonto.com", "Europe", "Paris"),
    ("Spendesk Soft", "spendesk.com", "Europe", "Paris"),
    ("Sorare Soft", "sorare.com", "Europe", "Paris"),
    ("Photoroom Soft", "photoroom.com", "Europe", "Paris"),
    ("Pigment Soft", "pigment.com", "Europe", "Paris"),
    ("PayFit Soft", "payfit.com", "Europe", "Paris"),
    ("Criteo Soft", "criteo.com", "Europe", "Paris"),
    ("BlaBlaCar Soft", "blablacar.com", "Europe", "Paris"),
    ("Contentsquare Soft", "contentsquare.com", "Europe", "Paris"),
    ("Mirakl Soft", "mirakl.com", "Europe", "Paris"),
    ("Back Market Soft", "backmarket.com", "Europe", "Paris"),
    ("ManoMano Soft", "manomano.com", "Europe", "Paris"),
    ("Swile Soft", "swile.co", "Europe", "Paris"),
    ("Pennylane Soft", "pennylane.com", "Europe", "Paris"),
    ("Deezer Soft", "deezer.com", "Europe", "Paris"),
    ("Scaleway Soft", "scaleway.com", "Europe", "Paris"),
    ("Strapi Soft", "strapi.io", "Europe", "Paris"),
    ("Crisp Soft", "crisp.chat", "Europe", "Nantes"),
    ("Hibob Soft", "hibob.com", "Europe", "London"),
    ("Attio Soft", "attio.com", "Europe", "London"),
    ("Beekeeper Soft", "beekeeper.io", "Europe", "Zurich"),
    ("Scandit Soft", "scandit.com", "Europe", "Zurich"),
    ("Proton Soft", "proton.me", "Europe", "Geneva"),
    ("Sonar Soft", "sonarsource.com", "Europe", "Geneva"),
    ("Bitpanda Soft", "bitpanda.com", "Europe", "Vienna"),
    ("GoStudent Soft", "gostudent.org", "Europe", "Vienna"),
    ("TourRadar Soft", "tourradar.com", "Europe", "Vienna"),
    ("JetBrains Soft", "jetbrains.com", "Europe", "Prague"),
    ("Productboard Soft", "productboard.com", "Europe", "Prague"),
    ("Kiwi Soft", "kiwi.com", "Europe", "Prague"),
    ("Rohlik Soft", "rohlik.cz", "Europe", "Prague"),
    ("Trezor Soft", "trezor.io", "Europe", "Prague"),
    ("Avast Soft", "avast.com", "Europe", "Prague"),
    ("Sanity Soft", "sanity.io", "Europe", "Oslo"),
    ("Kahoot Soft", "kahoot.com", "Europe", "Oslo"),
    ("Schibsted Soft", "schibsted.com", "Europe", "Oslo"),
    ("Oda Soft", "oda.com", "Europe", "Oslo"),
    ("Elliptic Soft", "elliptic.co", "Europe", "London"),
    ("Endava Soft", "endava.com", "Europe", "London"),
    ("SoftServe Soft", "softserveinc.com", "Europe", "Lviv"),
    ("Intellias Soft", "intellias.com", "Europe", "Lviv"),
    ("ELEKS Soft", "eleks.com", "Europe", "Lviv"),
    ("DataArt Soft", "dataart.com", "Europe", "London"),
    ("Andersen Soft", "andersenlab.com", "Europe", "Warsaw"),
    ("Yalantis Soft", "yalantis.com", "Europe", "Dnipro"),
    ("Allegro Soft", "allegro.pl", "Europe", "Warsaw"),
    ("Docplanner Soft", "docplanner.com", "Europe", "Warsaw"),
    ("Booksy Soft", "booksy.com", "Europe", "Warsaw"),
    ("Brainly Soft", "brainly.com", "Europe", "Krakow"),
    ("Canva Soft", "canva.com", "Australia", "Sydney"),
    ("Atlassian Soft", "atlassian.com", "Australia", "Sydney"),
    ("Xero Soft", "xero.com", "Australia", "Wellington"),
    ("Culture Amp Soft", "cultureamp.com", "Australia", "Melbourne"),
    ("Airwallex Soft", "airwallex.com", "Australia", "Melbourne"),
    ("Employment Hero Soft", "employmenthero.com", "Australia", "Sydney"),
    ("Deputy Soft", "deputy.com", "Australia", "Sydney"),
    ("SafetyCulture Soft", "safetyculture.com", "Australia", "Sydney"),
    ("Buildkite Soft", "buildkite.com", "Australia", "Melbourne"),
    ("Envato Soft", "envato.com", "Australia", "Melbourne"),
    ("Linktree Soft", "linktr.ee", "Australia", "Melbourne"),
    ("Immutable Soft", "immutable.com", "Australia", "Sydney"),
    ("SiteMinder Soft", "siteminder.com", "Australia", "Sydney"),
    ("Airtasker Soft", "airtasker.com", "Australia", "Sydney"),
    ("Up Soft", "up.com.au", "Australia", "Melbourne"),
    ("Judo Soft", "judo.bank", "Australia", "Melbourne"),
    ("MoneyMe Soft", "moneyme.com.au", "Australia", "Sydney"),
    ("Seek Soft", "seek.com.au", "Australia", "Melbourne"),
    ("Afterpay Soft", "afterpay.com", "Australia", "Melbourne"),
    ("Zip Soft", "zip.co", "Australia", "Sydney"),
    ("Prospa Soft", "prospa.com", "Australia", "Sydney"),
    ("Tyro Soft", "tyro.com", "Australia", "Sydney"),
    ("Campaign Soft", "campaignmonitor.com", "Australia", "Sydney"),
    ("BigCommerce Soft", "bigcommerce.com", "Australia", "Sydney"),
    ("Nearmap Soft", "nearmap.com", "Australia", "Sydney"),
    ("Appen Soft", "appen.com", "Australia", "Sydney"),
    ("Nitro Soft", "gonitro.com", "Australia", "Sydney"),
    ("Anghami Soft", "anghami.com", "UAE", "Dubai"),
    ("NEOM Soft", "neom.com", "KSA", "Tabuk"),
    ("Tabby Soft", "tabby.ai", "UAE", "Dubai"),
    ("Tamara Soft", "tamara.co", "KSA", "Riyadh"),
    ("Bayzat Soft", "bayzat.com", "UAE", "Dubai"),
    ("Mamo Soft", "mamopay.com", "UAE", "Dubai"),
    ("Foodics Soft", "foodics.com", "KSA", "Riyadh"),
    ("Careem Soft", "careem.com", "UAE", "Dubai"),
    ("Noon Soft", "noon.com", "UAE", "Dubai"),
    ("Instabug Soft", "instabug.com", "Egypt", "Cairo"),
    ("Paymob Soft", "paymob.com", "Egypt", "Cairo"),
    ("Telda Soft", "telda.com", "Egypt", "Cairo"),
    ("Halan Soft", "halan.com", "Egypt", "Cairo"),
    ("Swvl Soft", "swvl.com", "Egypt", "Cairo"),
    ("MyFatoorah Soft", "myfatoorah.com", "Kuwait", "Kuwait"),
    ("Tap Soft", "tap.company", "Kuwait", "Kuwait"),
    ("Jahez Soft", "jahez.net", "KSA", "Riyadh"),
    ("Mrsool Soft", "mrsool.com", "KSA", "Riyadh"),
    ("Sary Soft", "sary.com", "KSA", "Riyadh"),
    ("Unifonic Soft", "unifonic.com", "KSA", "Riyadh"),
    ("Lean Soft", "leantech.me", "KSA", "Riyadh"),
    ("Snoonu Soft", "snoonu.com", "Qatar", "Doha"),
    ("Property Soft", "propertyfinder.ae", "UAE", "Dubai"),
    ("Bayut Soft", "bayut.com", "UAE", "Dubai"),
    ("Dubizzle Soft", "dubizzle.com", "UAE", "Dubai"),
    ("Kitopi Soft", "kitopi.com", "UAE", "Dubai"),
    ("Sarwa Soft", "sarwa.co", "UAE", "Dubai"),
    ("Beehive Soft", "beehive.ae", "UAE", "Dubai"),
    ("Postpay Soft", "postpay.io", "UAE", "Dubai"),
    ("Spotii Soft", "spotii.com", "UAE", "Dubai"),
    ("Syarah Soft", "syarah.com", "KSA", "Riyadh"),
    ("Hunger Soft", "hungerstation.com", "KSA", "Riyadh"),
    ("The Chefz Soft", "thechefz.co", "KSA", "Riyadh"),
    ("Barq Soft", "barq.com", "KSA", "Riyadh"),
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
    ("Census Soft", "getcensus.com", "Remote", "Worldwide"),
    ("Hex Soft", "hex.tech", "Remote", "Worldwide"),
    ("Amplitude Soft", "amplitude.com", "Remote", "Worldwide"),
    ("Mixpanel Soft", "mixpanel.com", "Remote", "Worldwide"),
    ("Pendo Soft", "pendo.io", "Remote", "Worldwide"),
    ("FullStory Soft", "fullstory.com", "Remote", "Worldwide"),
    ("Hotjar Soft", "hotjar.com", "Remote", "Worldwide"),
    ("Heap Soft", "heap.io", "Remote", "Worldwide"),
    ("Twilio Soft", "twilio.com", "Remote", "Worldwide"),
    ("Klaviyo Soft", "klaviyo.com", "Remote", "Worldwide"),
    ("Customer Soft", "customer.io", "Remote", "Worldwide"),
    ("Intercom Soft", "intercom.com", "Remote", "Worldwide"),
    ("Zendesk Soft", "zendesk.com", "Remote", "Worldwide"),
    ("Freshworks Soft", "freshworks.com", "Remote", "Worldwide"),
    ("Gong Soft", "gong.io", "Remote", "Worldwide"),
    ("Outreach Soft", "outreach.io", "Remote", "Worldwide"),
    ("Apollo Soft", "apollo.io", "Remote", "Worldwide"),
    ("Clay Soft", "clay.com", "Remote", "Worldwide"),
    ("Cognism Soft", "cognism.com", "Remote", "Worldwide"),
    ("Plaid Soft", "plaid.com", "Remote", "Worldwide"),
    ("Marqeta Soft", "marqeta.com", "Remote", "Worldwide"),
    ("Unit Soft", "unit.co", "Remote", "Worldwide"),
    ("Column Soft", "column.com", "Remote", "Worldwide"),
    ("Modern Soft", "moderntreasury.com", "Remote", "Worldwide"),
    ("Melio Soft", "meliopayments.com", "Remote", "Worldwide"),
    ("Tipalti Soft", "tipalti.com", "Remote", "Worldwide"),
    ("Navan Soft", "navan.com", "Remote", "Worldwide"),
    ("Expensify Soft", "expensify.com", "Remote", "Worldwide"),
    ("Rippling Soft", "rippling.com", "Remote", "Worldwide"),
    ("Gusto Soft", "gusto.com", "Remote", "Worldwide"),
    ("Deel Soft", "deel.com", "Remote", "Worldwide"),
    ("Remote Soft", "remote.com", "Remote", "Worldwide"),
    ("Oyster Soft", "oysterhr.com", "Remote", "Worldwide"),
    ("Lattice Soft", "lattice.com", "Remote", "Worldwide"),
    ("15Five Soft", "15five.com", "Remote", "Worldwide"),
    ("BetterUp Soft", "betterup.com", "Remote", "Worldwide"),
    ("Calm Soft", "calm.com", "Remote", "Worldwide"),
    ("Headspace Soft", "headspace.com", "Remote", "Worldwide"),
    ("Duolingo Soft", "duolingo.com", "Remote", "Worldwide"),
    ("Coursera Soft", "coursera.org", "Remote", "Worldwide"),
    ("Udemy Soft", "udemy.com", "Remote", "Worldwide"),
    ("Grammarly Soft", "grammarly.com", "Remote", "Worldwide"),
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
    ("Gett Soft", "gett.com", "Europe", "London"),
    ("Crypto Soft", "crypto.com", "Remote", "Worldwide"),
    ("Bybit Soft", "bybit.com", "Remote", "Worldwide"),
    ("OKX Soft", "okx.com", "Remote", "Worldwide"),
    ("Chainalysis Soft", "chainalysis.com", "Remote", "Worldwide"),
    ("Fireblocks Soft", "fireblocks.com", "Remote", "Worldwide"),
    ("Alchemy Soft", "alchemy.com", "Remote", "Worldwide"),
    ("Consensys Soft", "consensys.net", "Remote", "Worldwide"),
    ("OpenSea Soft", "opensea.io", "Remote", "Worldwide"),
    ("Dune Soft", "dune.com", "Remote", "Worldwide"),
    ("Solana Soft", "solana.com", "Remote", "Worldwide"),
    ("Aptos Soft", "aptoslabs.com", "Remote", "Worldwide"),
    ("Worldcoin Soft", "worldcoin.org", "Remote", "Worldwide"),
    ("Perplexity Soft", "perplexity.ai", "Remote", "Worldwide"),
    ("Cohere Soft", "cohere.com", "Remote", "Worldwide"),
    ("Mistral Soft", "mistral.ai", "Europe", "Paris"),
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
    ("PostHog Soft", "posthog.com", "Remote", "Worldwide"),
    ("Sentry Soft", "sentry.io", "Remote", "Worldwide"),
    ("New Relic Soft", "newrelic.com", "Remote", "Worldwide"),
    ("Dynatrace Soft", "dynatrace.com", "Europe", "Linz"),
    ("Elastic Soft", "elastic.co", "Remote", "Worldwide"),
    ("Grafana Soft", "grafana.com", "Remote", "Worldwide"),
    ("Honeycomb Soft", "honeycomb.io", "Remote", "Worldwide"),
    ("Timescale Soft", "timescale.com", "Remote", "Worldwide"),
    ("QuestDB Soft", "questdb.io", "Europe", "London"),
    ("ClickHouse Soft", "clickhouse.com", "Remote", "Worldwide"),
    ("Cockroach Soft", "cockroachlabs.com", "Remote", "Worldwide"),
    ("Yugabyte Soft", "yugabyte.com", "Remote", "Worldwide"),
    ("MongoDB Soft", "mongodb.com", "Remote", "Worldwide"),
    ("Redis Soft", "redis.com", "Remote", "Worldwide"),
    ("Upstash Soft", "upstash.com", "Remote", "Worldwide"),
    ("Dragonfly Soft", "dragonflydb.io", "Remote", "Worldwide"),
    ("Baserow Soft", "baserow.io", "Europe", "Amsterdam"),
    ("HERE Soft", "here.com", "Europe", "Berlin"),
    ("Carto Soft", "carto.com", "Europe", "Madrid"),
    ("Felt Soft", "felt.com", "Remote", "Worldwide"),
    ("Plausible Soft", "plausible.io", "Europe", "Tallinn"),
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

    print("pre-mx filter", len(fresh), flush=True)
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
            in {"Kuwait", "Australia", "UAE", "KSA", "Egypt", "Jordan", "Bahrain", "Qatar"}
            else 0
        )
        plan.append((pri, region, name, domain, city, locs))
    plan = sorted(plan)
    print("plan", len(plan), flush=True)
    for item in plan[:50]:
        print(f"  {item[3]:32} {item[2]} [{item[1]}]", flush=True)

    # Also mine residual Proofpoint join/@ aliases on partial domains
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
        company = dom.split(".")[0].replace("-", " ").title()
        residual.append(("Remote", company, dom, "Worldwide", missing[:3]))
    print("residual", len(residual), flush=True)
    for region, name, domain, city, locs in residual:
        plan.append((1, region, name, domain, city, locs))

    found = []
    stats: Counter[str] = Counter()
    target = 25
    for i, (_, region, name, domain, city, locs) in enumerate(plan, 1):
        if len(found) >= target:
            print("hit", target, flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(plan)}] {email}", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.4)
            if ok:
                stats["ok"] += 1
                clean = clean_name(name)
                print("  OK", flush=True)
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
            print(f"  NO {tag}", flush=True)
            if tag == "catch-all":
                break

    out = ROOT / "output/emails_shortlist_batch39_2026-08-16.csv"
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
        print(
            f"  {r['HR / Recruiter Email']:40} {r['Company']} [{r['Region']}]",
            flush=True,
        )


if __name__ == "__main__":
    main()
