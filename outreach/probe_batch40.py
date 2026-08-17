#!/usr/bin/env python3
"""Probe batch40: more Google/Proofpoint/Mimecast hiring aliases for 2026-08-16."""
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
    # Europe — second wave
    ("Revolut Soft", "revolut.com", "Europe", "London"),
    ("Wise Soft", "wise.com", "Europe", "London"),
    ("Checkout Soft", "checkout.com", "Europe", "London"),
    ("SumUp Soft", "sumup.com", "Europe", "London"),
    ("Deliveroo Soft", "deliveroo.com", "Europe", "London"),
    ("Darktrace Soft", "darktrace.com", "Europe", "Cambridge"),
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
    ("Klarna Soft", "klarna.com", "Europe", "Stockholm"),
    ("Spotify Soft", "spotify.com", "Europe", "Stockholm"),
    ("Epidemic Soft", "epidemicsound.com", "Europe", "Stockholm"),
    ("Trustly Soft", "trustly.com", "Europe", "Stockholm"),
    ("Tink Soft", "tink.com", "Europe", "Stockholm"),
    ("Northvolt Soft", "northvolt.com", "Europe", "Stockholm"),
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
    ("Taxfix Soft", "taxfix.com", "Europe", "Dublin"),
    ("Intercom Soft", "intercom.io", "Europe", "Dublin"),
    ("Workday Soft", "workday.com", "Europe", "Dublin"),
    ("Stripe Soft", "stripe.com", "Europe", "Dublin"),
    ("HubSpot Soft", "hubspot.com", "Europe", "Dublin"),
    ("Shopify Soft", "shopify.com", "Europe", "Dublin"),
    ("Fiverr Soft", "fiverr.com", "Europe", "Tel Aviv"),
    ("Wix Soft", "wix.com", "Europe", "Tel Aviv"),
    ("Monday Soft", "monday.com", "Europe", "Tel Aviv"),
    ("Similarweb Soft", "similarweb.com", "Europe", "Tel Aviv"),
    ("Taboola Soft", "taboola.com", "Europe", "Tel Aviv"),
    ("Outbrain Soft", "outbrain.com", "Europe", "Tel Aviv"),
    ("AppsFlyer Soft", "appsflyer.com", "Europe", "Tel Aviv"),
    ("IronSource Soft", "ironsource.com", "Europe", "Tel Aviv"),
    ("Unity Soft", "unity.com", "Europe", "Copenhagen"),
    ("Playtika Soft", "playtika.com", "Europe", "Tel Aviv"),
    ("Moon Active Soft", "moonactive.com", "Europe", "Tel Aviv"),
    ("Lemonade Soft", "lemonade.com", "Europe", "Tel Aviv"),
    ("Pagaya Soft", "pagaya.com", "Europe", "Tel Aviv"),
    ("Rapyd Soft", "rapyd.net", "Europe", "Tel Aviv"),
    ("Payoneer Soft", "payoneer.com", "Europe", "Tel Aviv"),
    ("eToro Soft", "etoro.com", "Europe", "Tel Aviv"),
    ("Plus500 Soft", "plus500.com", "Europe", "Tel Aviv"),
    ("Riskified Soft", "riskified.com", "Europe", "Tel Aviv"),
    ("Forter Soft", "forter.com", "Europe", "Tel Aviv"),
    ("NICE Soft", "nice.com", "Europe", "Tel Aviv"),
    ("Check Point Soft", "checkpoint.com", "Europe", "Tel Aviv"),
    ("CyberArk Soft", "cyberark.com", "Europe", "Tel Aviv"),
    ("Snyk Soft", "snyk.io", "Europe", "Tel Aviv"),
    ("Wiz Soft", "wiz.io", "Europe", "Tel Aviv"),
    ("Orca Soft", "orca.security", "Europe", "Tel Aviv"),
    ("Aqua Soft", "aquasec.com", "Europe", "Tel Aviv"),
    ("JFrog Soft", "jfrog.com", "Europe", "Tel Aviv"),
    ("Redis Soft", "redis.com", "Europe", "Tel Aviv"),
    ("Gong Soft", "gong.io", "Europe", "Tel Aviv"),
    ("WalkMe Soft", "walkme.com", "Europe", "Tel Aviv"),
    ("Appsheet Soft", "appsheet.com", "Europe", "Tel Aviv"),
    ("HoneyBook Soft", "honeybook.com", "Europe", "Tel Aviv"),
    ("Melio Soft", "meliopayments.com", "Europe", "Tel Aviv"),
    ("Papaya Soft", "papayaglobal.com", "Europe", "Tel Aviv"),
    ("HiBob Soft", "hibob.com", "Europe", "Tel Aviv"),
    ("Lightricks Soft", "lightricks.com", "Europe", "Jerusalem"),
    ("Mobileye Soft", "mobileye.com", "Europe", "Jerusalem"),
    ("OrCam Soft", "orcam.com", "Europe", "Jerusalem"),
    ("StoreDot Soft", "store-dot.com", "Europe", "Herzliya"),
    ("Gett Soft", "gett.com", "Europe", "Tel Aviv"),
    ("Via Soft", "ridewithvia.com", "Europe", "Tel Aviv"),
    ("Moovit Soft", "moovit.com", "Europe", "Tel Aviv"),
    # AU extras
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
    ("Brighte Soft", "brighte.com.au", "Australia", "Sydney"),
    ("Expert Soft", "expert360.com", "Australia", "Sydney"),
    ("Whispir Soft", "whispir.com", "Australia", "Melbourne"),
    ("Finder Soft", "finder.com.au", "Australia", "Sydney"),
    ("Hipages Soft", "hipages.com.au", "Australia", "Sydney"),
    ("Pet Circle Soft", "petcircle.com.au", "Australia", "Sydney"),
    ("Car Next Soft", "carnextdoor.com.au", "Australia", "Sydney"),
    ("Class Soft", "class.com.au", "Australia", "Sydney"),
    ("Kogan Soft", "kogan.com", "Australia", "Melbourne"),
    ("Jora Soft", "jora.com", "Australia", "Melbourne"),
    ("Catch Soft", "catch.com.au", "Australia", "Melbourne"),
    ("REA Soft", "rea-group.com", "Australia", "Melbourne"),
    ("Domain Soft", "domain.com.au", "Australia", "Sydney"),
    ("Carsales Soft", "carsales.com.au", "Australia", "Melbourne"),
    ("Iress Soft", "iress.com", "Australia", "Melbourne"),
    ("Wisetech Soft", "wisetechglobal.com", "Australia", "Sydney"),
    ("Technology Soft", "technologyone.com", "Australia", "Brisbane"),
    ("Xero Soft2", "xero.com.au", "Australia", "Wellington"),
    # MENA
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
    ("Pure Harvest Soft", "pureharvest.ae", "UAE", "Abu Dhabi"),
    ("Magnati Soft", "magnati.com", "UAE", "Dubai"),
    ("Yallacompare Soft", "yallacompare.com", "UAE", "Dubai"),
    ("Now Money Soft", "nowmoney.me", "UAE", "Dubai"),
    ("Foloosi Soft", "foloosi.com", "UAE", "Dubai"),
    ("Nana Soft", "nana.sa", "KSA", "Riyadh"),
    ("Vezeeta Soft", "vezeeta.com", "Egypt", "Cairo"),
    ("MaxAB Soft", "maxab.com", "Egypt", "Cairo"),
    ("Breadfast Soft", "breadfast.com", "Egypt", "Cairo"),
    ("Rabbit Soft", "rabbitmart.com", "Egypt", "Cairo"),
    ("Trella Soft", "trella.app", "Egypt", "Cairo"),
    ("Fawry Soft", "fawry.com", "Egypt", "Cairo"),
    ("PayTabs Soft", "paytabs.com", "KSA", "Riyadh"),
    ("HyperPay Soft", "hyperpay.com", "KSA", "Riyadh"),
    ("Geidea Soft", "geidea.net", "KSA", "Riyadh"),
    ("STC Pay Soft", "stcpay.com.sa", "KSA", "Riyadh"),
    ("Alinma Soft", "alinma.com", "KSA", "Riyadh"),
    ("AlRajhi Soft", "alrajhibank.com.sa", "KSA", "Riyadh"),
    ("SABB Soft", "sabb.com", "KSA", "Riyadh"),
    ("SNB Soft", "alahli.com", "KSA", "Riyadh"),
    ("Riyad Soft", "riyadbank.com", "KSA", "Riyadh"),
    ("FAB Soft", "bankfab.com", "UAE", "Abu Dhabi"),
    ("ADCB Soft", "adcb.com", "UAE", "Abu Dhabi"),
    ("ENBD Soft", "emiratesnbd.com", "UAE", "Dubai"),
    ("Mashreq Soft", "mashreqbank.com", "UAE", "Dubai"),
    ("DIB Soft", "dib.ae", "UAE", "Dubai"),
    ("CBD Soft", "cbd.ae", "UAE", "Dubai"),
    ("RAKBANK Soft", "rakbank.ae", "UAE", "Ras Al Khaimah"),
    ("QNB Soft", "qnb.com", "Qatar", "Doha"),
    ("CBQ Soft", "cbq.qa", "Qatar", "Doha"),
    ("Doha Soft", "dohabank.com.qa", "Qatar", "Doha"),
    ("NBK Soft", "nbk.com", "Kuwait", "Kuwait"),
    ("KFH Soft", "kfh.com", "Kuwait", "Kuwait"),
    ("Boubyan Soft", "bankboubyan.com", "Kuwait", "Kuwait"),
    ("Zain Soft", "zain.com", "Kuwait", "Kuwait"),
    ("Ooredoo Soft", "ooredoo.com", "Qatar", "Doha"),
    ("Etisalat Soft", "etisalat.ae", "UAE", "Abu Dhabi"),
    ("du Soft", "du.ae", "UAE", "Dubai"),
    ("Batelco Soft", "batelco.com", "Bahrain", "Manama"),
    ("stc Soft", "stc.com.sa", "KSA", "Riyadh"),
    # Remote SaaS / AI / infra
    ("Notion Soft", "notion.so", "Remote", "Worldwide"),
    ("Figma Soft", "figma.com", "Remote", "Worldwide"),
    ("Linear Soft", "linear.app", "Remote", "Worldwide"),
    ("Retool Soft", "retool.com", "Remote", "Worldwide"),
    ("Coda Soft", "coda.io", "Remote", "Worldwide"),
    ("Asana Soft", "asana.com", "Remote", "Worldwide"),
    ("ClickUp Soft", "clickup.com", "Remote", "Worldwide"),
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
    ("Zendesk Soft", "zendesk.com", "Remote", "Worldwide"),
    ("Freshworks Soft", "freshworks.com", "Remote", "Worldwide"),
    ("Outreach Soft", "outreach.io", "Remote", "Worldwide"),
    ("Apollo Soft", "apollo.io", "Remote", "Worldwide"),
    ("Clay Soft", "clay.com", "Remote", "Worldwide"),
    ("Cognism Soft", "cognism.com", "Remote", "Worldwide"),
    ("Plaid Soft", "plaid.com", "Remote", "Worldwide"),
    ("Marqeta Soft", "marqeta.com", "Remote", "Worldwide"),
    ("Unit Soft", "unit.co", "Remote", "Worldwide"),
    ("Column Soft", "column.com", "Remote", "Worldwide"),
    ("Modern Soft", "moderntreasury.com", "Remote", "Worldwide"),
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
    ("Duolingo Soft", "duolingo.com", "Remote", "Worldwide"),
    ("Coursera Soft", "coursera.org", "Remote", "Worldwide"),
    ("Grammarly Soft", "grammarly.com", "Remote", "Worldwide"),
    ("Raycast Soft", "raycast.com", "Remote", "Worldwide"),
    ("Warp Soft", "warp.dev", "Remote", "Worldwide"),
    ("Sourcegraph Soft", "sourcegraph.com", "Remote", "Worldwide"),
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
    ("Upstash Soft", "upstash.com", "Remote", "Worldwide"),
    ("Dragonfly Soft", "dragonflydb.io", "Remote", "Worldwide"),
    ("Baserow Soft", "baserow.io", "Europe", "Amsterdam"),
    ("HERE Soft", "here.com", "Europe", "Berlin"),
    ("Felt Soft", "felt.com", "Remote", "Worldwide"),
    ("Plausible Soft", "plausible.io", "Europe", "Tallinn"),
    ("Brex Soft", "brex.com", "Remote", "Worldwide"),
    ("Ramp Soft", "ramp.com", "Remote", "Worldwide"),
    ("Mercury Soft", "mercury.com", "Remote", "Worldwide"),
    ("Affirm Soft", "affirm.com", "Remote", "Worldwide"),
    ("Block Soft", "block.xyz", "Remote", "Worldwide"),
    ("Square Soft", "squareup.com", "Remote", "Worldwide"),
    ("Cash Soft", "cash.app", "Remote", "Worldwide"),
    ("Faire Soft", "faire.com", "Remote", "Worldwide"),
    ("Flexport Soft", "flexport.com", "Remote", "Worldwide"),
    ("ShipBob Soft", "shipbob.com", "Remote", "Worldwide"),
    ("Teikametrics Soft", "teikametrics.com", "Remote", "Worldwide"),
    ("Instacart Soft", "instacart.com", "Remote", "Worldwide"),
    ("DoorDash Soft", "doordash.com", "Remote", "Worldwide"),
    ("Uber Soft", "uber.com", "Remote", "Worldwide"),
    ("Lyft Soft", "lyft.com", "Remote", "Worldwide"),
    ("Airbnb Soft", "airbnb.com", "Remote", "Worldwide"),
    ("Booking Soft", "booking.com", "Europe", "Amsterdam"),
    ("Expedia Soft", "expedia.com", "Remote", "Worldwide"),
    ("Tripadvisor Soft", "tripadvisor.com", "Remote", "Worldwide"),
    ("Priceline Soft", "priceline.com", "Remote", "Worldwide"),
    ("Kayak Soft", "kayak.com", "Remote", "Worldwide"),
    ("Hopper Soft", "hopper.com", "Remote", "Worldwide"),
    ("SeatGeek Soft", "seatgeek.com", "Remote", "Worldwide"),
    ("StubHub Soft", "stubhub.com", "Remote", "Worldwide"),
    ("Ticketmaster Soft", "ticketmaster.com", "Remote", "Worldwide"),
    ("Eventbrite Soft", "eventbrite.com", "Remote", "Worldwide"),
    ("Discord Soft", "discord.com", "Remote", "Worldwide"),
    ("Slack Soft", "slack.com", "Remote", "Worldwide"),
    ("Zoom Soft", "zoom.us", "Remote", "Worldwide"),
    ("Dropbox Soft", "dropbox.com", "Remote", "Worldwide"),
    ("Box Soft", "box.com", "Remote", "Worldwide"),
    ("DocuSign Soft", "docusign.com", "Remote", "Worldwide"),
    ("Adobe Soft", "adobe.com", "Remote", "Worldwide"),
    ("Autodesk Soft", "autodesk.com", "Remote", "Worldwide"),
    ("Salesforce Soft", "salesforce.com", "Remote", "Worldwide"),
    ("ServiceNow Soft", "servicenow.com", "Remote", "Worldwide"),
    ("Palantir Soft", "palantir.com", "Remote", "Worldwide"),
    ("Snowflake Soft2", "snowflakecomputing.com", "Remote", "Worldwide"),
    ("Databricks Soft2", "databricks.net", "Remote", "Worldwide"),
    ("Hugging Soft", "huggingface.co", "Remote", "Worldwide"),
    ("Replicate Soft", "replicate.com", "Remote", "Worldwide"),
    ("Modal Soft", "modal.com", "Remote", "Worldwide"),
    ("Anyscale Soft", "anyscale.com", "Remote", "Worldwide"),
    ("Baseten Soft", "baseten.co", "Remote", "Worldwide"),
    ("Banana Soft", "banana.dev", "Remote", "Worldwide"),
    ("Cerebras Soft", "cerebras.net", "Remote", "Worldwide"),
    ("SambaNova Soft", "sambanova.ai", "Remote", "Worldwide"),
    ("Adept Soft", "adept.ai", "Remote", "Worldwide"),
    ("Character Soft", "character.ai", "Remote", "Worldwide"),
    ("Inflection Soft", "inflection.ai", "Remote", "Worldwide"),
    ("Anthropic Soft", "anthropic.com", "Remote", "Worldwide"),
    ("OpenAI Soft", "openai.com", "Remote", "Worldwide"),
    ("xAI Soft", "x.ai", "Remote", "Worldwide"),
    ("Grok Soft", "grok.x.ai", "Remote", "Worldwide"),
    ("Midjourney Soft", "midjourney.com", "Remote", "Worldwide"),
    ("Stability Soft2", "stability.ai", "Europe", "London"),
    ("Pika Soft", "pika.art", "Remote", "Worldwide"),
    ("Luma Soft", "lumalabs.ai", "Remote", "Worldwide"),
    ("HeyGen Soft", "heygen.com", "Remote", "Worldwide"),
    ("Synthesia Soft2", "synthesia.io", "Europe", "London"),
    ("Tome Soft", "tome.app", "Remote", "Worldwide"),
    ("Gamma Soft", "gamma.app", "Remote", "Worldwide"),
    ("Beautiful Soft", "beautiful.ai", "Remote", "Worldwide"),
    ("Pitch Soft", "pitch.com", "Europe", "Berlin"),
    ("Canva Soft2", "canva.com", "Australia", "Sydney"),
    ("Figma Soft2", "figma.com", "Remote", "Worldwide"),
    ("Miro Soft2", "miro.com", "Europe", "Amsterdam"),
    ("Mural Soft", "mural.co", "Remote", "Worldwide"),
    ("Whimsical Soft", "whimsical.com", "Remote", "Worldwide"),
    ("Excalidraw Soft", "excalidraw.com", "Remote", "Worldwide"),
    ("tldraw Soft", "tldraw.com", "Remote", "Worldwide"),
    ("Coda Soft2", "coda.io", "Remote", "Worldwide"),
    ("Airtable Soft", "airtable.com", "Remote", "Worldwide"),
    ("Smartsheet Soft", "smartsheet.com", "Remote", "Worldwide"),
    ("Monday Soft2", "monday.com", "Remote", "Worldwide"),
    ("Asana Soft2", "asana.com", "Remote", "Worldwide"),
    ("Jira Soft", "atlassian.com", "Australia", "Sydney"),
    ("Linear Soft2", "linear.app", "Remote", "Worldwide"),
    ("Height Soft", "height.app", "Remote", "Worldwide"),
    ("Shortcut Soft", "shortcut.com", "Remote", "Worldwide"),
    ("Plane Soft", "plane.so", "Remote", "Worldwide"),
    ("Basecamp Soft", "basecamp.com", "Remote", "Worldwide"),
    ("Todoist Soft", "todoist.com", "Remote", "Worldwide"),
    ("TickTick Soft", "ticktick.com", "Remote", "Worldwide"),
    ("Things Soft", "culturedcode.com", "Remote", "Worldwide"),
    ("Obsidian Soft", "obsidian.md", "Remote", "Worldwide"),
    ("Roam Soft", "roamresearch.com", "Remote", "Worldwide"),
    ("Logseq Soft", "logseq.com", "Remote", "Worldwide"),
    ("Reflect Soft", "reflect.app", "Remote", "Worldwide"),
    ("Mem Soft", "mem.ai", "Remote", "Worldwide"),
    ("Craft Soft", "craft.do", "Europe", "London"),
    ("Bear Soft", "bear.app", "Europe", "Italy"),
    ("Ulysses Soft", "ulysses.app", "Europe", "Germany"),
    ("iA Soft", "ia.net", "Europe", "Zurich"),
    ("Arc Soft", "arc.net", "Remote", "Worldwide"),
    ("Brave Soft", "brave.com", "Remote", "Worldwide"),
    ("Opera Soft", "opera.com", "Europe", "Oslo"),
    ("Vivaldi Soft", "vivaldi.com", "Europe", "Oslo"),
    ("The Browser Soft", "thebrowser.company", "Remote", "Worldwide"),
    ("Dia Soft", "diabrowser.com", "Remote", "Worldwide"),
    ("Comet Soft", "comet.browser", "Remote", "Worldwide"),
    ("Sigma Soft2", "sigmacomputing.com", "Remote", "Worldwide"),
    ("Omni Soft", "omni.co", "Remote", "Worldwide"),
    ("Lightdash Soft", "lightdash.com", "Remote", "Worldwide"),
    ("Evidence Soft", "evidence.dev", "Remote", "Worldwide"),
    ("Observable Soft", "observablehq.com", "Remote", "Worldwide"),
    ("Streamlit Soft", "streamlit.io", "Remote", "Worldwide"),
    ("Gradio Soft", "gradio.app", "Remote", "Worldwide"),
    ("Plotly Soft", "plotly.com", "Remote", "Worldwide"),
    ("Tableau Soft", "tableau.com", "Remote", "Worldwide"),
    ("Qlik Soft", "qlik.com", "Remote", "Worldwide"),
    ("Sisense Soft", "sisense.com", "Remote", "Worldwide"),
    ("Domo Soft", "domo.com", "Remote", "Worldwide"),
    ("Looker Soft", "looker.com", "Remote", "Worldwide"),
    ("Mode Soft", "mode.com", "Remote", "Worldwide"),
    ("Preset Soft", "preset.io", "Remote", "Worldwide"),
    ("Redash Soft", "redash.io", "Remote", "Worldwide"),
    ("Superset Soft", "apachesuperset.com", "Remote", "Worldwide"),
    ("Monte Soft", "montecarlodata.com", "Remote", "Worldwide"),
    ("Anomalo Soft", "anomalo.com", "Remote", "Worldwide"),
    ("Great Soft", "greatexpectations.io", "Remote", "Worldwide"),
    ("Soda Soft", "soda.io", "Remote", "Worldwide"),
    ("Elementary Soft", "elementary.io", "Remote", "Worldwide"),
    ("dbt Soft2", "dbtlabs.com", "Remote", "Worldwide"),
    ("Transform Soft", "transform.co", "Remote", "Worldwide"),
    ("Atlan Soft", "atlan.com", "Remote", "Worldwide"),
    ("Alation Soft", "alation.com", "Remote", "Worldwide"),
    ("Collibra Soft", "collibra.com", "Europe", "Brussels"),
    ("Informatica Soft", "informatica.com", "Remote", "Worldwide"),
    ("Talend Soft", "talend.com", "Europe", "Paris"),
    ("Fivetran Soft2", "fivetran.com", "Remote", "Worldwide"),
    ("Stitch Soft", "stitchdata.com", "Remote", "Worldwide"),
    ("Matillion Soft", "matillion.com", "Europe", "Manchester"),
    ("Airbyte Soft2", "airbyte.com", "Remote", "Worldwide"),
    ("Meltano Soft", "meltano.com", "Remote", "Worldwide"),
    ("Singer Soft", "singer.io", "Remote", "Worldwide"),
    ("Census Soft2", "getcensus.com", "Remote", "Worldwide"),
    ("Hightouch Soft", "hightouch.com", "Remote", "Worldwide"),
    ("RudderStack Soft", "rudderstack.com", "Remote", "Worldwide"),
    ("Segment Soft", "segment.com", "Remote", "Worldwide"),
    ("mParticle Soft", "mparticle.com", "Remote", "Worldwide"),
    ("Tealium Soft", "tealium.com", "Remote", "Worldwide"),
    ("Treasure Soft", "treasuredata.com", "Remote", "Worldwide"),
    ("Amperity Soft", "amperity.com", "Remote", "Worldwide"),
    ("ActionIQ Soft", "actioniq.com", "Remote", "Worldwide"),
    ("BlueConic Soft", "blueconic.com", "Remote", "Worldwide"),
    ("Iterable Soft", "iterable.com", "Remote", "Worldwide"),
    ("Braze Soft", "braze.com", "Remote", "Worldwide"),
    ("Customer Soft2", "customer.io", "Remote", "Worldwide"),
    ("OneSignal Soft", "onesignal.com", "Remote", "Worldwide"),
    ("Pushwoosh Soft", "pushwoosh.com", "Remote", "Worldwide"),
    ("Airship Soft", "airship.com", "Remote", "Worldwide"),
    ("Leanplum Soft", "leanplum.com", "Remote", "Worldwide"),
    ("CleverTap Soft", "clevertap.com", "Remote", "Worldwide"),
    ("MoEngage Soft", "moengage.com", "Remote", "Worldwide"),
    ("WebEngage Soft", "webengage.com", "Remote", "Worldwide"),
    ("Insider Soft", "useinsider.com", "Europe", "Istanbul"),
    ("Adjust Soft2", "adjust.com", "Europe", "Berlin"),
    ("AppsFlyer Soft2", "appsflyer.com", "Europe", "Tel Aviv"),
    ("Branch Soft", "branch.io", "Remote", "Worldwide"),
    ("Singular Soft", "singular.net", "Remote", "Worldwide"),
    ("Kochava Soft", "kochava.com", "Remote", "Worldwide"),
    ("Tenjin Soft", "tenjin.com", "Remote", "Worldwide"),
    ("GameAnalytics Soft", "gameanalytics.com", "Europe", "Copenhagen"),
    ("Unity Soft2", "unity3d.com", "Europe", "Copenhagen"),
    ("Epic Soft", "epicgames.com", "Remote", "Worldwide"),
    ("Riot Soft", "riotgames.com", "Remote", "Worldwide"),
    ("Valve Soft", "valvesoftware.com", "Remote", "Worldwide"),
    ("Roblox Soft", "roblox.com", "Remote", "Worldwide"),
    ("Niantic Soft", "nianticlabs.com", "Remote", "Worldwide"),
    ("Supercell Soft2", "supercell.com", "Europe", "Helsinki"),
    ("King Soft", "king.com", "Europe", "Stockholm"),
    ("Playrix Soft", "playrix.com", "Europe", "Dublin"),
    ("Zynga Soft", "zynga.com", "Remote", "Worldwide"),
    ("Take Two Soft", "take2games.com", "Remote", "Worldwide"),
    ("EA Soft", "ea.com", "Remote", "Worldwide"),
    ("Ubisoft Soft", "ubisoft.com", "Europe", "Paris"),
    ("CD Projekt Soft", "cdprojekt.com", "Europe", "Warsaw"),
    ("Embracer Soft", "embracer.com", "Europe", "Stockholm"),
    ("Paradox Soft", "paradoxinteractive.com", "Europe", "Stockholm"),
    ("Frontier Soft", "frontier.co.uk", "Europe", "Cambridge"),
    ("Jagex Soft", "jagex.com", "Europe", "Cambridge"),
    ("Rebellion Soft", "rebellion.com", "Europe", "Oxford"),
    ("Sumo Soft", "sumo-digital.com", "Europe", "Sheffield"),
    ("Splash Soft", "splashdamage.com", "Europe", "London"),
    ("Rockstar Soft", "rockstargames.com", "Remote", "Worldwide"),
    ("Bungie Soft", "bungie.net", "Remote", "Worldwide"),
    ("Blizzard Soft", "blizzard.com", "Remote", "Worldwide"),
    ("Activision Soft", "activision.com", "Remote", "Worldwide"),
    ("Bethesda Soft", "bethesda.net", "Remote", "Worldwide"),
    ("id Soft", "idsoftware.com", "Remote", "Worldwide"),
    ("Machine Soft", "machinezone.com", "Remote", "Worldwide"),
    ("Scopely Soft", "scopely.com", "Remote", "Worldwide"),
    ("Glu Soft", "glu.com", "Remote", "Worldwide"),
    ("Kabam Soft", "kabam.com", "Remote", "Worldwide"),
    ("Nexon Soft", "nexon.com", "Remote", "Worldwide"),
    ("Netmarble Soft", "netmarble.com", "Remote", "Worldwide"),
    ("NCSoft Soft", "ncsoft.com", "Remote", "Worldwide"),
    ("Krafton Soft", "krafton.com", "Remote", "Worldwide"),
    ("Smilegate Soft", "smilegate.com", "Remote", "Worldwide"),
    ("Com2uS Soft", "com2us.com", "Remote", "Worldwide"),
    ("Kakao Soft", "kakaogames.com", "Remote", "Worldwide"),
    ("Line Soft", "linecorp.com", "Remote", "Worldwide"),
    ("Naver Soft", "navercorp.com", "Remote", "Worldwide"),
    ("Coupang Soft", "coupang.com", "Remote", "Worldwide"),
    ("Tokopedia Soft", "tokopedia.com", "Remote", "Worldwide"),
    ("Bukalapak Soft", "bukalapak.com", "Remote", "Worldwide"),
    ("Gojek Soft", "gojek.com", "Remote", "Worldwide"),
    ("Grab Soft", "grab.com", "Remote", "Worldwide"),
    ("Sea Soft", "sea.com", "Remote", "Worldwide"),
    ("Shopee Soft", "shopee.com", "Remote", "Worldwide"),
    ("Lazada Soft", "lazada.com", "Remote", "Worldwide"),
    ("Carousell Soft", "carousell.com", "Remote", "Worldwide"),
    ("PropertyGuru Soft", "propertyguru.com", "Remote", "Worldwide"),
    ("Traveloka Soft", "traveloka.com", "Remote", "Worldwide"),
    ("Agoda Soft", "agoda.com", "Remote", "Worldwide"),
    ("Booking Soft2", "bookingholdings.com", "Remote", "Worldwide"),
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
    for item in plan[:60]:
        print(f"  {item[3]:32} {item[2]} [{item[1]}]", flush=True)

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
    target = 28
    for i, (_, region, name, domain, city, locs) in enumerate(plan, 1):
        if len(found) >= target:
            print("hit", target, flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(plan)}] {email}", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.35)
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

    out = ROOT / "output/emails_shortlist_batch40_2026-08-16.csv"
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
