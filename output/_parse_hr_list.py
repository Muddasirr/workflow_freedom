#!/usr/bin/env python3
"""Parse user HR list, SMTP-verify unpublished leftovers, write send CSV."""
from __future__ import annotations

import csv
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "outreach"))

from send_emails import (  # noqa: E402
    BLOCKED_COMPANIES,
    BLOCKED_DOMAINS,
    SKIP_LOCAL,
    already_sent,
)
from smtp_verify import bounced_emails, verify_mailbox  # noqa: E402

RAW = """
i2c	careers@i2cinc.com
netsol	amir.raza@netsoltech.com
devsinc	muhammadusmanaslam@hotmail.com
10Pearls	anus.intizar@10pearls.com
Systems	syedhashirshahgillani@gmail.com
Ovex Technologies	asyed@ovextech.com
TechAbout	careers@techabout.com
Digital Dividend	Career@Digital-Dividend.com
ZAPTA Technologies	𝐚𝐲𝐞𝐬𝐡𝐚.𝐜𝐚𝐫𝐞𝐞𝐫@𝐳𝐚𝐩𝐭𝐚𝐭𝐞𝐜𝐡.𝐜𝐨𝐦
AppsNation Karachi	jobs@appsnation.co
Contour Software	amna.ahsan@contour-software.com
Devsort	hr@devsort.net
Phaedra Solutions	careers@phaedrasolutions.com
Brainx	careers@brainxtech.com
ConsoleDot	𝐳𝐞𝐞𝐬𝐡𝐚𝐧.𝐡𝐫𝟎𝟎𝟏𝟐@𝐜𝐨𝐧𝐬𝐨𝐥𝐞𝐝𝐨𝐭.𝐜𝐨𝐦
Bizzclan	hr@bizzclan.com
Alfatah	basit.ali@alfatah.com.pk
Rendream	careers@rendream.work
COTHM	admin.jt@cothm.edu.pk
Tekboox	saddam.hussain@tekboox.com
Optlinkhub	tayyaba@optlinkhub.com
Millennium Nexus	mariyam@msd-my.com
Solutioninn	mahrukh@solutioninn.com
tecspine	hr@tecspine.com
iifatech	hr@iifatech.com
codingcops	iqra.arshad@codingcops.com
dinindustries	hrdpl@dinindustries.com
adamjeeinsurance	recruitment@adamjeeinsurance.com
pikessoft	hr@pikessoft.com
xpertprime	careers@xpertprime.com
conversotech	mehru@conversotech.com
dubizzlelabs	mehran.butt@dubizzlelabs.com
crescentcorporation	hr@crescentcorporation.com.pk
devexcelit	hr@devexcelit.com
infotechgroup	careers@infotechgroup.com
pakqatar	recruitment@pakqatar.com.pk
wistech	people@wistech.biz
shaukatkhanum	careers@shaukatkhanum.org.pk
tekhqs	asma.noor@tekhqs.com
sysvoy	hr@sysvoy.com
bjssoftsolutions	Contact@bjssoftsolutions.com
purelogics	careers@purelogics.com
spadasoft	careers@spadasoft.com
ittehadchemicals	hr@ittehadchemicals.com
novatoresols	Talent@novatoresols.com
gamedistrict	hassanmahmood@gamedistrict.co
suzukicanal	sohail@suzukicanal.com.pk
360solutions	careers@360solutions.dev
hytgenx	careers@hytgenx.com
codexiatech	careers@codexiatech.com
focusteck	careers@focusteck.com
zaptatech	hr@zaptatech.com
ozipub	careers@ozipub.io
nxb	𝐤𝐚𝐢𝐧𝐚𝐭.𝐚𝐥𝐢@𝐧𝐱𝐛.𝐜𝐨𝐦.𝐩𝐤
viralsquare	careers@viralsquare.org
phishrod	maha.nadeem@phishrod.co
codeupscale	zafar.hayat@codeupscale.com
transcure	Hr@transcure.net
optimumhrc	jahanzab@optimumhrc.com
ititans	careers@ititans.com
kualitatem	jobs@kualitatem.com
byd-mega	talent@byd-mega.com
master	habibullah.hr@master.com.pk
abendsoft	hr@abendsoft.com
techverx	shahzaib.mushtaq@techverx.com
hrways	jobs@hrways.co
binarybrix	hr@binarybrix.com
itroadway	bilal.waheed@itroadway.com
glixentech	hr@glixentech.com
faisaltown	careers@faisaltown.com.pk
onemachinesoftware	recruitment@onemachinesoftware.com
euphoriaxr	career@euphoriaxr.com
xevensolutions	hr@xevensolutions.com
optimageeks	amna.zia@optimageeks.com
softpyramid	hr@softpyramid.com
almarah	careers@almarah.org
pinnacloid	ayesha.shahzad@pinnacloid.com
geekybugs	careers@geekybugs.com
boolmind	sara.chishti@boolmind.com
agilekode	hr@agilekode.com
nexskill	Talenthunt@nexskill.com
bkstack	hr@bkstack.com
kualitatem named	Danya.sardar@kualitatem.com
clarisync	career@clarisync.com
sixlogics	hr@sixlogics.com
ahlogistic	hre01.ho.lhr@ahlogistic.com.pk
bnu	career@bnu.edu.pk
abark	hr@abark.pk
macrosoftinc	shahmin@macrosoftinc.com
ablfunds	career@ablfunds.com
reporteq	nabeeha@reporteq.com
climatesolutions	hr@climatesolutions.com.pk
smth	hr@smth.pk
consforc	careers@consforc.com
staffasia	career@staffasia.org
zanda	careers@zanda.pk
brainyhrs	shahbaz@brainyhrs.com
optimumhrc jobs	jobs@optimumhrc.com
arhumanc	hr@arhumanc.co
ortakconsultants	careers@ortakconsultants.com
exdnow	hamza.hassan@exdnow.com
firstfmg	career@firstfmg.co
toyotawalton	hr@toyotawalton.com
synavos	𝐜𝐚𝐫𝐞𝐞𝐫𝐬@𝐬𝐲𝐧𝐚𝐯𝐨𝐬.𝐜𝐨𝐦
primasystems	careers@primasystems.net
vertexitsol	saad.qaisar@vertexitsol.com
touchstoneintl	ameer.hamza@touchstoneintl.com
clikiin	careers@clikiin.com
technstack	careers@technstack.com
alliedpetroleum	jobs@alliedpetroleum.com.pk
bdasol	maria@bdasol.com
proskillshr	careers@proskillshr.com
pk.see	careers@pk.see.biz
"""

