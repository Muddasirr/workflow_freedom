#!/usr/bin/env python3
"""Probe batch27 — PK / MENA / Europe / Australia / remote for remaining daily slots."""
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

NEW = [
    # Pakistan / Karachi product & software houses
    ("Techverx PK", "techverx.com", "Pakistan", "Lahore"),
    ("PureLogics PK", "purelogics.com", "Pakistan", "Lahore"),
    ("Nextbridge PK", "nextbridge.com.pk", "Pakistan", "Lahore"),
    ("Rolustech PK", "rolustech.com", "Pakistan", "Lahore"),
    ("Sekel Tech PK", "sekel.tech", "Pakistan", "Lahore"),
    ("DevBatch PK", "devbatch.com", "Pakistan", "Lahore"),
    ("Speridian PK", "speridian.com", "Pakistan", "Islamabad"),
    ("Zigron PK", "zigron.com", "Pakistan", "Islamabad"),
    ("HazenTech PK", "hazentech.com", "Pakistan", "Islamabad"),
    ("LMKT PK", "lmkt.com", "Pakistan", "Islamabad"),
    ("Netsmartz PK", "netsmartz.com", "Pakistan", "Lahore"),
    ("Elixir Technologies PK", "elixir.com.pk", "Pakistan", "Islamabad"),
    ("DPL PK", "dpl.com.pk", "Pakistan", "Islamabad"),
    ("Empiric PK", "empiric.com.pk", "Pakistan", "Lahore"),
    ("Recur PK", "recur.com.pk", "Pakistan", "Lahore"),
    ("Arpatech PK", "arpatech.com", "Karachi", "Karachi"),
    ("Mindstorm Studios PK", "mindstormstudios.com", "Karachi", "Karachi"),
    ("Vizteck Solutions PK", "vizteck.com", "Karachi", "Karachi"),
    ("Genetech Solutions PK", "genetechsolutions.com", "Karachi", "Karachi"),
    ("Powersoft19 PK", "powersoft19.com", "Pakistan", "Lahore"),
    ("Shophive PK", "shophive.com", "Pakistan", "Lahore"),
    ("Trax PK", "trax.pk", "Karachi", "Karachi"),
    ("Keenu PK", "keenu.com", "Karachi", "Karachi"),
    ("Haball PK", "haball.com", "Karachi", "Karachi"),
    ("Sastaticket PK", "sastaticket.com.pk", "Karachi", "Karachi"),
    ("Retailistan PK", "retailistan.co", "Karachi", "Karachi"),
    ("Dastgyr Soft", "dastgyr.co", "Karachi", "Karachi"),
    ("Golootlo Soft", "golootlo.com.pk", "Karachi", "Karachi"),
    ("Swich Soft", "swich.com", "Karachi", "Karachi"),
    ("Mauqa Soft", "mauqa.pk", "Pakistan", "Lahore"),
    ("FindMyProfessionals Soft", "findmyprofessionals.pk", "Pakistan", "Lahore"),
    ("Gaditek Soft", "gaditek.com", "Karachi", "Karachi"),
    ("Salsoft Soft", "salsoft.net", "Karachi", "Karachi"),
    ("SSI Decisions Soft", "ssidecisions.com", "Karachi", "Karachi"),
    ("Avanza Solutions Soft", "avanzasolutions.com", "Karachi", "Karachi"),
    ("KalSoft Soft", "kalsoft.com", "Karachi", "Karachi"),
    ("Inbox Business Soft", "inboxbiz.com", "Karachi", "Karachi"),
    ("KoderLabs Soft", "koderlabs.com", "Karachi", "Karachi"),
    ("Softinlays Soft", "softinlays.pk", "Pakistan", "Lahore"),
    ("SoftAct Soft", "softact.pk", "Pakistan", "Islamabad"),
    ("TechVista Soft", "techvista.com.pk", "Pakistan", "Lahore"),
    ("Softsquare Soft", "softsquare.com.pk", "Pakistan", "Lahore"),
    ("Synergy IT Soft", "synergyit.com.pk", "Pakistan", "Lahore"),
    ("CyberVision Soft", "cybervision.com.pk", "Pakistan", "Islamabad"),
    ("Appxolute Soft", "appxolute.pk", "Pakistan", "Islamabad"),
    ("Codehouse Soft", "codehouse.com.pk", "Pakistan", "Islamabad"),
    ("Techverce Soft", "techverce.pk", "Pakistan", "Lahore"),
    ("Codility Solutions Soft", "codilitysolutions.pk", "Pakistan", "Lahore"),
    ("ApexSoft Soft", "apexsoft.com.pk", "Pakistan", "Lahore"),
    ("FolioSoft Soft", "foliosoft.pk", "Pakistan", "Lahore"),
    ("CresTech Soft", "crestech.com.pk", "Pakistan", "Lahore"),
    ("SoftPyramid Soft", "softpyramid.net", "Pakistan", "Lahore"),
    ("Sofizar Soft", "sofizar.net", "Pakistan", "Lahore"),
    ("Logicose Soft", "logicose.net", "Pakistan", "Lahore"),
    ("Ebryx Soft", "ebryx.net", "Pakistan", "Lahore / remote"),
    ("VTeams Soft", "vteams.net", "Pakistan", "Lahore / remote"),
    ("WebHR Soft", "webhr.net", "Pakistan", "Lahore / remote"),
    ("Fermat Soft", "fermat.pk", "Pakistan", "Lahore / remote"),
    ("Dukan Soft", "getdukan.com", "Pakistan", "Lahore / remote"),
    ("PriceOye Soft", "priceoye.net", "Pakistan", "Lahore"),
    ("Bookme Soft", "bookme.com", "Pakistan", "Lahore"),
    ("Dawaai Soft", "dawaai.net", "Karachi", "Karachi"),
    ("Abhi Soft", "abhi.com", "Karachi", "Karachi"),
    ("NayaPay Soft", "nayapay.net", "Karachi", "Karachi"),
    ("Bazaar Technologies Soft", "bazaartechnologies.com", "Karachi", "Karachi"),
    ("Retailo Technologies Soft", "retailotechnologies.com", "Karachi", "Karachi"),
    ("SadaPay Soft", "sadapay.net", "Karachi", "Karachi"),
    ("Finja Soft", "finja.net", "Pakistan", "Lahore"),
    ("Tez Financial Soft", "tez.com.pk", "Pakistan", "Lahore"),
    ("Rozee Soft", "rozee.com.pk", "Pakistan", "Lahore / remote"),
    ("BrightSpyre Soft", "brightspyre.net", "Pakistan", "Islamabad"),
    ("Mustakbil Soft", "mustakbil.pk", "Pakistan", "Karachi / remote"),
    ("Bykea Soft", "bykea.com.pk", "Karachi", "Karachi"),
    ("Airlift Technologies Soft", "airlift.pk", "Karachi", "Karachi"),
    ("Foodpanda Soft", "foodpanda.com", "Karachi", "Karachi"),
    ("Daraz Soft", "daraz.com", "Karachi", "Karachi"),
    ("PakWheels Soft", "pakwheels.net", "Karachi", "Karachi"),
    ("Zameen Soft", "zameen.net", "Karachi", "Karachi"),
    ("OLX Soft", "olxgroup.com", "Karachi", "Karachi"),
    ("Systems Limited Soft", "systemsltd.pk", "Pakistan", "Lahore / remote"),
    ("Netsol Soft", "netsol.com", "Pakistan", "Lahore / remote"),
    ("10Pearls Soft", "10pearls.net", "Pakistan", "Karachi / remote"),
    ("Arbisoft Soft", "arbisoft.net", "Pakistan", "Lahore / remote"),
    ("VentureDive Soft", "venturedive.net", "Pakistan", "Karachi / remote"),
    ("Confiz Soft", "confiz.net", "Pakistan", "Lahore / remote"),
    ("Emumba Soft", "emumba.net", "Pakistan", "Islamabad / remote"),
    ("Devsinc Soft", "devsinc.net", "Pakistan", "Lahore / remote"),
    ("Tkxel Soft", "tkxel.net", "Pakistan", "Lahore / remote"),
    ("Afiniti Soft", "afiniti.net", "Pakistan", "Islamabad / remote"),
    ("Tintash Soft", "tintash.org", "Karachi", "Karachi"),
    ("Xgrid Soft", "xgrid.co.uk", "Karachi", "Karachi"),
    ("Creative Chaos Soft", "creativechaos.com.pk", "Karachi", "Karachi"),
    ("NorthBay Soft", "northbay.co", "Karachi", "Karachi"),
    ("Techlogix Soft", "techlogix.co", "Karachi", "Karachi"),
    ("Contour Soft", "contoursoftware.pk", "Karachi", "Karachi"),
    ("Folio3 Soft", "folio3.pk", "Karachi", "Karachi"),
    # Kuwait / Qatar / UAE / KSA / Egypt
    ("UPayments Soft", "upayments.kw", "Kuwait", "Kuwait / remote"),
    ("SkipCash Soft", "skipcash.kw", "Kuwait", "Kuwait / remote"),
    ("Tap Payments Soft", "tap.company", "Kuwait", "Kuwait / remote"),
    ("MyFatoorah Soft", "myfatoorah.com.kw", "Kuwait", "Kuwait / remote"),
    ("Jeel Soft", "jeel.app", "Kuwait", "Kuwait / remote"),
    ("Xcite Soft", "xcite.com.kw", "Kuwait", "Kuwait"),
    ("Warba Soft", "warba.com.kw", "Kuwait", "Kuwait"),
    ("Kamco Soft", "kamco.com.kw", "Kuwait", "Kuwait"),
    ("Markaz Soft", "markaz.com.kw", "Kuwait", "Kuwait"),
    ("Tabby Soft", "tabby.com", "UAE", "Dubai / remote"),
    ("Tamara Soft", "tamara.ai", "KSA", "Riyadh / remote"),
    ("PostPay Soft", "getpostpay.com", "UAE", "Dubai / remote"),
    ("Spotii Soft", "spotii.ae", "UAE", "Dubai / remote"),
    ("Sarwa Soft", "sarwa.com", "UAE", "Dubai / remote"),
    ("Wahed Soft", "wahedinvest.com", "UAE", "Dubai / remote"),
    ("Bayzat Soft", "bayzat.ae", "UAE", "Dubai / remote"),
    ("Mamo Soft", "mamopay.ae", "UAE", "Dubai / remote"),
    ("Lean Technologies Soft", "leantechnologies.com", "UAE", "Dubai / remote"),
    ("Tarabut Soft", "tarabut.me", "Bahrain", "Manama / remote"),
    ("PayTabs Soft", "paytabs.sa", "KSA", "Riyadh / remote"),
    ("HyperPay Soft", "hyperpay.sa", "KSA", "Riyadh / remote"),
    ("Moyasar Soft", "moyasar.sa", "KSA", "Riyadh / remote"),
    ("Foodics Soft", "foodics.co", "KSA", "Riyadh / remote"),
    ("Salla Soft", "salla.com.sa", "KSA", "Riyadh / remote"),
    ("Zid Soft", "zid.com.sa", "KSA", "Riyadh / remote"),
    ("Jahez Soft", "jahez.com.sa", "KSA", "Riyadh / remote"),
    ("HungerStation Soft", "hungerstation.sa", "KSA", "Riyadh / remote"),
    ("Mrsool Soft", "mrsool.sa", "KSA", "Riyadh / remote"),
    ("Nana Soft", "nana.com.sa", "KSA", "Riyadh / remote"),
    ("Unifonic Soft", "unifonic.sa", "KSA", "Riyadh / remote"),
    ("Careem Soft", "careem.ae", "UAE", "Dubai / remote"),
    ("Noon Soft", "noon.partners", "UAE", "Dubai / remote"),
    ("Property Finder Soft", "propertyfinder.group", "UAE", "Dubai / remote"),
    ("Bayut Soft", "bayutgroup.com", "UAE", "Dubai / remote"),
    ("Dubizzle Soft", "dubizzle.group", "UAE", "Dubai / remote"),
    ("GulfTalent Soft", "gulftalent.com", "UAE", "Dubai / remote"),
    ("OpenSooq Soft", "opensooq.jo", "Jordan", "Amman / remote"),
    ("Mawdoo3 Soft", "mawdoo3.net", "Jordan", "Amman / remote"),
    ("MadfooatCom Soft", "madfooat.com.jo", "Jordan", "Amman / remote"),
    ("Instabug Soft", "instabug.eg", "Egypt", "Cairo / remote"),
    ("Paymob Soft", "paymob.eg", "Egypt", "Cairo / remote"),
    ("MoneyFellows Soft", "moneyfellows.eg", "Egypt", "Cairo / remote"),
    ("Telda Soft", "telda.eg", "Egypt", "Cairo / remote"),
    ("Halan Soft", "halan.eg", "Egypt", "Cairo / remote"),
    ("Trella Soft", "trella.eg", "Egypt", "Cairo / remote"),
    ("Breadfast Soft", "breadfast.eg", "Egypt", "Cairo / remote"),
    ("MaxAB Soft", "maxab.eg", "Egypt", "Cairo / remote"),
    ("Vezeeta Soft", "vezeeta.eg", "Egypt", "Cairo / remote"),
    ("Swvl Soft", "swvl.eg", "Egypt", "Cairo / remote"),
    ("Rabbit Soft", "rabbit.eg", "Egypt", "Cairo / remote"),
    ("Elmenus Soft", "elmenus.eg", "Egypt", "Cairo / remote"),
    ("Fawry Soft", "fawry.eg", "Egypt", "Cairo / remote"),
    ("Valify Soft", "valify.eg", "Egypt", "Cairo / remote"),
    ("Khazna Soft", "khazna.eg", "Egypt", "Cairo / remote"),
    ("Eventtus Soft", "eventtus.eg", "Egypt", "Cairo / remote"),
    ("Flat6Labs Soft", "flat6labs.eg", "Egypt", "Cairo / remote"),
    ("QNB Soft", "qnb.qa", "Qatar", "Doha"),
    ("CBQ Soft", "commercialbank.qa", "Qatar", "Doha"),
    ("Doha Bank Soft", "dohabank.qa", "Qatar", "Doha"),
    ("Ooredoo Soft", "ooredoo.com.qa", "Qatar", "Doha"),
    ("Beeah Soft", "beeah.group", "UAE", "Sharjah / remote"),
    ("Majid Al Futtaim Soft", "majidalfuttaim.ae", "UAE", "Dubai / remote"),
    ("Emaar Soft", "emaar.ae", "UAE", "Dubai / remote"),
    ("DP World Soft", "dpworld.ae", "UAE", "Dubai / remote"),
    ("Magnati Soft", "magnati.ae", "UAE", "Dubai / remote"),
    ("Network International Soft", "networkinternational.ae", "UAE", "Dubai / remote"),
    ("Stc Pay Soft", "stcpay.sa", "KSA", "Riyadh / remote"),
    ("Boom Soft", "boom.com.sa", "KSA", "Riyadh / remote"),
    # Australia
    ("Deputy Soft", "deputy.app", "Australia", "Sydney / remote"),
    ("Employment Hero Soft", "employmenthero.com.au", "Australia", "Sydney / remote"),
    ("Culture Amp Soft", "cultureamp.app", "Australia", "Melbourne / remote"),
    ("SafetyCulture Soft", "safetyculture.app", "Australia", "Sydney / remote"),
    ("Buildkite Soft", "buildkite.app", "Australia", "Melbourne / remote"),
    ("Immutable Soft", "immutable.games", "Australia", "Sydney / remote"),
    ("Linktree Soft", "linktree.app", "Australia", "Melbourne / remote"),
    ("Airwallex Soft", "airwallex.app", "Australia", "Melbourne / remote"),
    ("Propeller Soft", "propeller.aero", "Australia", "Sydney / remote"),
    ("Nitro Soft", "gonitro.com.au", "Australia", "Sydney / remote"),
    ("SiteMinder Soft", "siteminder.app", "Australia", "Sydney / remote"),
    ("Expert360 Soft", "expert360.app", "Australia", "Sydney / remote"),
    ("Airtasker Soft", "airtasker.app", "Australia", "Sydney / remote"),
    ("Brighte Soft", "brighte.app", "Australia", "Sydney / remote"),
    ("Prospa Soft", "prospa.app", "Australia", "Sydney / remote"),
    ("Tyro Soft", "tyro.bank", "Australia", "Sydney / remote"),
    ("Nearmap Soft", "nearmap.app", "Australia", "Sydney / remote"),
    ("Finder Soft", "finder.com", "Australia", "Sydney / remote"),
    ("Envato Soft", "envato.com.au", "Australia", "Melbourne / remote"),
    ("Campaign Monitor Soft", "campaignmonitor.com.au", "Australia", "Sydney / remote"),
    ("Afterpay Soft", "afterpay.com.au", "Australia", "Melbourne / remote"),
    ("Zip Soft", "zip.com.au", "Australia", "Sydney / remote"),
    ("Xero Soft", "xero.com.au", "Australia", "Wellington / remote"),
    ("MYOB Soft", "myob.com.au", "Australia", "Melbourne / remote"),
    ("REA Soft", "rea.com.au", "Australia", "Melbourne / remote"),
    ("Seek Soft", "seek.com", "Australia", "Melbourne / remote"),
    ("Carsales Soft", "carsales.com", "Australia", "Melbourne / remote"),
    ("Domain Soft", "domain.com", "Australia", "Sydney / remote"),
    ("Local Measure Soft", "localmeasure.com.au", "Australia", "Sydney / remote"),
    # Europe product
    ("Personio Soft", "personio.app", "Europe", "Munich / remote"),
    ("Leapsome Soft", "leapsome.app", "Europe", "Berlin / remote"),
    ("Kenjo Soft", "kenjo.com", "Europe", "Berlin / remote"),
    ("Factorial Soft", "factorial.app", "Europe", "Barcelona / remote"),
    ("Hibob Soft", "hibob.app", "Europe", "London / remote"),
    ("CharlieHR Soft", "charlie.com", "Europe", "London / remote"),
    ("Breathe Soft", "breathe.com", "Europe", "London / remote"),
    ("Contentful Soft", "contentful.app", "Europe", "Berlin / remote"),
    ("SumUp Soft", "sumup.app", "Europe", "London / remote"),
    ("Trade Republic Soft", "traderepublic.app", "Europe", "Berlin / remote"),
    ("GetYourGuide Soft", "getyourguide.app", "Europe", "Berlin / remote"),
    ("Mollie Soft", "mollie.app", "Europe", "Amsterdam / remote"),
    ("Bunq Soft", "bunq.app", "Europe", "Amsterdam / remote"),
    ("MessageBird Soft", "messagebird.app", "Europe", "Amsterdam / remote"),
    ("Aiven Soft", "aiven.app", "Europe", "Helsinki / remote"),
    ("Weaviate Soft", "weaviate.app", "Europe", "Amsterdam / remote"),
    ("Qdrant Soft", "qdrant.app", "Europe", "Berlin / remote"),
    ("Deepset Soft", "deepset.app", "Europe", "Berlin / remote"),
    ("Neptune Soft", "neptune.app", "Europe", "Warsaw / remote"),
    ("Plausible Soft", "plausible.app", "Europe", "Tallinn / remote"),
    ("Softr Soft", "softr.app", "Europe", "Berlin / remote"),
    ("Gitpod Soft", "gitpod.app", "Europe", "Kiel / remote"),
    ("Tyk Soft", "tyk.app", "Europe", "London / remote"),
    ("Gravitee Soft", "gravitee.app", "Europe", "Lille / remote"),
    ("Attio Soft", "attio.app", "Europe", "London / remote"),
    ("Alan Soft", "alan.app", "Europe", "Paris / remote"),
    ("Doctolib Soft", "doctolib.app", "Europe", "Paris / remote"),
    ("Spendesk Soft", "spendesk.app", "Europe", "Paris / remote"),
    ("Qonto Soft", "qonto.app", "Europe", "Paris / remote"),
    ("Swile Soft", "swile.app", "Europe", "Paris / remote"),
    ("Pennylane Soft", "pennylane.app", "Europe", "Paris / remote"),
    ("Back Market Soft", "backmarket.app", "Europe", "Paris / remote"),
    ("Photoroom Soft", "photoroom.app", "Europe", "Paris / remote"),
    ("Dust Soft", "dust.app", "Europe", "Paris / remote"),
    ("Pigment Soft", "pigment.app", "Europe", "Paris / remote"),
    ("Sorare Soft", "sorare.app", "Europe", "Paris / remote"),
    ("Scaleway Soft", "scaleway.app", "Europe", "Paris / remote"),
    ("Clever Cloud Soft", "clever-cloud.app", "Europe", "Nantes / remote"),
    ("Platform Soft", "platform.sh", "Europe", "Paris / remote"),
    ("Ledger Soft", "ledger.app", "Europe", "Paris / remote"),
    ("Aircall Soft", "aircall.app", "Europe", "Paris / remote"),
    ("Algolia Soft", "algolia.app", "Europe", "Paris / remote"),
    ("Contentsquare Soft", "contentsquare.app", "Europe", "Paris / remote"),
    ("BlaBlaCar Soft", "blablacar.app", "Europe", "Paris / remote"),
    ("Deezer Soft", "deezer.app", "Europe", "Paris / remote"),
    ("Voodoo Soft", "voodoo.app", "Europe", "Paris / remote"),
    ("Shift Technology Soft", "shifttechnology.com", "Europe", "Paris / remote"),
    ("Citymapper Soft", "citymapper.app", "Europe", "London / remote"),
    ("GoCardless Soft", "gocardless.app", "Europe", "London / remote"),
    ("Checkout Soft", "checkout.app", "Europe", "London / remote"),
    ("Monzo Soft", "monzo.app", "Europe", "London / remote"),
    ("Starling Soft", "starling.app", "Europe", "London / remote"),
    ("Wise Soft", "wise.app", "Europe", "London / remote"),
    ("Darktrace Soft", "darktrace.app", "Europe", "Cambridge / remote"),
    ("Graphcore Soft", "graphcore.app", "Europe", "Bristol / remote"),
    ("Improbable Soft", "improbable.app", "Europe", "London / remote"),
    ("Stability Soft", "stability.app", "Europe", "London / remote"),
    ("Mistral Soft", "mistral.app", "Europe", "Paris / remote"),
    ("Jina Soft", "jina.app", "Europe", "Berlin / remote"),
    ("QuestDB Soft", "questdb.app", "Europe", "London / remote"),
    ("N8n Soft", "n8n.app", "Europe", "Berlin / remote"),
    ("Make Soft", "make.app", "Europe", "Prague / remote"),
    ("Simple Analytics Soft", "simpleanalytics.app", "Europe", "Netherlands / remote"),
    ("Pirsch Soft", "pirsch.app", "Europe", "Germany / remote"),
    ("Matomo Soft", "matomo.app", "Europe", "Auckland / remote"),
    ("ClickHouse Soft", "clickhouse.app", "Europe", "Amsterdam / remote"),
    ("OVH Soft", "ovh.com", "Europe", "Roubaix / remote"),
    ("Catawiki Soft", "catawiki.app", "Europe", "Amsterdam / remote"),
    ("Backbase Soft", "backbase.app", "Europe", "Amsterdam / remote"),
    ("Picnic Soft", "picnic.com", "Europe", "Amsterdam / remote"),
    ("TomTom Soft", "tomtom.app", "Europe", "Amsterdam / remote"),
    ("Adyen Soft", "adyen.app", "Europe", "Amsterdam / remote"),
    ("Booking Soft", "booking.app", "Europe", "Amsterdam / remote"),
    ("Klarna Soft", "klarna.app", "Europe", "Stockholm / remote"),
    ("Spotify Soft", "spotify.app", "Europe", "Stockholm / remote"),
    ("King Soft", "king.app", "Europe", "Stockholm / remote"),
    ("N26 Soft", "n26.app", "Europe", "Berlin / remote"),
    ("Delivery Hero Soft", "deliveryhero.app", "Europe", "Berlin / remote"),
    ("HelloFresh Soft", "hellofresh.app", "Europe", "Berlin / remote"),
    ("Zalando Soft", "zalando.app", "Europe", "Berlin / remote"),
    ("Revolut Soft", "revolut.app", "Europe", "London / remote"),
    ("Deliveroo Soft", "deliveroo.app", "Europe", "London / remote"),
    # Remote AI / developer / SaaS
    ("Cursor Soft", "cursor.sh", "Remote", "Worldwide remote"),
    ("Replit Soft", "replit.app", "Remote", "Worldwide remote"),
    ("CodeSandbox Soft", "csb.app", "Remote", "Worldwide remote"),
    ("Modal Soft", "modal.app", "Remote", "Worldwide remote"),
    ("Banana Soft", "banana.app", "Remote", "Worldwide remote"),
    ("Replicate Soft", "replicate.app", "Remote", "Worldwide remote"),
    ("Together Soft", "together.app", "Remote", "Worldwide remote"),
    ("Fireworks Soft", "fireworks.app", "Remote", "Worldwide remote"),
    ("Anyscale Soft", "anyscale.app", "Remote", "Worldwide remote"),
    ("Baseten Soft", "baseten.app", "Remote", "Worldwide remote"),
    ("Weights Biases Soft", "wandb.app", "Remote", "Worldwide remote"),
    ("Labelbox Soft", "labelbox.app", "Remote", "Worldwide remote"),
    ("Scale Soft", "scale.app", "Remote", "Worldwide remote"),
    ("Snorkel Soft", "snorkel.app", "Remote", "Worldwide remote"),
    ("LangChain Soft", "langchain.app", "Remote", "Worldwide remote"),
    ("Pinecone Soft", "pinecone.app", "Remote", "Worldwide remote"),
    ("Chroma Soft", "trychroma.app", "Remote", "Worldwide remote"),
    ("Turbopuffer Soft", "turbopuffer.app", "Remote", "Worldwide remote"),
    ("Reducto Soft", "reducto.app", "Remote", "Worldwide remote"),
    ("Extend Soft", "extend.app", "Remote", "Worldwide remote"),
    ("Perplexity Soft", "perplexity.app", "Remote", "Worldwide remote"),
    ("Glean Soft", "glean.app", "Remote", "Worldwide remote"),
    ("Harvey Soft", "harvey.app", "Remote", "Worldwide remote"),
    ("Hebbia Soft", "hebbia.app", "Remote", "Worldwide remote"),
    ("EvenUp Soft", "evenup.app", "Remote", "Worldwide remote"),
    ("Ironclad Soft", "ironclad.app", "Remote", "Worldwide remote"),
    ("Spellbook Soft", "spellbook.app", "Remote", "Worldwide remote"),
    ("Clerk Soft", "clerk.app", "Remote", "Worldwide remote"),
    ("Stytch Soft", "stytch.app", "Remote", "Worldwide remote"),
    ("WorkOS Soft", "workos.app", "Remote", "Worldwide remote"),
    ("Descope Soft", "descope.app", "Remote", "Worldwide remote"),
    ("SuperTokens Soft", "supertokens.app", "Remote", "Worldwide remote"),
    ("FusionAuth Soft", "fusionauth.app", "Remote", "Worldwide remote"),
    ("Resend Soft", "resend.app", "Remote", "Worldwide remote"),
    ("Loops Soft", "loops.app", "Remote", "Worldwide remote"),
    ("PostHog Soft", "posthog.app", "Remote", "Worldwide remote"),
    ("Cal Soft", "cal.app", "Remote", "Worldwide remote"),
    ("Linear Soft", "linear.dev", "Remote", "Worldwide remote"),
    ("Height Soft", "height.dev", "Remote", "Worldwide remote"),
    ("Plane Soft", "plane.app", "Remote", "Worldwide remote"),
    ("Incident Soft", "incident.app", "Remote", "Worldwide remote"),
    ("Rootly Soft", "rootly.app", "Remote", "Worldwide remote"),
    ("FireHydrant Soft", "firehydrant.app", "Remote", "Worldwide remote"),
    ("Chronosphere Soft", "chronosphere.app", "Remote", "Worldwide remote"),
    ("Honeycomb Soft", "honeycomb.app", "Remote", "Worldwide remote"),
    ("Buf Soft", "buf.app", "Remote", "Worldwide remote"),
    ("Temporal Soft", "temporal.app", "Remote", "Worldwide remote"),
    ("Prefect Soft", "prefect.app", "Remote", "Worldwide remote"),
    ("Dagster Soft", "dagster.app", "Remote", "Worldwide remote"),
    ("Airbyte Soft", "airbyte.app", "Remote", "Worldwide remote"),
    ("dbt Soft", "dbt.app", "Remote", "Worldwide remote"),
    ("Census Soft", "census.app", "Remote", "Worldwide remote"),
    ("Hightouch Soft", "hightouch.app", "Remote", "Worldwide remote"),
    ("RudderStack Soft", "rudderstack.app", "Remote", "Worldwide remote"),
    ("Customer.io Soft", "customer.io", "Remote", "Worldwide remote"),
    ("OneSignal Soft", "onesignal.app", "Remote", "Worldwide remote"),
    ("Clay Soft", "clay.app", "Remote", "Worldwide remote"),
    ("Apollo Soft", "apollo.app", "Remote", "Worldwide remote"),
    ("Appsmith Soft", "appsmith.app", "Remote", "Worldwide remote"),
    ("Budibase Soft", "budibase.app", "Remote", "Worldwide remote"),
    ("Tooljet Soft", "tooljet.app", "Remote", "Worldwide remote"),
    ("Framer Soft", "framer.app", "Remote", "Worldwide remote"),
    ("Webflow Soft", "webflow.app", "Remote", "Worldwide remote"),
    ("Bubble Soft", "bubble.app", "Remote", "Worldwide remote"),
    ("Ghost Soft", "ghost.app", "Remote", "Worldwide remote"),
    ("Beehiiv Soft", "beehiiv.app", "Remote", "Worldwide remote"),
    ("Substack Soft", "substack.app", "Remote", "Worldwide remote"),
    ("Notion Soft", "notion.app", "Remote", "Worldwide remote"),
    ("Coda Soft", "coda.app", "Remote", "Worldwide remote"),
    ("Retool Soft", "retool.app", "Remote", "Worldwide remote"),
    ("Supabase Soft", "supabase.app", "Remote", "Worldwide remote"),
    ("Neon Soft", "neon.app", "Remote", "Worldwide remote"),
    ("PlanetScale Soft", "planetscale.app", "Remote", "Worldwide remote"),
    ("Railway Soft", "railway.dev", "Remote", "Worldwide remote"),
    ("Render Soft", "render.app", "Remote", "Worldwide remote"),
    ("Fly Soft", "fly.app", "Remote", "Worldwide remote"),
    ("Snyk Soft", "snyk.app", "Remote", "Worldwide remote"),
    ("Wiz Soft", "wiz.app", "Remote", "Worldwide remote"),
    ("Orca Soft", "orca.app", "Remote", "Worldwide remote"),
    ("Material Security Soft", "material.app", "Remote", "Worldwide remote"),
    ("Drata Soft", "drata.app", "Remote", "Worldwide remote"),
    ("Secureframe Soft", "secureframe.app", "Remote", "Worldwide remote"),
    ("JumpCloud Soft", "jumpcloud.app", "Remote", "Worldwide remote"),
    ("Deel Soft", "deel.app", "Remote", "Worldwide remote"),
    ("Remote Soft", "remote.app", "Remote", "Worldwide remote"),
    ("Oyster Soft", "oyster.app", "Remote", "Worldwide remote"),
    ("Rippling Soft", "rippling.app", "Remote", "Worldwide remote"),
    ("Lattice Soft", "lattice.app", "Remote", "Worldwide remote"),
    ("15Five Soft", "15five.app", "Remote", "Worldwide remote"),
    ("BambooHR Soft", "bamboohr.app", "Remote", "Worldwide remote"),
    ("Gusto Soft", "gusto.app", "Remote", "Worldwide remote"),
    ("Justworks Soft", "justworks.app", "Remote", "Worldwide remote"),
    ("Sourcegraph Soft", "sourcegraph.app", "Remote", "Worldwide remote"),
    ("HashiCorp Soft", "hashicorp.app", "Remote", "Worldwide remote"),
    ("Pulumi Soft", "pulumi.app", "Remote", "Worldwide remote"),
    ("Statsig Soft", "statsig.app", "Remote", "Worldwide remote"),
    ("Amplitude Soft", "amplitude.app", "Remote", "Worldwide remote"),
    ("Mixpanel Soft", "mixpanel.app", "Remote", "Worldwide remote"),
    ("FullStory Soft", "fullstory.app", "Remote", "Worldwide remote"),
    ("LogRocket Soft", "logrocket.app", "Remote", "Worldwide remote"),
    ("Sentry Soft", "sentry.app", "Remote", "Worldwide remote"),
    ("PagerDuty Soft", "pagerduty.app", "Remote", "Worldwide remote"),
    ("Grafana Soft", "grafana.app", "Remote", "Worldwide remote"),
    ("Elastic Soft", "elastic.app", "Remote", "Worldwide remote"),
    ("Redpanda Soft", "redpanda.app", "Remote", "Worldwide remote"),
    ("WarpStream Soft", "warpstream.app", "Remote", "Worldwide remote"),
    ("Materialize Soft", "materialize.app", "Remote", "Worldwide remote"),
    ("RisingWave Soft", "risingwave.app", "Remote", "Worldwide remote"),
    ("SingleStore Soft", "singlestore.app", "Remote", "Worldwide remote"),
    ("Yugabyte Soft", "yugabyte.app", "Remote", "Worldwide remote"),
    ("Hasura Soft", "hasura.app", "Remote", "Worldwide remote"),
    ("Kong Soft", "kong.app", "Remote", "Worldwide remote"),
    ("Solo Soft", "solo.app", "Remote", "Worldwide remote"),
    ("Isovalent Soft", "isovalent.app", "Remote", "Worldwide remote"),
    ("Sysdig Soft", "sysdig.app", "Remote", "Worldwide remote"),
    ("Aqua Soft", "aqua.app", "Remote", "Worldwide remote"),
    ("Lacework Soft", "lacework.app", "Remote", "Worldwide remote"),
    ("Crowdstrike Soft", "crowdstrike.app", "Remote", "Worldwide remote"),
    ("SentinelOne Soft", "sentinelone.app", "Remote", "Worldwide remote"),
    ("Gong Soft", "gong.app", "Remote", "Worldwide remote"),
    ("Clari Soft", "clari.app", "Remote", "Worldwide remote"),
    ("Outreach Soft", "outreach.app", "Remote", "Worldwide remote"),
    ("Salesloft Soft", "salesloft.app", "Remote", "Worldwide remote"),
    ("Affinity Soft", "affinity.app", "Remote", "Worldwide remote"),
    ("Intercom Soft", "intercom.app", "Remote", "Worldwide remote"),
    ("Freshworks Soft", "freshworks.app", "Remote", "Worldwide remote"),
    ("HubSpot Soft", "hubspot.app", "Remote", "Worldwide remote"),
    ("Zendesk Soft", "zendesk.app", "Remote", "Worldwide remote"),
    ("Braze Soft", "braze.app", "Remote", "Worldwide remote"),
    ("Iterable Soft", "iterable.app", "Remote", "Worldwide remote"),
    ("Klaviyo Soft", "klaviyo.app", "Remote", "Worldwide remote"),
    ("ActiveCampaign Soft", "activecampaign.app", "Remote", "Worldwide remote"),
    ("ConvertKit Soft", "convertkit.app", "Remote", "Worldwide remote"),
    ("Mailgun Soft", "mailgun.app", "Remote", "Worldwide remote"),
    ("Postmark Soft", "postmark.app", "Remote", "Worldwide remote"),
    ("SendGrid Soft", "sendgrid.app", "Remote", "Worldwide remote"),
    ("Dropbox Soft", "dropbox.app", "Remote", "Worldwide remote"),
    ("Box Soft", "box.app", "Remote", "Worldwide remote"),
    ("Egnyte Soft", "egnyte.app", "Remote", "Worldwide remote"),
    ("Lucid Soft", "lucid.app", "Remote", "Worldwide remote"),
    ("Miro Soft", "miro.app", "Remote", "Worldwide remote"),
    ("Figma Soft", "figma.app", "Remote", "Worldwide remote"),
    ("InVision Soft", "invision.app", "Remote", "Worldwide remote"),
    ("Asana Soft", "asana.app", "Remote", "Worldwide remote"),
    ("Monday Soft", "monday.app", "Remote", "Worldwide remote"),
    ("ClickUp Soft", "clickup.app", "Remote", "Worldwide remote"),
    ("Basecamp Soft", "basecamp.app", "Remote", "Worldwide remote"),
    ("Shortcut Soft", "shortcut.app", "Remote", "Worldwide remote"),
    ("Zapier Soft", "zapier.app", "Remote", "Worldwide remote"),
    ("Tray Soft", "tray.app", "Remote", "Worldwide remote"),
    ("Workato Soft", "workato.app", "Remote", "Worldwide remote"),
    ("Okta Soft", "okta.app", "Remote", "Worldwide remote"),
    ("Auth0 Soft", "auth0.app", "Remote", "Worldwide remote"),
    ("Cloudflare Soft", "cloudflare.app", "Remote", "Worldwide remote"),
    ("Fastly Soft", "fastly.app", "Remote", "Worldwide remote"),
    ("Datadog Soft", "datadog.app", "Remote", "Worldwide remote"),
    ("New Relic Soft", "newrelic.app", "Remote", "Worldwide remote"),
    ("Dynatrace Soft", "dynatrace.app", "Remote", "Worldwide remote"),
    ("MongoDB Soft", "mongodb.app", "Remote", "Worldwide remote"),
    ("Redis Soft", "redis.app", "Remote", "Worldwide remote"),
    ("Confluent Soft", "confluent.app", "Remote", "Worldwide remote"),
    ("InfluxData Soft", "influxdata.app", "Remote", "Worldwide remote"),
    ("Fivetran Soft", "fivetran.app", "Remote", "Worldwide remote"),
    ("Segment Soft", "segment.app", "Remote", "Worldwide remote"),
    ("mParticle Soft", "mparticle.app", "Remote", "Worldwide remote"),
    ("Tealium Soft", "tealium.app", "Remote", "Worldwide remote"),
    ("Hotjar Soft", "hotjar.app", "Remote", "Worldwide remote"),
    ("Heap Soft", "heap.app", "Remote", "Worldwide remote"),
    ("Split Soft", "split.app", "Remote", "Worldwide remote"),
    ("Reclaim Soft", "reclaim.app", "Remote", "Worldwide remote"),
    ("Motion Soft", "motion.app", "Remote", "Worldwide remote"),
    ("Clockwise Soft", "clockwise.app", "Remote", "Worldwide remote"),
    ("SavvyCal Soft", "savvycal.app", "Remote", "Worldwide remote"),
    ("Calendly Soft", "calendly.app", "Remote", "Worldwide remote"),
    ("TidyCal Soft", "tidycal.app", "Remote", "Worldwide remote"),
    ("Cron Soft", "cron.app", "Remote", "Worldwide remote"),
    ("Fathom Soft", "fathom.app", "Remote", "Worldwide remote"),
    ("Umami Soft", "umami.app", "Remote", "Worldwide remote"),
    ("Typedream Soft", "typedream.app", "Remote", "Worldwide remote"),
    ("Carrd Soft", "carrd.app", "Remote", "Worldwide remote"),
    ("Super Soft", "super.app", "Remote", "Worldwide remote"),
    ("Adalo Soft", "adalo.app", "Remote", "Worldwide remote"),
    ("Glide Soft", "glide.app", "Remote", "Worldwide remote"),
    ("DocuSign Soft", "docusign.app", "Remote", "Worldwide remote"),
    ("PandaDoc Soft", "pandadoc.app", "Remote", "Worldwide remote"),
    ("HelloSign Soft", "hellosign.app", "Remote", "Worldwide remote"),
    ("Character Soft", "character.app", "Remote", "Worldwide remote"),
    ("You Soft", "you.app", "Remote", "Worldwide remote"),
    ("Inflection Soft", "inflection.app", "Remote", "Worldwide remote"),
    ("Adept Soft", "adept.app", "Remote", "Worldwide remote"),
    ("Cohere Soft", "cohere.app", "Remote", "Worldwide remote"),
    ("Casetext Soft", "casetext.app", "Remote", "Worldwide remote"),
    ("Abstract Soft", "abstract.app", "Remote", "Worldwide remote"),
    ("Parseur Soft", "parseur.app", "Remote", "Worldwide remote"),
    ("Abnormal Soft", "abnormal.app", "Remote", "Worldwide remote"),
    ("Y Combinator Soft", "ycombinator.app", "Remote", "Worldwide remote"),
    ("Wellfound Soft", "wellfound.app", "Remote", "Worldwide remote"),
    ("Hirect Soft", "hirect.app", "Remote", "Worldwide remote"),
    ("Coder Soft", "coder.app", "Remote", "Worldwide remote"),
    ("Val Town Soft", "val.app", "Remote", "Worldwide remote"),
    ("Comet Soft", "comet.app", "Remote", "Worldwide remote"),
    ("Unstructured Soft", "unstructured.app", "Remote", "Worldwide remote"),
    ("Voyage Soft", "voyage.app", "Remote", "Worldwide remote"),
    ("Nomic Soft", "nomic.app", "Remote", "Worldwide remote"),
    ("Milvus Soft", "milvus.app", "Remote", "Worldwide remote"),
    ("Zilliz Soft", "zilliz.app", "Remote", "Worldwide remote"),
    ("Deno Soft", "deno.app", "Remote", "Worldwide remote"),
    ("Bun Soft", "bun.app", "Remote", "Worldwide remote"),
    ("Prisma Soft", "prisma.app", "Remote", "Worldwide remote"),
    ("Buttondown Soft", "buttondown.app", "Remote", "Worldwide remote"),
    ("Plausible Soft2", "plausible.io", "Europe", "Tallinn / remote"),
]

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
    "Soft", "Soft2", "Soft3", "Soft4", "Digital", "Tech", "Careers", "Studios",
    "Solutions", "Technologies", "Technology", "Limited", "Group",
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

    out = ROOT / "output" / "emails_shortlist_batch27_2026-08-15.csv"
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
