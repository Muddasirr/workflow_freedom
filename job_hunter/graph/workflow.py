"""LangGraph apply agent.

find posting → find published email → SMTP-validate → personalized letter → send
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from job_hunter.graph.nodes import (
    deliver,
    find_email,
    find_jobs,
    pick_job,
    route_email,
    route_pick,
    route_validate,
    skip,
    validate_email,
    write_letter,
)
from job_hunter.graph.state import GraphState


def build_apply_graph():
    graph = StateGraph(GraphState)
    graph.add_node("find_jobs", find_jobs)
    graph.add_node("pick_job", pick_job)
    graph.add_node("find_email", find_email)
    graph.add_node("validate_email", validate_email)
    graph.add_node("write_letter", write_letter)
    graph.add_node("deliver", deliver)
    graph.add_node("skip", skip)

    graph.add_edge(START, "find_jobs")
    graph.add_edge("find_jobs", "pick_job")
    graph.add_conditional_edges(
        "pick_job",
        route_pick,
        {"find_email": "find_email", "done": END},
    )
    graph.add_conditional_edges(
        "find_email",
        route_email,
        {"validate_email": "validate_email", "skip": "skip"},
    )
    graph.add_conditional_edges(
        "validate_email",
        route_validate,
        {"write_letter": "write_letter", "skip": "skip"},
    )
    graph.add_edge("write_letter", "deliver")
    graph.add_edge("deliver", "pick_job")
    graph.add_edge("skip", "pick_job")
    return graph.compile()


def run_apply_graph(
    *,
    send: bool = False,
    limit: int = 8,
    delay: float = 90.0,
    daily_cap: int = 80,
    no_agent: bool = False,
) -> GraphState:
    lock = None
    if send:
        import sys

        from job_hunter.config import ROOT

        if str(ROOT / "outreach") not in sys.path:
            sys.path.insert(0, str(ROOT / "outreach"))
        from send_emails import acquire_lock

        lock = acquire_lock()
    try:
        app = build_apply_graph()
        initial: GraphState = {
            "send": send,
            "limit": limit,
            "delay": delay,
            "daily_cap": daily_cap,
            "no_agent": no_agent,
            "jobs": [],
            "index": 0,
            "current": {},
            "sent_count": 0,
            "skipped": [],
            "results": [],
            "log": [],
            "done": False,
            "lookups": 0,
        }
        final = app.invoke(initial, {"recursion_limit": 800})
        results = final.get("results") or []
        sent = [r for r in results if r.get("status") in {"sent", "dry-run"}]
        skipped = [r for r in results if r.get("status") not in {"sent", "dry-run"}]
        print()
        print(f"Walked {len(results)} companies")
        print(f"  Ready/sent: {len(sent)}")
        print(f"  Skipped:    {len(skipped)}")
        for row in sent:
            print(
                f"  {row.get('status'):8}  {row.get('email')}  {row.get('company')}  "
                f"{row.get('title')}  [{row.get('letter_kind')}]"
            )
        return final
    finally:
        if lock is not None:
            lock.close()