SKIP_EXTRA = {"support", "admin.jt"}
PERSONAL = {"gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "icloud.com"}


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s).strip().lower()


def main() -> None:
    sent_e, sent_c = already_sent()
    sent_d = {e.split("@", 1)[1] for e in sent_e if "@" in e}
    bounced = bounced_emails()
    seen_e: set[str] = set()
    seen_c: set[str] = set()
    seen_d: set[str] = set()
    rows: list[dict[str, str]] = []
    skipped = []

    for line in RAW.strip().splitlines():
        if "\t" not in line:
            continue
        company, email = line.split("\t", 1)
        company = company.strip()
        email = norm(email)
        company_key = company.lower()
        if "@" not in email:
            skipped.append((company, email, "no email"))
            continue
        local, _, domain = email.partition("@")
        if local in SKIP_LOCAL or local in SKIP_EXTRA:
            skipped.append((company, email, "junk local"))
            continue
        if domain in PERSONAL:
            skipped.append((company, email, "personal mailbox"))
            continue
        if domain in BLOCKED_DOMAINS:
            skipped.append((company, email, "blocked domain"))
            continue
        if any(b == company_key or b in company_key for b in BLOCKED_COMPANIES):
            skipped.append((company, email, "blocked company"))
            continue
        if email in sent_e or email in bounced or email in seen_e:
            skipped.append((company, email, "already sent/seen email"))
            continue
        if company_key in sent_c or company_key in seen_c:
            skipped.append((company, email, "already sent/seen company"))
            continue
        if domain in sent_d or domain in seen_d:
            skipped.append((company, email, "already sent/seen domain"))
            continue
        seen_e.add(email)
        seen_c.add(company_key)
        seen_d.add(domain)
        rows.append(
            {
                "Company": company,
                "Region": "Pakistan",
                "City": "",
                "HR / Recruiter Email": email,
                "Email Source": "known company contact",
                "Other Emails": "",
                "Domain": domain,
                "Careers / Apply URL": "",
                "Sample Role": "",
                "Location Clause": "",
                "Letter": "",
                "SMTP Verification": "",
            }
        )

    print(f"unique new to probe: {len(rows)}", flush=True)
    ready = []
    for r in rows:
        email = r["HR / Recruiter Email"]
        ok, detail = verify_mailbox(email)
        r["SMTP Verification"] = (detail or "")[:400]
        print(f"  SMTP {'OK' if ok else 'NO '} {email:48} {r['Company'][:22]:22} {detail[:70]}", flush=True)
        if ok:
            ready.append(r)

    out = ROOT / "output" / "emails_user_hr_2026-08-19.csv"
    fields = list(ready[0].keys()) if ready else [
        "Company", "Region", "City", "HR / Recruiter Email", "Email Source",
        "Other Emails", "Domain", "Careers / Apply URL", "Sample Role",
        "Location Clause", "Letter", "SMTP Verification",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as h:
        w = csv.DictWriter(h, fieldnames=fields)
        w.writeheader()
        w.writerows(ready)
    print(f"READY {len(ready)} -> {out}", flush=True)
    for r in ready:
        print(f"  SENDABLE {r['HR / Recruiter Email']} ({r['Company']})", flush=True)
    print("skipped", len(skipped), flush=True)


if __name__ == "__main__":
    main()
