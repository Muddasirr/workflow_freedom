#!/usr/bin/env python3
"""Probe batch25 — fresh PK / MENA / Europe / Australia / remote hiring inboxes."""
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
    # Europe product / infra
    ("Contentful EU", "contentful.com", "Europe", "Berlin / remote"),
    ("Personio EU", "personio.com", "Europe", "Munich / remote"),
    ("SumUp EU", "sumup.com", "Europe", "London / remote"),
    ("N26 EU", "n26.com", "Europe", "Berlin / remote"),
    ("Trade Republic EU", "traderepublic.com", "Europe", "Berlin / remote"),
    ("GetYourGuide EU", "getyourguide.com", "Europe", "Berlin / remote"),
    ("Delivery Hero EU", "deliveryhero.com", "Europe", "Berlin / remote"),
    ("HelloFresh EU", "hellofresh.com", "Europe", "Berlin / remote"),
    ("Zalando EU", "zalando.com", "Europe", "Berlin / remote"),
    ("Klarna EU", "klarna.com", "Europe", "Stockholm / remote"),
    ("Spotify Soft", "spotify.com", "Europe", "Stockholm / remote"),
    ("King Soft", "king.com", "Europe", "Stockholm / remote"),
    ("Mollie EU", "mollie.com", "Europe", "Amsterdam / remote"),
    ("Adyen Soft", "adyen.com", "Europe", "Amsterdam / remote"),
    ("Booking Soft", "booking.com", "Europe", "Amsterdam / remote"),
    ("TomTom Soft", "tomtom.com", "Europe", "Amsterdam / remote"),
    ("MessageBird Soft", "messagebird.com", "Europe", "Amsterdam / remote"),
    ("Picnic Soft", "picnic.app", "Europe", "Amsterdam / remote"),
    ("Bunq Soft", "bunq.com", "Europe", "Amsterdam / remote"),
    ("Catawiki Soft", "catawiki.com", "Europe", "Amsterdam / remote"),
    ("Backbase Soft", "backbase.com", "Europe", "Amsterdam / remote"),
    ("Deezer Soft", "deezer.com", "Europe", "Paris / remote"),
    ("BlaBlaCar Soft", "blablacar.com", "Europe", "Paris / remote"),
    ("Doctolib Soft", "doctolib.com", "Europe", "Paris / remote"),
    ("Alan Soft", "alan.com", "Europe", "Paris / remote"),
    ("Ledger Soft", "ledger.com", "Europe", "Paris / remote"),
    ("Datadog Soft", "datadoghq.com", "Europe", "Paris / remote"),
    ("Contentsquare Soft", "contentsquare.com", "Europe", "Paris / remote"),
    ("Mirakl Soft", "mirakl.com", "Europe", "Paris / remote"),
    ("Spendesk Soft", "spendesk.com", "Europe", "Paris / remote"),
    ("Qonto Soft", "qonto.com", "Europe", "Paris / remote"),
    ("Swile Soft", "swile.co", "Europe", "Paris / remote"),
    ("Pennylane Soft", "pennylane.com", "Europe", "Paris / remote"),
    ("Front Soft", "front.com", "Europe", "Paris / remote"),
    ("Aircall Soft", "aircall.io", "Europe", "Paris / remote"),
    ("Algolia Soft", "algolia.com", "Europe", "Paris / remote"),
    ("Criteo Soft", "criteo.com", "Europe", "Paris / remote"),
    ("Voodoo Soft", "voodoo.io", "Europe", "Paris / remote"),
    ("Back Market Soft", "backmarket.com", "Europe", "Paris / remote"),
    ("Lydia Soft", "lydia-app.com", "Europe", "Paris / remote"),
    ("Revolut Soft", "revolut.com", "Europe", "London / remote"),
    ("Monzo Soft", "monzo.com", "Europe", "London / remote"),
    ("Starling Soft", "starlingbank.com", "Europe", "London / remote"),
    ("Wise Soft", "wise.com", "Europe", "London / remote"),
    ("Checkout Soft", "checkout.com", "Europe", "London / remote"),
    ("GoCardless Soft", "gocardless.com", "Europe", "London / remote"),
    ("Deliveroo Soft", "deliveroo.com", "Europe", "London / remote"),
    ("Citymapper Soft", "citymapper.com", "Europe", "London / remote"),
    ("Cazoo Soft", "cazoo.co.uk", "Europe", "London / remote"),
    ("Darktrace Soft", "darktrace.com", "Europe", "Cambridge / remote"),
    ("Graphcore Soft", "graphcore.ai", "Europe", "Bristol / remote"),
    ("Improbable Soft", "improbable.io", "Europe", "London / remote"),
    ("Benevolent Soft", "benevolent.ai", "Europe", "London / remote"),
    ("DeepMind Soft", "deepmind.com", "Europe", "London / remote"),
    ("Stability Soft", "stability.ai", "Europe", "London / remote"),
    ("Hugging Face Soft", "huggingface.co", "Europe", "Paris / remote"),
    ("Mistral Soft", "mistral.ai", "Europe", "Paris / remote"),
    ("Photoroom Soft", "photoroom.com", "Europe", "Paris / remote"),
    ("Dust Soft", "dust.tt", "Europe", "Paris / remote"),
    ("Crew Soft", "crew.work", "Europe", "Paris / remote"),
    ("Pigment Soft", "pigment.com", "Europe", "Paris / remote"),
    ("Shift Technology Soft", "shift-technology.com", "Europe", "Paris / remote"),
    ("MeilleursAgents Soft", "meilleursagents.com", "Europe", "Paris / remote"),
    ("Luko Soft", "luko.eu", "Europe", "Paris / remote"),
    ("Sorare Soft", "sorare.com", "Europe", "Paris / remote"),
    ("Ledger Soft2", "ledger.fr", "Europe", "Paris / remote"),
    ("Scaleway Soft", "scaleway.com", "Europe", "Paris / remote"),
    ("OVH Soft", "ovhcloud.com", "Europe", "Roubaix / remote"),
    ("Clever Cloud Soft", "clever-cloud.com", "Europe", "Nantes / remote"),
    ("Platform.sh Soft", "platform.sh", "Europe", "Paris / remote"),
    ("Cockroach Labs Soft", "cockroachlabs.com", "Europe", "NYC / remote"),
    ("ClickHouse Soft", "clickhouse.com", "Europe", "Amsterdam / remote"),
    ("Yugabyte Soft", "yugabyte.com", "Remote", "Worldwide remote"),
    ("SingleStore Soft", "singlestore.com", "Remote", "Worldwide remote"),
    ("PlanetScale Soft", "planetscale.com", "Remote", "Worldwide remote"),
    ("Neon Soft", "neon.tech", "Remote", "Worldwide remote"),
    ("Supabase Soft", "supabase.com", "Remote", "Worldwide remote"),
    ("Hasura Soft", "hasura.io", "Remote", "Worldwide remote"),
    ("Prisma Soft", "prisma.io", "Remote", "Worldwide remote"),
    ("Railway Soft", "railway.app", "Remote", "Worldwide remote"),
    ("Render Soft", "render.com", "Remote", "Worldwide remote"),
    ("Fly Soft", "fly.io", "Remote", "Worldwide remote"),
    ("Deno Soft", "deno.com", "Remote", "Worldwide remote"),
    ("Bun Soft", "bun.sh", "Remote", "Worldwide remote"),
    ("Vercel Soft", "vercel.com", "Remote", "Worldwide remote"),
    ("Netlify Soft", "netlify.com", "Remote", "Worldwide remote"),
    ("Cloudflare Soft", "cloudflare.com", "Remote", "Worldwide remote"),
    ("Fastly Soft", "fastly.com", "Remote", "Worldwide remote"),
    ("HashiCorp Soft", "hashicorp.com", "Remote", "Worldwide remote"),
    ("Pulumi Soft", "pulumi.com", "Remote", "Worldwide remote"),
    ("Terraform Soft", "terraform.io", "Remote", "Worldwide remote"),
    ("LaunchDarkly Soft", "launchdarkly.com", "Remote", "Worldwide remote"),
    ("Split Soft", "split.io", "Remote", "Worldwide remote"),
    ("Statsig Soft", "statsig.com", "Remote", "Worldwide remote"),
    ("Amplitude Soft", "amplitude.com", "Remote", "Worldwide remote"),
    ("Mixpanel Soft", "mixpanel.com", "Remote", "Worldwide remote"),
    ("PostHog Soft", "posthog.com", "Remote", "Worldwide remote"),
    ("Heap Soft", "heap.io", "Remote", "Worldwide remote"),
    ("FullStory Soft", "fullstory.com", "Remote", "Worldwide remote"),
    ("Hotjar Soft", "hotjar.com", "Remote", "Worldwide remote"),
    ("LogRocket Soft", "logrocket.com", "Remote", "Worldwide remote"),
    ("Sentry Soft", "sentry.io", "Remote", "Worldwide remote"),
    ("Bugsnag Soft", "bugsnag.com", "Remote", "Worldwide remote"),
    ("Rollbar Soft", "rollbar.com", "Remote", "Worldwide remote"),
    ("PagerDuty Soft", "pagerduty.com", "Remote", "Worldwide remote"),
    ("Opsgenie Soft", "opsgenie.com", "Remote", "Worldwide remote"),
    ("Incident Soft", "incident.io", "Remote", "Worldwide remote"),
    ("Rootly Soft", "rootly.com", "Remote", "Worldwide remote"),
    ("FireHydrant Soft", "firehydrant.com", "Remote", "Worldwide remote"),
    ("Chronosphere Soft", "chronosphere.io", "Remote", "Worldwide remote"),
    ("Honeycomb Soft", "honeycomb.io", "Remote", "Worldwide remote"),
    ("Lightstep Soft", "lightstep.com", "Remote", "Worldwide remote"),
    ("New Relic Soft", "newrelic.com", "Remote", "Worldwide remote"),
    ("Dynatrace Soft", "dynatrace.com", "Remote", "Worldwide remote"),
    ("Datadog Soft2", "datadog.com", "Remote", "Worldwide remote"),
    ("Grafana Soft", "grafana.com", "Remote", "Worldwide remote"),
    ("Elastic Soft", "elastic.co", "Remote", "Worldwide remote"),
    ("MongoDB Soft2", "mongodb.com", "Remote", "Worldwide remote"),
    ("Redis Soft", "redis.com", "Remote", "Worldwide remote"),
    ("Redis Soft2", "redis.io", "Remote", "Worldwide remote"),
    ("Confluent Soft", "confluent.io", "Remote", "Worldwide remote"),
    ("Aiven Soft", "aiven.io", "Europe", "Helsinki / remote"),
    ("Crunchy Data Soft", "crunchydata.com", "Remote", "Worldwide remote"),
    ("Timescale Soft2", "timescale.com", "Remote", "Worldwide remote"),
    ("InfluxData Soft", "influxdata.com", "Remote", "Worldwide remote"),
    ("QuestDB Soft", "questdb.io", "Europe", "London / remote"),
    ("Materialize Soft", "materialize.com", "Remote", "Worldwide remote"),
    ("RisingWave Soft", "risingwave.com", "Remote", "Worldwide remote"),
    ("Redpanda Soft", "redpanda.com", "Remote", "Worldwide remote"),
    ("WarpStream Soft", "warpstream.com", "Remote", "Worldwide remote"),
    ("Buf Soft", "buf.build", "Remote", "Worldwide remote"),
    ("Temporal Soft", "temporal.io", "Remote", "Worldwide remote"),
    ("Cadence Soft", "uber.com", "Remote", "Worldwide remote"),
    ("Prefect Soft", "prefect.io", "Remote", "Worldwide remote"),
    ("Dagster Soft", "dagster.io", "Remote", "Worldwide remote"),
    ("Airbyte Soft", "airbyte.com", "Remote", "Worldwide remote"),
    ("Fivetran Soft", "fivetran.com", "Remote", "Worldwide remote"),
    ("dbt Soft", "getdbt.com", "Remote", "Worldwide remote"),
    ("Census Soft", "getcensus.com", "Remote", "Worldwide remote"),
    ("Hightouch Soft", "hightouch.com", "Remote", "Worldwide remote"),
    ("RudderStack Soft", "rudderstack.com", "Remote", "Worldwide remote"),
    ("Segment Soft", "segment.com", "Remote", "Worldwide remote"),
    ("mParticle Soft", "mparticle.com", "Remote", "Worldwide remote"),
    ("Tealium Soft", "tealium.com", "Remote", "Worldwide remote"),
    ("Iterable Soft", "iterable.com", "Remote", "Worldwide remote"),
    ("Customer.io Soft", "customer.io", "Remote", "Worldwide remote"),
    ("Braze Soft", "braze.com", "Remote", "Worldwide remote"),
    ("OneSignal Soft", "onesignal.com", "Remote", "Worldwide remote"),
    ("Pushwoosh Soft", "pushwoosh.com", "Remote", "Worldwide remote"),
    ("Intercom Soft", "intercom.com", "Remote", "Worldwide remote"),
    ("Zendesk Soft", "zendesk.com", "Remote", "Worldwide remote"),
    ("Freshworks Soft", "freshworks.com", "Remote", "Worldwide remote"),
    ("HubSpot Soft", "hubspot.com", "Remote", "Worldwide remote"),
    ("Salesforce Soft", "salesforce.com", "Remote", "Worldwide remote"),
    ("Gong Soft", "gong.io", "Remote", "Worldwide remote"),
    ("Chorus Soft", "chorus.ai", "Remote", "Worldwide remote"),
    ("Clari Soft", "clari.com", "Remote", "Worldwide remote"),
    ("Outreach Soft", "outreach.io", "Remote", "Worldwide remote"),
    ("Salesloft Soft", "salesloft.com", "Remote", "Worldwide remote"),
    ("Apollo Soft", "apollo.io", "Remote", "Worldwide remote"),
    ("Clay Soft", "clay.com", "Remote", "Worldwide remote"),
    ("Attio Soft", "attio.com", "Europe", "London / remote"),
    ("Affinity Soft", "affinity.co", "Remote", "Worldwide remote"),
    ("Notion Soft", "notion.so", "Remote", "Worldwide remote"),
    ("Coda Soft", "coda.io", "Remote", "Worldwide remote"),
    ("Airtable Soft", "airtable.com", "Remote", "Worldwide remote"),
    ("Retool Soft", "retool.com", "Remote", "Worldwide remote"),
    ("Appsmith Soft", "appsmith.com", "Remote", "Worldwide remote"),
    ("Budibase Soft", "budibase.com", "Remote", "Worldwide remote"),
    ("Tooljet Soft", "tooljet.com", "Remote", "Worldwide remote"),
    ("N8n Soft", "n8n.io", "Europe", "Berlin / remote"),
    ("Zapier Soft", "zapier.com", "Remote", "Worldwide remote"),
    ("Make Soft", "make.com", "Europe", "Prague / remote"),
    ("Tray Soft", "tray.io", "Remote", "Worldwide remote"),
    ("Workato Soft", "workato.com", "Remote", "Worldwide remote"),
    ("MuleSoft Soft", "mulesoft.com", "Remote", "Worldwide remote"),
    ("Kong Soft", "konghq.com", "Remote", "Worldwide remote"),
    ("Tyk Soft", "tyk.io", "Europe", "London / remote"),
    ("Gravitee Soft", "gravitee.io", "Europe", "Lille / remote"),
    ("Solo Soft", "solo.io", "Remote", "Worldwide remote"),
    ("Isovalent Soft", "isovalent.com", "Remote", "Worldwide remote"),
    ("Sysdig Soft", "sysdig.com", "Remote", "Worldwide remote"),
    ("Aqua Soft", "aquasec.com", "Remote", "Worldwide remote"),
    ("Snyk Soft", "snyk.io", "Remote", "Worldwide remote"),
    ("Wiz Soft", "wiz.io", "Remote", "Worldwide remote"),
    ("Orca Soft", "orca.security", "Remote", "Worldwide remote"),
    ("Lacework Soft", "lacework.com", "Remote", "Worldwide remote"),
    ("Crowdstrike Soft", "crowdstrike.com", "Remote", "Worldwide remote"),
    ("SentinelOne Soft", "sentinelone.com", "Remote", "Worldwide remote"),
    ("Abnormal Soft", "abnormalsecurity.com", "Remote", "Worldwide remote"),
    ("Material Security Soft", "material.security", "Remote", "Worldwide remote"),
    ("Vanta Soft", "vanta.com", "Remote", "Worldwide remote"),
    ("Drata Soft", "drata.com", "Remote", "Worldwide remote"),
    ("Secureframe Soft", "secureframe.com", "Remote", "Worldwide remote"),
    ("Tugboat Soft", "tugboatlogic.com", "Remote", "Worldwide remote"),
    ("JumpCloud Soft", "jumpcloud.com", "Remote", "Worldwide remote"),
    ("Okta Soft", "okta.com", "Remote", "Worldwide remote"),
    ("Auth0 Soft", "auth0.com", "Remote", "Worldwide remote"),
    ("Stytch Soft", "stytch.com", "Remote", "Worldwide remote"),
    ("Clerk Soft", "clerk.com", "Remote", "Worldwide remote"),
    ("WorkOS Soft", "workos.com", "Remote", "Worldwide remote"),
    ("Descope Soft", "descope.com", "Remote", "Worldwide remote"),
    ("FusionAuth Soft", "fusionauth.io", "Remote", "Worldwide remote"),
    ("SuperTokens Soft", "supertokens.com", "Remote", "Worldwide remote"),
    ("Keycloak Soft", "keycloak.org", "Remote", "Worldwide remote"),
    # Australia
    ("Canva Soft2", "canva.com", "Australia", "Sydney / remote"),
    ("Atlassian Soft2", "atlassian.com", "Australia", "Sydney / remote"),
    ("Afterpay Soft", "afterpay.com", "Australia", "Melbourne / remote"),
    ("Zip Soft", "zip.co", "Australia", "Sydney / remote"),
    ("Culture Amp Soft", "cultureamp.com", "Australia", "Melbourne / remote"),
    ("Employment Hero Soft", "employmenthero.com", "Australia", "Sydney / remote"),
    ("Deputy Soft", "deputy.com", "Australia", "Sydney / remote"),
    ("SafetyCulture Soft", "safetyculture.com", "Australia", "Sydney / remote"),
    ("Envato Soft", "envato.com", "Australia", "Melbourne / remote"),
    ("Campaign Monitor Soft", "campaignmonitor.com", "Australia", "Sydney / remote"),
    ("Braintree Soft", "braintree.com", "Australia", "Sydney / remote"),
    ("Immutable Soft", "immutable.com", "Australia", "Sydney / remote"),
    ("Linktree Soft", "linktr.ee", "Australia", "Melbourne / remote"),
    ("Airwallex Soft", "airwallex.com", "Australia", "Melbourne / remote"),
    ("Tyro Soft", "tyro.com", "Australia", "Sydney / remote"),
    ("Judo Soft", "judo.bank", "Australia", "Melbourne / remote"),
    ("Prospa Soft", "prospa.com", "Australia", "Sydney / remote"),
    ("Brighte Soft", "brighte.com.au", "Australia", "Sydney / remote"),
    ("Finder Soft", "finder.com.au", "Australia", "Sydney / remote"),
    ("Expert360 Soft", "expert360.com", "Australia", "Sydney / remote"),
    ("Airtasker Soft", "airtasker.com", "Australia", "Sydney / remote"),
    ("Carsales Soft", "carsales.com.au", "Australia", "Melbourne / remote"),
    ("REA Soft", "rea-group.com", "Australia", "Melbourne / remote"),
    ("Domain Soft", "domain.com.au", "Australia", "Sydney / remote"),
    ("Seek Soft", "seek.com.au", "Australia", "Melbourne / remote"),
    ("Xero Soft", "xero.com", "Australia", "Wellington / remote"),
    ("MYOB Soft", "myob.com", "Australia", "Melbourne / remote"),
    ("Reckon Soft", "reckon.com", "Australia", "Sydney / remote"),
    ("SiteMinder Soft", "siteminder.com", "Australia", "Sydney / remote"),
    ("Nitro Soft", "gonitro.com", "Australia", "Sydney / remote"),
    ("Nearmap Soft", "nearmap.com", "Australia", "Sydney / remote"),
    ("Archistar Soft", "archistar.ai", "Australia", "Sydney / remote"),
    ("Propeller Soft", "propelleraero.com", "Australia", "Sydney / remote"),
    ("Buildkite Soft", "buildkite.com", "Australia", "Melbourne / remote"),
    ("Local Measure Soft", "localmeasure.com", "Australia", "Sydney / remote"),
    ("Culture Amp Soft2", "cultureamp.co", "Australia", "Melbourne / remote"),
    # MENA / GCC product
    ("Tabby Soft", "tabby.ai", "UAE", "Dubai / remote"),
    ("Tamara Soft", "tamara.co", "KSA", "Riyadh / remote"),
    ("PostPay Soft", "postpay.io", "UAE", "Dubai / remote"),
    ("Spotii Soft", "spotii.com", "UAE", "Dubai / remote"),
    ("Sarwa Soft", "sarwa.co", "UAE", "Dubai / remote"),
    ("ShariaPortfolio Soft", "shariaportfolio.com", "UAE", "Dubai / remote"),
    ("Wahed Soft", "wahed.com", "UAE", "Dubai / remote"),
    ("Sarwa Soft2", "sarwa.ai", "UAE", "Dubai / remote"),
    ("Bayzat Soft", "bayzat.com", "UAE", "Dubai / remote"),
    ("Mamo Soft", "mamopay.com", "UAE", "Dubai / remote"),
    ("Lean Soft", "leantech.me", "UAE", "Dubai / remote"),
    ("Tarabut Soft", "tarabut.com", "Bahrain", "Manama / remote"),
    ("Network International Soft", "network.ae", "UAE", "Dubai / remote"),
    ("Magnati Soft", "magnati.com", "UAE", "Dubai / remote"),
    ("PayTabs Soft", "paytabs.com", "KSA", "Riyadh / remote"),
    ("HyperPay Soft", "hyperpay.com", "KSA", "Riyadh / remote"),
    ("Moyasar Soft", "moyasar.com", "KSA", "Riyadh / remote"),
    ("Foodics Soft", "foodics.com", "KSA", "Riyadh / remote"),
    ("Salla Soft", "salla.sa", "KSA", "Riyadh / remote"),
    ("Zid Soft", "zid.sa", "KSA", "Riyadh / remote"),
    ("Jahez Soft", "jahez.net", "KSA", "Riyadh / remote"),
    ("HungerStation Soft", "hungerstation.com", "KSA", "Riyadh / remote"),
    ("Mrsool Soft", "mrsool.com", "KSA", "Riyadh / remote"),
    ("Nana Soft", "nana.sa", "KSA", "Riyadh / remote"),
    ("Unifonic Soft", "unifonic.com", "KSA", "Riyadh / remote"),
    ("Careem Soft2", "careem.com", "UAE", "Dubai / remote"),
    ("Noon Soft", "noon.com", "UAE", "Dubai / remote"),
    ("Amazon Soft AE", "amazon.ae", "UAE", "Dubai / remote"),
    ("Fetchr Soft", "fetchr.us", "UAE", "Dubai / remote"),
    ("Swvl Soft", "swvl.com", "Egypt", "Cairo / remote"),
    ("MaxAB Soft", "maxab.co", "Egypt", "Cairo / remote"),
    ("Breadfast Soft", "breadfast.com", "Egypt", "Cairo / remote"),
    ("Vezeeta Soft", "vezeeta.com", "Egypt", "Cairo / remote"),
    ("Instabug Soft", "instabug.com", "Egypt", "Cairo / remote"),
    ("Eventtus Soft", "eventtus.com", "Egypt", "Cairo / remote"),
    ("Flat6Labs Soft", "flat6labs.com", "Egypt", "Cairo / remote"),
    ("Fawry Soft", "fawry.com", "Egypt", "Cairo / remote"),
    ("Paymob Soft", "paymob.com", "Egypt", "Cairo / remote"),
    ("Sympl Soft", "sympl.ai", "Egypt", "Cairo / remote"),
    ("Valify Soft", "valify.me", "Egypt", "Cairo / remote"),
    ("MoneyFellows Soft", "moneyfellows.com", "Egypt", "Cairo / remote"),
    ("Khazna Soft", "khazna.me", "Egypt", "Cairo / remote"),
    ("Telda Soft", "telda.com", "Egypt", "Cairo / remote"),
    ("Halan Soft", "halan.com", "Egypt", "Cairo / remote"),
    ("Trella Soft", "trella.app", "Egypt", "Cairo / remote"),
    ("Rabbit Soft", "rabbitmart.com", "Egypt", "Cairo / remote"),
    ("Elmenus Soft", "elmenus.com", "Egypt", "Cairo / remote"),
    ("Otlob Soft", "otlob.com", "Egypt", "Cairo / remote"),
    ("Property Finder Soft", "propertyfinder.ae", "UAE", "Dubai / remote"),
    ("Bayut Soft", "bayut.com", "UAE", "Dubai / remote"),
    ("Dubizzle Soft", "dubizzle.com", "UAE", "Dubai / remote"),
    ("OpenSooq Soft", "opensooq.com", "Jordan", "Amman / remote"),
    ("Mawdoo3 Soft", "mawdoo3.com", "Jordan", "Amman / remote"),
    ("ArabiaWeather Soft", "arabiaweather.com", "Jordan", "Amman / remote"),
    ("MadfooatCom Soft", "madfooat.com", "Jordan", "Amman / remote"),
    ("HyperPay Soft2", "hyperpay.net", "Jordan", "Amman / remote"),
    ("Jeel Soft", "jeelpay.com", "Kuwait", "Kuwait / remote"),
    ("Tap Soft", "tap.company", "Kuwait", "Kuwait / remote"),
    ("MyFatoorah Soft", "myfatoorah.com", "Kuwait", "Kuwait / remote"),
    ("Boom Soft", "boom.sa", "KSA", "Riyadh / remote"),
    ("Stc Pay Soft", "stcpay.com.sa", "KSA", "Riyadh / remote"),
    ("AlRajhi Soft", "alrajhibank.com.sa", "KSA", "Riyadh"),
    ("QNB Soft", "qnb.com", "Qatar", "Doha"),
    ("CBQ Soft", "cbq.qa", "Qatar", "Doha"),
    ("Doha Bank Soft", "dohabank.com.qa", "Qatar", "Doha"),
    ("Ooredoo Soft", "ooredoo.qa", "Qatar", "Doha"),
    ("Vodafone Soft QA", "vodafone.qa", "Qatar", "Doha"),
    ("Beeah Soft", "beeah.ae", "UAE", "Sharjah / remote"),
    ("Majid Soft", "majidalfuttaim.com", "UAE", "Dubai / remote"),
    ("Emaar Soft", "emaar.com", "UAE", "Dubai / remote"),
    ("DP World Soft", "dpworld.com", "UAE", "Dubai / remote"),
    # Pakistan fresh product / IT
    ("Systems Limited Soft2", "systemsltd.com", "Pakistan", "Lahore / remote"),
    ("Netsol Soft2", "netsoltech.com", "Pakistan", "Lahore / remote"),
    ("10Pearls Soft2", "10pearls.com", "Pakistan", "Karachi / remote"),
    ("Arbisoft Soft2", "arbisoft.com", "Pakistan", "Lahore / remote"),
    ("VentureDive Soft2", "venturedive.com", "Pakistan", "Karachi / remote"),
    ("Confiz Soft2", "confiz.com", "Pakistan", "Lahore / remote"),
    ("Emumba Soft2", "emumba.com", "Pakistan", "Islamabad / remote"),
    ("Devsinc Soft2", "devsinc.com", "Pakistan", "Lahore / remote"),
    ("Tkxel Soft2", "tkxel.com", "Pakistan", "Lahore / remote"),
    ("Folio3 Soft2", "folio3.com", "Karachi", "Karachi"),
    ("Tintash Soft2", "tintash.com", "Karachi", "Karachi"),
    ("Xgrid Soft2", "xgrid.co", "Karachi", "Karachi"),
    ("Creative Chaos Soft2", "creativechaos.co", "Karachi", "Karachi"),
    ("NorthBay Soft2", "northbaysolutions.com", "Karachi", "Karachi"),
    ("Techlogix Soft2", "techlogix.com", "Karachi", "Karachi"),
    ("Contour Soft2", "contour-software.com", "Karachi", "Karachi"),
    ("Afiniti Soft2", "afiniti.com", "Pakistan", "Islamabad / remote"),
    ("Careem Soft PK", "careem.pk", "Karachi", "Karachi"),
    ("Bykea Soft2", "bykea.com", "Karachi", "Karachi"),
    ("Airlift Soft2", "airlifttechnologies.com", "Karachi", "Karachi"),
    ("Bazaar Soft2", "bazaar.tech", "Karachi", "Karachi"),
    ("Retailo Soft2", "retailo.tech", "Karachi", "Karachi"),
    ("SadaPay Soft2", "sadapay.pk", "Karachi", "Karachi"),
    ("NayaPay Soft2", "nayapay.com", "Karachi", "Karachi"),
    ("Abhi Soft2", "abhi.com.pk", "Karachi", "Karachi"),
    ("Finja Soft2", "finja.pk", "Pakistan", "Lahore"),
    ("Keenu Soft2", "keenu.pk", "Karachi", "Karachi"),
    ("Haball Soft2", "haball.pk", "Karachi", "Karachi"),
    ("Dastgyr Soft2", "dastgyr.pk", "Karachi", "Karachi"),
    ("Tez Soft2", "tez.pk", "Pakistan", "Lahore"),
    ("Dukan Soft2", "dukan.com", "Pakistan", "Lahore"),
    ("PriceOye Soft2", "priceoye.pk", "Pakistan", "Lahore"),
    ("Daraz Soft2", "daraz.pk", "Karachi", "Karachi"),
    ("Foodpanda Soft2", "foodpanda.pk", "Karachi", "Karachi"),
    ("Rozee Soft", "rozee.pk", "Pakistan", "Lahore / remote"),
    ("Mustakbil Soft", "mustakbil.com", "Pakistan", "Karachi / remote"),
    ("BrightSpyre Soft2", "brightspyre.com", "Pakistan", "Islamabad"),
    ("Bayt Soft", "bayt.com", "UAE", "Dubai / remote"),
    ("GulfTalent Soft", "gulftalent.com", "UAE", "Dubai / remote"),
    ("Hirect Soft", "hirect.in", "Remote", "Worldwide remote"),
    ("Wellfound Soft2", "angel.co", "Remote", "Worldwide remote"),
    ("Y Combinator Soft", "ycombinator.com", "Remote", "Worldwide remote"),
    ("Remote Soft", "remote.com", "Remote", "Worldwide remote"),
    ("Deel Soft", "deel.com", "Remote", "Worldwide remote"),
    ("Oyster Soft", "oysterhr.com", "Remote", "Worldwide remote"),
    ("Rippling Soft", "rippling.com", "Remote", "Worldwide remote"),
    ("Gusto Soft", "gusto.com", "Remote", "Worldwide remote"),
    ("Justworks Soft", "justworks.com", "Remote", "Worldwide remote"),
    ("Lattice Soft", "lattice.com", "Remote", "Worldwide remote"),
    ("15Five Soft", "15five.com", "Remote", "Worldwide remote"),
    ("Culture Amp Soft3", "cultureamp.com.au", "Australia", "Melbourne / remote"),
    ("Leapsome Soft", "leapsome.com", "Europe", "Berlin / remote"),
    ("Personio Soft2", "personio.de", "Europe", "Munich / remote"),
    ("Factorial Soft", "factorialhr.com", "Europe", "Barcelona / remote"),
    ("Kenjo Soft", "kenjo.io", "Europe", "Berlin / remote"),
    ("Hibob Soft", "hibob.com", "Europe", "London / remote"),
    ("CharlieHR Soft", "charliehr.com", "Europe", "London / remote"),
    ("Breathe Soft", "breathehr.com", "Europe", "London / remote"),
    ("BambooHR Soft", "bamboohr.com", "Remote", "Worldwide remote"),
    ("Workday Soft", "workday.com", "Remote", "Worldwide remote"),
    ("UKG Soft", "ukg.com", "Remote", "Worldwide remote"),
    ("ADP Soft", "adp.com", "Remote", "Worldwide remote"),
    ("Paychex Soft", "paychex.com", "Remote", "Worldwide remote"),
    ("Paylocity Soft", "paylocity.com", "Remote", "Worldwide remote"),
    ("Paycom Soft", "paycom.com", "Remote", "Worldwide remote"),
    # More remote AI / developer tools
    ("Anthropic Soft", "anthropic.com", "Remote", "Worldwide remote"),
    ("OpenAI Soft", "openai.com", "Remote", "Worldwide remote"),
    ("Cohere Soft", "cohere.com", "Remote", "Worldwide remote"),
    ("Adept Soft", "adept.ai", "Remote", "Worldwide remote"),
    ("Inflection Soft", "inflection.ai", "Remote", "Worldwide remote"),
    ("Character Soft", "character.ai", "Remote", "Worldwide remote"),
    ("Perplexity Soft", "perplexity.ai", "Remote", "Worldwide remote"),
    ("You Soft", "you.com", "Remote", "Worldwide remote"),
    ("Glean Soft", "glean.com", "Remote", "Worldwide remote"),
    ("Hebbia Soft", "hebbia.com", "Remote", "Worldwide remote"),
    ("Harvey Soft", "harvey.ai", "Remote", "Worldwide remote"),
    ("EvenUp Soft", "evenuplaw.com", "Remote", "Worldwide remote"),
    ("Casetext Soft", "casetext.com", "Remote", "Worldwide remote"),
    ("Spellbook Soft", "spellbook.legal", "Remote", "Worldwide remote"),
    ("Ironclad Soft", "ironcladapp.com", "Remote", "Worldwide remote"),
    ("DocuSign Soft", "docusign.com", "Remote", "Worldwide remote"),
    ("PandaDoc Soft", "pandadoc.com", "Remote", "Worldwide remote"),
    ("HelloSign Soft", "hellosign.com", "Remote", "Worldwide remote"),
    ("Dropbox Soft", "dropbox.com", "Remote", "Worldwide remote"),
    ("Box Soft", "box.com", "Remote", "Worldwide remote"),
    ("Egnyte Soft", "egnyte.com", "Remote", "Worldwide remote"),
    ("Lucid Soft", "lucid.co", "Remote", "Worldwide remote"),
    ("Miro Soft", "miro.com", "Remote", "Worldwide remote"),
    ("Figma Soft", "figma.com", "Remote", "Worldwide remote"),
    ("Abstract Soft", "abstract.com", "Remote", "Worldwide remote"),
    ("InVision Soft", "invisionapp.com", "Remote", "Worldwide remote"),
    ("Webflow Soft", "webflow.com", "Remote", "Worldwide remote"),
    ("Framer Soft", "framer.com", "Remote", "Worldwide remote"),
    ("Bubble Soft", "bubble.io", "Remote", "Worldwide remote"),
    ("Adalo Soft", "adalo.com", "Remote", "Worldwide remote"),
    ("Glide Soft", "glideapps.com", "Remote", "Worldwide remote"),
    ("Softr Soft", "softr.io", "Europe", "Berlin / remote"),
    ("Typedream Soft", "typedream.com", "Remote", "Worldwide remote"),
    ("Carrd Soft", "carrd.co", "Remote", "Worldwide remote"),
    ("Super Soft", "super.so", "Remote", "Worldwide remote"),
    ("Ghost Soft", "ghost.org", "Remote", "Worldwide remote"),
    ("Substack Soft", "substack.com", "Remote", "Worldwide remote"),
    ("Beehiiv Soft", "beehiiv.com", "Remote", "Worldwide remote"),
    ("ConvertKit Soft", "convertkit.com", "Remote", "Worldwide remote"),
    ("Mailchimp Soft", "mailchimp.com", "Remote", "Worldwide remote"),
    ("Klaviyo Soft", "klaviyo.com", "Remote", "Worldwide remote"),
    ("ActiveCampaign Soft", "activecampaign.com", "Remote", "Worldwide remote"),
    ("Customer.io Soft2", "customerio.com", "Remote", "Worldwide remote"),
    ("Postmark Soft", "postmarkapp.com", "Remote", "Worldwide remote"),
    ("SendGrid Soft", "sendgrid.com", "Remote", "Worldwide remote"),
    ("Mailgun Soft", "mailgun.com", "Remote", "Worldwide remote"),
    ("Resend Soft", "resend.com", "Remote", "Worldwide remote"),
    ("Loops Soft", "loops.so", "Remote", "Worldwide remote"),
    ("Buttondown Soft", "buttondown.email", "Remote", "Worldwide remote"),
    ("Plausible Soft", "plausible.io", "Europe", "Tallinn / remote"),
    ("Fathom Soft", "usefathom.com", "Remote", "Worldwide remote"),
    ("Simple Analytics Soft", "simpleanalytics.com", "Europe", "Netherlands / remote"),
    ("Pirsch Soft", "pirsch.io", "Europe", "Germany / remote"),
    ("Matomo Soft", "matomo.org", "Europe", "New Zealand / remote"),
    ("Umami Soft", "umami.is", "Remote", "Worldwide remote"),
    ("Cal Soft", "cal.com", "Remote", "Worldwide remote"),
    ("Calendly Soft", "calendly.com", "Remote", "Worldwide remote"),
    ("SavvyCal Soft", "savvycal.com", "Remote", "Worldwide remote"),
    ("TidyCal Soft", "tidycal.com", "Remote", "Worldwide remote"),
    ("Cron Soft", "cron.com", "Remote", "Worldwide remote"),
    ("Reclaim Soft", "reclaim.ai", "Remote", "Worldwide remote"),
    ("Motion Soft", "usemotion.com", "Remote", "Worldwide remote"),
    ("Clockwise Soft", "getclockwise.com", "Remote", "Worldwide remote"),
    ("Linear Soft", "linear.app", "Remote", "Worldwide remote"),
    ("Height Soft", "height.app", "Remote", "Worldwide remote"),
    ("Plane Soft", "plane.so", "Remote", "Worldwide remote"),
    ("Shortcut Soft", "shortcut.com", "Remote", "Worldwide remote"),
    ("Clubhouse Soft", "clubhouse.com", "Remote", "Worldwide remote"),
    ("Asana Soft", "asana.com", "Remote", "Worldwide remote"),
    ("Monday Soft", "monday.com", "Remote", "Worldwide remote"),
    ("ClickUp Soft", "clickup.com", "Remote", "Worldwide remote"),
    ("Basecamp Soft", "basecamp.com", "Remote", "Worldwide remote"),
    ("Trello Soft", "trello.com", "Remote", "Worldwide remote"),
    ("Jira Soft", "atlassian.net", "Remote", "Worldwide remote"),
    ("GitLab Soft", "gitlab.com", "Remote", "Worldwide remote"),
    ("GitHub Soft", "github.com", "Remote", "Worldwide remote"),
    ("Bitbucket Soft", "bitbucket.org", "Remote", "Worldwide remote"),
    ("Sourcegraph Soft", "sourcegraph.com", "Remote", "Worldwide remote"),
    ("Cursor Soft", "cursor.com", "Remote", "Worldwide remote"),
    ("Replit Soft", "replit.com", "Remote", "Worldwide remote"),
    ("CodeSandbox Soft", "codesandbox.io", "Remote", "Worldwide remote"),
    ("Gitpod Soft", "gitpod.io", "Europe", "Kiel / remote"),
    ("Coder Soft", "coder.com", "Remote", "Worldwide remote"),
    ("StackBlitz Soft2", "stackblitz.io", "Remote", "Worldwide remote"),
    ("Val Town Soft", "val.town", "Remote", "Worldwide remote"),
    ("Modal Soft", "modal.com", "Remote", "Worldwide remote"),
    ("Banana Soft", "banana.dev", "Remote", "Worldwide remote"),
    ("Replicate Soft", "replicate.com", "Remote", "Worldwide remote"),
    ("Together Soft", "together.ai", "Remote", "Worldwide remote"),
    ("Fireworks Soft", "fireworks.ai", "Remote", "Worldwide remote"),
    ("Anyscale Soft", "anyscale.com", "Remote", "Worldwide remote"),
    ("Baseten Soft", "baseten.co", "Remote", "Worldwide remote"),
    ("Weights Biases Soft", "wandb.ai", "Remote", "Worldwide remote"),
    ("Comet Soft", "comet.com", "Remote", "Worldwide remote"),
    ("Neptune Soft", "neptune.ai", "Europe", "Warsaw / remote"),
    ("Labelbox Soft", "labelbox.com", "Remote", "Worldwide remote"),
    ("Scale Soft", "scale.com", "Remote", "Worldwide remote"),
    ("Snorkel Soft", "snorkel.ai", "Remote", "Worldwide remote"),
    ("Hugging Face Soft2", "hf.co", "Europe", "Paris / remote"),
    ("LangChain Soft", "langchain.com", "Remote", "Worldwide remote"),
    ("LlamaIndex Soft2", "llamaindex.ai", "Remote", "Worldwide remote"),
    ("Haystack Soft", "haystack.deepset.ai", "Europe", "Berlin / remote"),
    ("Deepset Soft", "deepset.ai", "Europe", "Berlin / remote"),
    ("Weaviate Soft", "weaviate.io", "Europe", "Amsterdam / remote"),
    ("Pinecone Soft", "pinecone.io", "Remote", "Worldwide remote"),
    ("Qdrant Soft", "qdrant.tech", "Europe", "Berlin / remote"),
    ("Chroma Soft", "trychroma.com", "Remote", "Worldwide remote"),
    ("Milvus Soft", "zilliz.com", "Remote", "Worldwide remote"),
    ("Turbopuffer Soft", "turbopuffer.com", "Remote", "Worldwide remote"),
    ("Voyage Soft", "voyageai.com", "Remote", "Worldwide remote"),
    ("Nomic Soft", "nomic.ai", "Remote", "Worldwide remote"),
    ("Jina Soft", "jina.ai", "Europe", "Berlin / remote"),
    ("Unstructured Soft", "unstructured.io", "Remote", "Worldwide remote"),
    ("LlamaParse Soft", "llamaparse.ai", "Remote", "Worldwide remote"),
    ("Reducto Soft", "reducto.ai", "Remote", "Worldwide remote"),
    ("Extend Soft", "extend.ai", "Remote", "Worldwide remote"),
    ("Parseur Soft", "parseur.com", "Remote", "Worldwide remote"),
]

