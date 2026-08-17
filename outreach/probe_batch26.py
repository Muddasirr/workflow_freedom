#!/usr/bin/env python3
"""Probe batch26 — fill remaining daily slots with fresh Google/Lark domains."""
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
    # Australia leftovers / ANZ
    ("Deputy Soft3", "deputy.com.au", "Australia", "Sydney / remote"),
    ("Employment Hero Soft3", "eh.com.au", "Australia", "Sydney / remote"),
    ("Culture Amp Soft4", "cultureamp.io", "Australia", "Melbourne / remote"),
    ("SafetyCulture Soft3", "safetyculture.io", "Australia", "Sydney / remote"),
    ("Buildkite Soft3", "buildkite.com.au", "Australia", "Melbourne / remote"),
    ("Immutable Soft3", "immutable.com.au", "Australia", "Sydney / remote"),
    ("Linktree Soft3", "linktree.com", "Australia", "Melbourne / remote"),
    ("Airwallex Soft3", "airwallex.io", "Australia", "Melbourne / remote"),
    ("Archistar Soft3", "archistar.com.au", "Australia", "Sydney / remote"),
    ("Propeller Soft3", "propelleraero.com.au", "Australia", "Sydney / remote"),
    ("Nitro Soft3", "nitro.com", "Australia", "Sydney / remote"),
    ("SiteMinder Soft3", "siteminder.com.au", "Australia", "Sydney / remote"),
    ("Expert360 Soft3", "expert360.com.au", "Australia", "Sydney / remote"),
    ("Airtasker Soft3", "airtasker.com.au", "Australia", "Sydney / remote"),
    ("Brighte Soft3", "brighte.com", "Australia", "Sydney / remote"),
    ("Prospa Soft3", "prospa.com.au", "Australia", "Sydney / remote"),
    ("Judo Soft3", "judo.bank", "Australia", "Melbourne / remote"),
    ("Tyro Soft3", "tyro.com.au", "Australia", "Sydney / remote"),
    ("Nearmap Soft3", "nearmap.com.au", "Australia", "Sydney / remote"),
    ("Canva Soft3", "canva.dev", "Australia", "Sydney / remote"),
    # Europe product mid-size
    ("Pennylane Soft3", "pennylane.tech", "Europe", "Paris / remote"),
    ("Spendesk Soft3", "spendesk.io", "Europe", "Paris / remote"),
    ("Qonto Soft3", "qonto.eu", "Europe", "Paris / remote"),
    ("Swile Soft3", "swile.com", "Europe", "Paris / remote"),
    ("Alan Soft3", "alan.eu", "Europe", "Paris / remote"),
    ("Doctolib Soft3", "doctolib.fr", "Europe", "Paris / remote"),
    ("Back Market Soft3", "backmarket.fr", "Europe", "Paris / remote"),
    ("Mirakl Soft3", "mirakl.net", "Europe", "Paris / remote"),
    ("Photoroom Soft3", "photoroom.app", "Europe", "Paris / remote"),
    ("Dust Soft3", "dust.tt", "Europe", "Paris / remote"),
    ("Crew Soft3", "crew.work", "Europe", "Paris / remote"),
    ("Pigment Soft3", "pigment.app", "Europe", "Paris / remote"),
    ("Sorare Soft3", "sorare.co", "Europe", "Paris / remote"),
    ("Scaleway Soft3", "scaleway.io", "Europe", "Paris / remote"),
    ("Clever Cloud Soft3", "clever-cloud.io", "Europe", "Nantes / remote"),
    ("Leapsome Soft3", "leapsome.io", "Europe", "Berlin / remote"),
    ("Personio Soft3", "personio.io", "Europe", "Munich / remote"),
    ("Factorial Soft3", "factorial.co", "Europe", "Barcelona / remote"),
    ("Contentful Soft3", "contentful.io", "Europe", "Berlin / remote"),
    ("SumUp Soft3", "sumup.io", "Europe", "London / remote"),
    ("Trade Republic Soft3", "traderepublic.io", "Europe", "Berlin / remote"),
    ("GetYourGuide Soft3", "getyourguide.io", "Europe", "Berlin / remote"),
    ("Mollie Soft3", "mollie.io", "Europe", "Amsterdam / remote"),
    ("Bunq Soft3", "bunq.io", "Europe", "Amsterdam / remote"),
    ("MessageBird Soft3", "bird.com", "Europe", "Amsterdam / remote"),
    ("Aiven Soft3", "aiven.com", "Europe", "Helsinki / remote"),
    ("Weaviate Soft3", "weaviate.com", "Europe", "Amsterdam / remote"),
    ("Qdrant Soft3", "qdrant.io", "Europe", "Berlin / remote"),
    ("Deepset Soft3", "deepset.com", "Europe", "Berlin / remote"),
    ("Neptune Soft3", "neptune.ml", "Europe", "Warsaw / remote"),
    ("Plausible Soft3", "plausible.com", "Europe", "Tallinn / remote"),
    ("Softr Soft3", "softr.com", "Europe", "Berlin / remote"),
    ("Gitpod Soft3", "gitpod.com", "Europe", "Kiel / remote"),
    ("Tyk Soft3", "tyk.com", "Europe", "London / remote"),
    ("Gravitee Soft3", "gravitee.com", "Europe", "Lille / remote"),
    ("Attio Soft3", "attio.io", "Europe", "London / remote"),
    ("Hibob Soft3", "hibob.io", "Europe", "London / remote"),
    ("Citymapper Soft3", "citymapper.io", "Europe", "London / remote"),
    ("GoCardless Soft3", "gocardless.io", "Europe", "London / remote"),
    ("Checkout Soft3", "checkout.io", "Europe", "London / remote"),
    ("Monzo Soft3", "monzo.io", "Europe", "London / remote"),
    ("Starling Soft3", "starlingbank.io", "Europe", "London / remote"),
    ("Wise Soft3", "transferwise.com", "Europe", "London / remote"),
    ("Darktrace Soft3", "darktrace.io", "Europe", "Cambridge / remote"),
    ("Graphcore Soft3", "graphcore.com", "Europe", "Bristol / remote"),
    ("Improbable Soft3", "improbable.com", "Europe", "London / remote"),
    ("Stability Soft3", "stability.ai", "Europe", "London / remote"),
    ("Mistral Soft3", "mistral.com", "Europe", "Paris / remote"),
    # MENA / GCC product
    ("Tabby Soft3", "gettabby.com", "UAE", "Dubai / remote"),
    ("Tamara Soft3", "tamara.com", "KSA", "Riyadh / remote"),
    ("PostPay Soft3", "postpay.com", "UAE", "Dubai / remote"),
    ("Mamo Soft3", "mamo.com", "UAE", "Dubai / remote"),
    ("Lean Soft3", "lean.sa", "KSA", "Riyadh / remote"),
    ("Tarabut Soft3", "tarabutgateway.com", "Bahrain", "Manama / remote"),
    ("Foodics Soft3", "foodics.sa", "KSA", "Riyadh / remote"),
    ("Salla Soft3", "salla.com", "KSA", "Riyadh / remote"),
    ("Zid Soft3", "zid.com", "KSA", "Riyadh / remote"),
    ("Jahez Soft3", "jahez.com", "KSA", "Riyadh / remote"),
    ("Unifonic Soft3", "unifonic.io", "KSA", "Riyadh / remote"),
    ("Instabug Soft3", "instabug.io", "Egypt", "Cairo / remote"),
    ("Paymob Soft3", "paymob.io", "Egypt", "Cairo / remote"),
    ("MoneyFellows Soft3", "moneyfellows.app", "Egypt", "Cairo / remote"),
    ("Telda Soft3", "telda.app", "Egypt", "Cairo / remote"),
    ("Halan Soft3", "halan.app", "Egypt", "Cairo / remote"),
    ("Trella Soft3", "trella.com", "Egypt", "Cairo / remote"),
    ("Breadfast Soft3", "breadfast.app", "Egypt", "Cairo / remote"),
    ("MaxAB Soft3", "maxab.com", "Egypt", "Cairo / remote"),
    ("Vezeeta Soft3", "vezeeta.io", "Egypt", "Cairo / remote"),
    ("Swvl Soft3", "swvl.io", "Egypt", "Cairo / remote"),
    ("Property Finder Soft3", "propertyfinder.com", "UAE", "Dubai / remote"),
    ("Bayut Soft3", "bayut.ae", "UAE", "Dubai / remote"),
    ("GulfTalent Soft3", "gulftalent.ae", "UAE", "Dubai / remote"),
    ("MyFatoorah Soft3", "myfatoorah.kw", "Kuwait", "Kuwait / remote"),
    ("Tap Soft3", "tap.payments", "Kuwait", "Kuwait / remote"),
    ("Jeel Soft3", "jeel.com", "Kuwait", "Kuwait / remote"),
    ("SkipCash Soft3", "skipcash.app", "Kuwait", "Kuwait / remote"),
    ("UPayments Soft3", "upayments.app", "Kuwait", "Kuwait / remote"),
    # Pakistan
    ("Systems Limited Soft3", "systemslimited.com", "Pakistan", "Lahore / remote"),
    ("Netsol Soft3", "netsol.com.pk", "Pakistan", "Lahore / remote"),
    ("10Pearls Soft3", "10pearls.pk", "Pakistan", "Karachi / remote"),
    ("Arbisoft Soft3", "arbisoft.pk", "Pakistan", "Lahore / remote"),
    ("VentureDive Soft3", "venturedive.pk", "Pakistan", "Karachi / remote"),
    ("Confiz Soft3", "confiz.pk", "Pakistan", "Lahore / remote"),
    ("Emumba Soft3", "emumba.pk", "Pakistan", "Islamabad / remote"),
    ("Devsinc Soft3", "devsinc.pk", "Pakistan", "Lahore / remote"),
    ("Tkxel Soft3", "tkxel.pk", "Pakistan", "Lahore / remote"),
    ("Afiniti Soft3", "afiniti.pk", "Pakistan", "Islamabad / remote"),
    ("Rozee Soft3", "rozee.com", "Pakistan", "Lahore / remote"),
    ("Mustakbil Soft3", "mustakbil.pk", "Pakistan", "Karachi / remote"),
    ("Dastgyr Soft3", "dastgyr.app", "Karachi", "Karachi"),
    ("Retailistan Soft3", "retailistan.pk", "Karachi", "Karachi"),
    ("Golootlo Soft3", "golootlo.com", "Karachi", "Karachi"),
    ("Bookme Soft3", "bookme.pk", "Pakistan", "Lahore"),
    ("Dawaai Soft3", "dawaai.pk", "Karachi", "Karachi"),
    ("Sastaticket Soft3", "sastaticket.pk", "Karachi", "Karachi"),
    ("PakWheels Soft3", "pakwheels.com", "Karachi", "Karachi"),
    ("Zameen Soft3", "zameen.com", "Karachi", "Karachi"),
    ("OLX Soft3", "olx.com.pk", "Karachi", "Karachi"),
    ("Easypaisa Soft3", "easypaisa.com.pk", "Pakistan", "Islamabad"),
    ("JazzCash Soft3", "jazzcash.com.pk", "Pakistan", "Islamabad"),
    ("WebHR Soft3", "webhr.com", "Pakistan", "Lahore / remote"),
    ("Fermat Soft3", "fermat.com", "Pakistan", "Lahore / remote"),
    ("VTeams Soft3", "vteams.pk", "Pakistan", "Lahore / remote"),
    ("SoftPyramid Soft3", "softpyramid.pk", "Pakistan", "Lahore"),
    ("Sofizar Soft3", "sofizar.pk", "Pakistan", "Lahore"),
    ("Logicose Soft3", "logicose.pk", "Pakistan", "Lahore"),
    ("Ebryx Soft3", "ebryx.pk", "Pakistan", "Lahore / remote"),
    # Remote product / AI / infra not heavily probed
    ("Cursor Soft3", "anysphere.com", "Remote", "Worldwide remote"),
    ("Replit Soft3", "repl.it", "Remote", "Worldwide remote"),
    ("CodeSandbox Soft3", "codesandbox.com", "Remote", "Worldwide remote"),
    ("Modal Soft3", "modal.systems", "Remote", "Worldwide remote"),
    ("Banana Soft3", "banana.com", "Remote", "Worldwide remote"),
    ("Replicate Soft3", "replicate.ai", "Remote", "Worldwide remote"),
    ("Together Soft3", "together.xyz", "Remote", "Worldwide remote"),
    ("Fireworks Soft3", "fireworks.com", "Remote", "Worldwide remote"),
    ("Anyscale Soft3", "anyscale.io", "Remote", "Worldwide remote"),
    ("Baseten Soft3", "baseten.com", "Remote", "Worldwide remote"),
    ("Weights Biases Soft3", "wandb.com", "Remote", "Worldwide remote"),
    ("Labelbox Soft3", "labelbox.io", "Remote", "Worldwide remote"),
    ("Scale Soft3", "scale.ai", "Remote", "Worldwide remote"),
    ("Snorkel Soft3", "snorkel.com", "Remote", "Worldwide remote"),
    ("LangChain Soft3", "langchain.dev", "Remote", "Worldwide remote"),
    ("Pinecone Soft3", "pinecone.ai", "Remote", "Worldwide remote"),
    ("Chroma Soft3", "chroma.com", "Remote", "Worldwide remote"),
    ("Turbopuffer Soft3", "turbopuffer.ai", "Remote", "Worldwide remote"),
    ("Reducto Soft3", "reducto.com", "Remote", "Worldwide remote"),
    ("Extend Soft3", "extend.com", "Remote", "Worldwide remote"),
    ("Perplexity Soft3", "perplexity.com", "Remote", "Worldwide remote"),
    ("Glean Soft3", "glean.co", "Remote", "Worldwide remote"),
    ("Harvey Soft3", "harvey.com", "Remote", "Worldwide remote"),
    ("Hebbia Soft3", "hebbia.ai", "Remote", "Worldwide remote"),
    ("EvenUp Soft3", "evenup.com", "Remote", "Worldwide remote"),
    ("Ironclad Soft3", "ironclad.com", "Remote", "Worldwide remote"),
    ("Spellbook Soft3", "spellbook.ai", "Remote", "Worldwide remote"),
    ("Clerk Soft3", "clerk.dev", "Remote", "Worldwide remote"),
    ("Stytch Soft3", "stytch.io", "Remote", "Worldwide remote"),
    ("WorkOS Soft3", "workos.io", "Remote", "Worldwide remote"),
    ("Descope Soft3", "descope.io", "Remote", "Worldwide remote"),
    ("SuperTokens Soft3", "supertokens.io", "Remote", "Worldwide remote"),
    ("FusionAuth Soft3", "fusionauth.com", "Remote", "Worldwide remote"),
    ("Resend Soft3", "resend.dev", "Remote", "Worldwide remote"),
    ("Loops Soft3", "loops.com", "Remote", "Worldwide remote"),
    ("PostHog Soft3", "posthog.io", "Remote", "Worldwide remote"),
    ("Cal Soft3", "cal.dev", "Remote", "Worldwide remote"),
    ("Linear Soft3", "linear.com", "Remote", "Worldwide remote"),
    ("Height Soft3", "height.com", "Remote", "Worldwide remote"),
    ("Plane Soft3", "plane.com", "Remote", "Worldwide remote"),
    ("Incident Soft3", "incident.com", "Remote", "Worldwide remote"),
    ("Rootly Soft3", "rootly.io", "Remote", "Worldwide remote"),
    ("FireHydrant Soft3", "firehydrant.io", "Remote", "Worldwide remote"),
    ("Chronosphere Soft3", "chronosphere.com", "Remote", "Worldwide remote"),
    ("Honeycomb Soft3", "honeycomb.com", "Remote", "Worldwide remote"),
    ("Buf Soft3", "buf.com", "Remote", "Worldwide remote"),
    ("Temporal Soft3", "temporal.com", "Remote", "Worldwide remote"),
    ("Prefect Soft3", "prefect.com", "Remote", "Worldwide remote"),
    ("Dagster Soft3", "dagster.com", "Remote", "Worldwide remote"),
    ("Airbyte Soft3", "airbyte.io", "Remote", "Worldwide remote"),
    ("dbt Soft3", "dbt.com", "Remote", "Worldwide remote"),
    ("Census Soft3", "census.com", "Remote", "Worldwide remote"),
    ("Hightouch Soft3", "hightouch.io", "Remote", "Worldwide remote"),
    ("RudderStack Soft3", "rudderstack.io", "Remote", "Worldwide remote"),
    ("Customer.io Soft3", "customerio.io", "Remote", "Worldwide remote"),
    ("OneSignal Soft3", "onesignal.io", "Remote", "Worldwide remote"),
    ("Clay Soft3", "clay.io", "Remote", "Worldwide remote"),
    ("Apollo Soft3", "apollo.com", "Remote", "Worldwide remote"),
    ("Appsmith Soft3", "appsmith.io", "Remote", "Worldwide remote"),
    ("Budibase Soft3", "budibase.io", "Remote", "Worldwide remote"),
    ("Tooljet Soft3", "tooljet.io", "Remote", "Worldwide remote"),
    ("N8n Soft3", "n8n.com", "Europe", "Berlin / remote"),
    ("Framer Soft3", "framer.website", "Remote", "Worldwide remote"),
    ("Webflow Soft3", "webflow.io", "Remote", "Worldwide remote"),
    ("Bubble Soft3", "bubble.com", "Remote", "Worldwide remote"),
    ("Ghost Soft3", "ghost.io", "Remote", "Worldwide remote"),
    ("Beehiiv Soft3", "beehiiv.io", "Remote", "Worldwide remote"),
    ("Substack Soft3", "substack.io", "Remote", "Worldwide remote"),
    ("Notion Soft3", "notion.com", "Remote", "Worldwide remote"),
    ("Coda Soft3", "coda.com", "Remote", "Worldwide remote"),
    ("Retool Soft3", "retool.io", "Remote", "Worldwide remote"),
    ("Supabase Soft3", "supabase.io", "Remote", "Worldwide remote"),
    ("Neon Soft3", "neon.com", "Remote", "Worldwide remote"),
    ("PlanetScale Soft3", "planetscale.io", "Remote", "Worldwide remote"),
    ("Railway Soft3", "railway.com", "Remote", "Worldwide remote"),
    ("Render Soft3", "render.io", "Remote", "Worldwide remote"),
    ("Fly Soft3", "fly.com", "Remote", "Worldwide remote"),
    ("Vercel Soft3", "vercel.app", "Remote", "Worldwide remote"),
    ("Netlify Soft3", "netlify.app", "Remote", "Worldwide remote"),
    ("Snyk Soft3", "snyk.com", "Remote", "Worldwide remote"),
    ("Wiz Soft3", "wiz.com", "Remote", "Worldwide remote"),
    ("Orca Soft3", "orca.com", "Remote", "Worldwide remote"),
    ("Material Security Soft3", "material.com", "Remote", "Worldwide remote"),
    ("Drata Soft3", "drata.io", "Remote", "Worldwide remote"),
    ("Secureframe Soft3", "secureframe.io", "Remote", "Worldwide remote"),
    ("JumpCloud Soft3", "jumpcloud.io", "Remote", "Worldwide remote"),
    ("Deel Soft3", "deel.io", "Remote", "Worldwide remote"),
    ("Remote Soft3", "remote.io", "Remote", "Worldwide remote"),
    ("Oyster Soft3", "oyster.com", "Remote", "Worldwide remote"),
    ("Rippling Soft3", "rippling.io", "Remote", "Worldwide remote"),
    ("Lattice Soft3", "latticehq.com", "Remote", "Worldwide remote"),
    ("15Five Soft3", "15five.io", "Remote", "Worldwide remote"),
    ("BambooHR Soft3", "bamboohr.io", "Remote", "Worldwide remote"),
    ("Gusto Soft3", "gusto.io", "Remote", "Worldwide remote"),
    ("Justworks Soft3", "justworks.io", "Remote", "Worldwide remote"),
    ("Sourcegraph Soft3", "sourcegraph.io", "Remote", "Worldwide remote"),
    ("GitLab Soft3", "gitlab.io", "Remote", "Worldwide remote"),
    ("HashiCorp Soft3", "hashicorp.io", "Remote", "Worldwide remote"),
    ("Pulumi Soft3", "pulumi.io", "Remote", "Worldwide remote"),
    ("LaunchDarkly Soft3", "launchdarkly.io", "Remote", "Worldwide remote"),
    ("Statsig Soft3", "statsig.io", "Remote", "Worldwide remote"),
    ("Amplitude Soft3", "amplitude.io", "Remote", "Worldwide remote"),
    ("Mixpanel Soft3", "mixpanel.io", "Remote", "Worldwide remote"),
    ("FullStory Soft3", "fullstory.io", "Remote", "Worldwide remote"),
    ("LogRocket Soft3", "logrocket.io", "Remote", "Worldwide remote"),
    ("Sentry Soft3", "sentry.com", "Remote", "Worldwide remote"),
    ("PagerDuty Soft3", "pagerduty.io", "Remote", "Worldwide remote"),
    ("Grafana Soft3", "grafana.io", "Remote", "Worldwide remote"),
    ("Elastic Soft3", "elastic.com", "Remote", "Worldwide remote"),
    ("ClickHouse Soft3", "clickhouse.io", "Europe", "Amsterdam / remote"),
    ("Redpanda Soft3", "redpanda.io", "Remote", "Worldwide remote"),
    ("WarpStream Soft3", "warpstream.io", "Remote", "Worldwide remote"),
    ("Materialize Soft3", "materialize.io", "Remote", "Worldwide remote"),
    ("RisingWave Soft3", "risingwave.io", "Remote", "Worldwide remote"),
    ("SingleStore Soft3", "singlestore.io", "Remote", "Worldwide remote"),
    ("Yugabyte Soft3", "yugabyte.io", "Remote", "Worldwide remote"),
    ("Hasura Soft3", "hasura.com", "Remote", "Worldwide remote"),
    ("Kong Soft3", "kong.com", "Remote", "Worldwide remote"),
    ("Solo Soft3", "solo.com", "Remote", "Worldwide remote"),
    ("Isovalent Soft3", "isovalent.io", "Remote", "Worldwide remote"),
    ("Sysdig Soft3", "sysdig.io", "Remote", "Worldwide remote"),
    ("Aqua Soft3", "aqua.io", "Remote", "Worldwide remote"),
    ("Lacework Soft3", "lacework.io", "Remote", "Worldwide remote"),
    ("Crowdstrike Soft3", "crowdstrike.io", "Remote", "Worldwide remote"),
    ("SentinelOne Soft3", "sentinelone.io", "Remote", "Worldwide remote"),
    ("Gong Soft3", "gong.com", "Remote", "Worldwide remote"),
    ("Clari Soft3", "clari.io", "Remote", "Worldwide remote"),
    ("Outreach Soft3", "outreach.com", "Remote", "Worldwide remote"),
    ("Salesloft Soft3", "salesloft.io", "Remote", "Worldwide remote"),
    ("Affinity Soft3", "affinity.com", "Remote", "Worldwide remote"),
    ("Intercom Soft3", "intercom.io", "Remote", "Worldwide remote"),
    ("Freshworks Soft3", "freshworks.io", "Remote", "Worldwide remote"),
    ("HubSpot Soft3", "hubspot.io", "Remote", "Worldwide remote"),
    ("Zendesk Soft3", "zendesk.io", "Remote", "Worldwide remote"),
    ("Braze Soft3", "braze.io", "Remote", "Worldwide remote"),
    ("Iterable Soft3", "iterable.io", "Remote", "Worldwide remote"),
    ("Klaviyo Soft3", "klaviyo.io", "Remote", "Worldwide remote"),
    ("ActiveCampaign Soft3", "activecampaign.io", "Remote", "Worldwide remote"),
    ("ConvertKit Soft3", "convertkit.io", "Remote", "Worldwide remote"),
    ("Mailgun Soft3", "mailgun.io", "Remote", "Worldwide remote"),
    ("Postmark Soft3", "postmark.com", "Remote", "Worldwide remote"),
    ("SendGrid Soft3", "sendgrid.io", "Remote", "Worldwide remote"),
    ("Dropbox Soft3", "dropbox.io", "Remote", "Worldwide remote"),
    ("Box Soft3", "box.io", "Remote", "Worldwide remote"),
    ("Egnyte Soft3", "egnyte.io", "Remote", "Worldwide remote"),
    ("Lucid Soft3", "lucidchart.com", "Remote", "Worldwide remote"),
    ("Miro Soft3", "miro.io", "Remote", "Worldwide remote"),
    ("Figma Soft3", "figma.io", "Remote", "Worldwide remote"),
    ("InVision Soft3", "invision.com", "Remote", "Worldwide remote"),
    ("Asana Soft3", "asana.io", "Remote", "Worldwide remote"),
    ("Monday Soft3", "monday.io", "Remote", "Worldwide remote"),
    ("ClickUp Soft3", "clickup.io", "Remote", "Worldwide remote"),
    ("Basecamp Soft3", "basecamp.io", "Remote", "Worldwide remote"),
    ("Shortcut Soft3", "shortcut.io", "Remote", "Worldwide remote"),
    ("Zapier Soft3", "zapier.io", "Remote", "Worldwide remote"),
    ("Make Soft3", "integromat.com", "Europe", "Prague / remote"),
    ("Tray Soft3", "tray.com", "Remote", "Worldwide remote"),
    ("Workato Soft3", "workato.io", "Remote", "Worldwide remote"),
    ("Okta Soft3", "okta.io", "Remote", "Worldwide remote"),
    ("Auth0 Soft3", "auth0.io", "Remote", "Worldwide remote"),
    ("Cloudflare Soft3", "cloudflare.io", "Remote", "Worldwide remote"),
    ("Fastly Soft3", "fastly.io", "Remote", "Worldwide remote"),
    ("Datadog Soft3", "datadog.io", "Remote", "Worldwide remote"),
    ("New Relic Soft3", "newrelic.io", "Remote", "Worldwide remote"),
    ("Dynatrace Soft3", "dynatrace.io", "Remote", "Worldwide remote"),
    ("MongoDB Soft3", "mongodb.io", "Remote", "Worldwide remote"),
    ("Redis Soft3", "redis.com", "Remote", "Worldwide remote"),
    ("Confluent Soft3", "confluent.com", "Remote", "Worldwide remote"),
    ("InfluxData Soft3", "influxdata.io", "Remote", "Worldwide remote"),
    ("Fivetran Soft3", "fivetran.io", "Remote", "Worldwide remote"),
    ("Segment Soft3", "segment.io", "Remote", "Worldwide remote"),
    ("mParticle Soft3", "mparticle.io", "Remote", "Worldwide remote"),
    ("Tealium Soft3", "tealium.io", "Remote", "Worldwide remote"),
    ("Hotjar Soft3", "hotjar.io", "Remote", "Worldwide remote"),
    ("Heap Soft3", "heap.com", "Remote", "Worldwide remote"),
    ("Split Soft3", "split.com", "Remote", "Worldwide remote"),
    ("Reclaim Soft3", "reclaim.com", "Remote", "Worldwide remote"),
    ("Motion Soft3", "motion.com", "Remote", "Worldwide remote"),
    ("Clockwise Soft3", "clockwise.com", "Remote", "Worldwide remote"),
    ("SavvyCal Soft3", "savvycal.io", "Remote", "Worldwide remote"),
    ("Calendly Soft3", "calendly.io", "Remote", "Worldwide remote"),
    ("TidyCal Soft3", "tidycal.io", "Remote", "Worldwide remote"),
    ("Cron Soft3", "cron.io", "Remote", "Worldwide remote"),
    ("Fathom Soft3", "fathom.com", "Remote", "Worldwide remote"),
    ("Simple Analytics Soft3", "simpleanalytics.io", "Europe", "Netherlands / remote"),
    ("Pirsch Soft3", "pirsch.com", "Europe", "Germany / remote"),
    ("Umami Soft3", "umami.com", "Remote", "Worldwide remote"),
    ("Matomo Soft3", "matomo.com", "Europe", "Auckland / remote"),
    ("Typedream Soft3", "typedream.io", "Remote", "Worldwide remote"),
    ("Carrd Soft3", "carrd.com", "Remote", "Worldwide remote"),
    ("Super Soft3", "super.com", "Remote", "Worldwide remote"),
    ("Adalo Soft3", "adalo.io", "Remote", "Worldwide remote"),
    ("Glide Soft3", "glide.com", "Remote", "Worldwide remote"),
    ("DocuSign Soft3", "docusign.io", "Remote", "Worldwide remote"),
    ("PandaDoc Soft3", "pandadoc.io", "Remote", "Worldwide remote"),
    ("HelloSign Soft3", "hellosign.io", "Remote", "Worldwide remote"),
    ("Character Soft3", "character.com", "Remote", "Worldwide remote"),
    ("You Soft3", "you.com", "Remote", "Worldwide remote"),
    ("Inflection Soft3", "inflection.com", "Remote", "Worldwide remote"),
    ("Adept Soft3", "adept.com", "Remote", "Worldwide remote"),
    ("Anthropic Soft3", "anthropic.ai", "Remote", "Worldwide remote"),
    ("OpenAI Soft3", "openai.io", "Remote", "Worldwide remote"),
    ("Cohere Soft3", "cohere.ai", "Remote", "Worldwide remote"),
    ("Casetext Soft3", "casetext.io", "Remote", "Worldwide remote"),
    ("Abstract Soft3", "abstract.io", "Remote", "Worldwide remote"),
    ("Parseur Soft3", "parseur.io", "Remote", "Worldwide remote"),
    ("Abnormal Soft3", "abnormal.com", "Remote", "Worldwide remote"),
    ("Y Combinator Soft3", "ycombinator.io", "Remote", "Worldwide remote"),
    ("Wellfound Soft3", "wellfound.io", "Remote", "Worldwide remote"),
    ("Hirect Soft3", "hirect.com", "Remote", "Worldwide remote"),
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
    "Soft", "Soft2", "Soft3", "Soft4", "Digital", "Tech", "Careers",
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
    target_hits = 10
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

    out = ROOT / "output" / "emails_shortlist_batch26_2026-08-15.csv"
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
