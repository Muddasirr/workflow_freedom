#!/usr/bin/env python3
"""Overlay new skills + Codet bullets onto the original Canva resume."""
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "MuddasirRizwan_Resume.pdf.pdf"
OUT = ROOT / "MuddasirRizwan_Resume.pdf"

pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

W, H = 595.5, 842.25
INK = Color(30 / 255, 30 / 255, 30 / 255)


def hy(y: float) -> float:
    """pdftotext bbox y (top-origin) -> PDF y (bottom-origin)."""
    return H - y


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = w if not cur else f"{cur} {w}"
        if pdfmetrics.stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def main() -> None:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))

    # Cover skills body + Codet bullets (keep section titles / company / dates)
    c.setFillColor(white)
    c.rect(20, hy(191), 560, hy(132) - hy(191), fill=1, stroke=0)
    c.rect(20, hy(392.5), 560, hy(251.5) - hy(392.5), fill=1, stroke=0)

    # --- skills ---
    c.setFillColor(INK)
    size = 9.6
    leading = 12.6
    y = hy(148.6)  # baseline near original Languages line
    skills = [
        ("Languages: ", "TypeScript, Python, Java, SQL, JavaScript (ES6+)"),
        (
            "Frameworks & Libraries: ",
            "LangGraph, LangChain, Node.js, FastAPI, React.js, Next.js, Redux, Jest",
        ),
        (
            "Tools & Technologies: ",
            "Kubernetes, GCP (GCS, Pub/Sub, Cloud Tasks), YugabyteDB, Prometheus, Docker, gRPC, Git",
        ),
    ]
    x0, max_w = 21.8, 548
    for label, rest in skills:
        c.setFont("DejaVuBold", size)
        c.drawString(x0, y, label)
        lw = pdfmetrics.stringWidth(label, "DejaVuBold", size)
        c.setFont("DejaVu", size)
        lines = wrap(rest, "DejaVu", size, max_w - lw)
        c.drawString(x0 + lw, y, lines[0])
        for extra in lines[1:]:
            y -= leading
            c.drawString(x0, y, extra)
        y -= leading

    # --- Codet bullets ---
    bullets = [
        "Designed AutoCloudEngineerAgent, a LangGraph control plane that proposes safe infra configs, deploys them only to a Kubernetes canary cell, then rejects, rolls back, or recommends promotion.",
        "Built the optimizer with a Gaussian-process ensemble (GP-UCB, trust-region leash) and BO-ICL as an advisory LLM surrogate that cannot override hard safety or isolation constraints.",
        "Persisted campaign/trial evidence in YugabyteDB (YSQL); stored artifacts in GCS; collected telemetry with Prometheus / Cloud Monitoring.",
        "Wired canary lifecycle via the Kubernetes API and gRPC: deploy, warm pools, invariant benchmarks, rollback on failure, approval before production.",
        "Used TypeScript, LangChain, GCP Pub/Sub & Cloud Tasks, and multi-runtime providers; treated IAM, encryption, and tenant isolation as immutable optimizer inputs.",
        "Also shipped the no-code product: dynamic database module, trigger-condition-action workflows, and AI-assisted predictions (React/Next.js UI).",
    ]
    bx, bsize, blead = 38.8, 9.5, 11.2
    max_bw = 530
    y = hy(267.3)
    for b in bullets:
        c.setFont("DejaVu", 8)
        c.drawString(28.5, y + 1, "•")
        c.setFont("DejaVu", bsize)
        lines = wrap(b, "DejaVu", bsize, max_bw)
        c.drawString(bx, y, lines[0])
        for extra in lines[1:]:
            y -= blead
            c.drawString(bx, y, extra)
        y -= blead + 0.8

    c.save()
    buf.seek(0)

    base = PdfReader(str(SRC))
    overlay = PdfReader(buf)
    page = base.pages[0]
    page.merge_page(overlay.pages[0])
    writer = PdfWriter()
    writer.add_page(page)
    if base.metadata:
        writer.add_metadata(base.metadata)
    with OUT.open("wb") as f:
        writer.write(f)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