TRY = ["careers", "hr", "jobs", "people", "recruiting", "talent", "hiring", "join"]
GOOGLEISH = ("google", "gmail", "googlemail", "aspmx", "larksuite", "lark", "feishu")
TARGET = {
    "Karachi",
    "Pakistan",
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
SUFFIXES = {
    "PK", "KW", "QA", "AE", "SA", "EG", "JO", "BH", "SG", "MY", "AU", "EU", "RM",
    "Soft", "Soft2", "Soft3", "Digital", "Tech", "Careers",
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
    target_hits = 16
    for i, (_pri, region, name, domain, city, locs) in enumerate(google, 1):
        if len(found) >= target_hits:
            print(f"hit {target_hits}, stop", flush=True)
            break
        for loc in locs:
            email = f"{loc}@{domain}"
            print(f"[{i}/{len(google)}] probe {email} ({name} / {region})", flush=True)
            ok, detail = verify_mailbox(email)
            time.sleep(0.2)
            if ok:
                stats["ok"] += 1
                print(f"  OK  {email}  {detail[:110]}", flush=True)
                clean = name
                parts = name.split()
                while parts and parts[-1] in SUFFIXES:
                    parts.pop()
                if parts:
                    clean = " ".join(parts)
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

    out = ROOT / "output" / "emails_shortlist_batch25_2026-08-15.csv"
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
