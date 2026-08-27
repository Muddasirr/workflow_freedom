from __future__ import annotations

import argparse

from job_hunter.graph.workflow import run_apply_graph


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LangGraph apply agent: job posting → published email → SMTP → personalized letter."
    )
    parser.add_argument("--send", action="store_true", help="Actually send. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=8, help="Max companies to send/preview.")
    parser.add_argument("--delay", type=float, default=90.0, help="Seconds between sends.")
    parser.add_argument("--daily-cap", type=int, default=80, help="Max sends per UTC day.")
    parser.add_argument("--no-agent", action="store_true", help="Use templates instead of Cursor letters.")
    args = parser.parse_args()
    run_apply_graph(
        send=args.send,
        limit=args.limit,
        delay=args.delay,
        daily_cap=args.daily_cap,
        no_agent=args.no_agent,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
