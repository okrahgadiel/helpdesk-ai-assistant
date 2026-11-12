"""CLI.
  python -m helpdesk ask "I'm locked out of my account"
  python -m helpdesk triage "the whole floor lost wifi"
  python -m helpdesk eval
  python -m helpdesk serve --port 8000
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="helpdesk", description="IT helpdesk AI assistant")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_ask = sub.add_parser("ask", help="Answer a question from the knowledge base")
    p_ask.add_argument("question")
    p_ask.add_argument("--json", action="store_true")
    p_tri = sub.add_parser("triage", help="Classify a ticket's category and priority")
    p_tri.add_argument("text")
    sub.add_parser("eval", help="Run the offline evaluation suite")
    p_srv = sub.add_parser("serve", help="Start the web chat UI")
    p_srv.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)

    if args.cmd == "eval":
        from .evaluate import evaluate
        evaluate()
        return 0
    if args.cmd == "serve":
        from .server import serve
        serve(args.port)
        return 0

    from .assistant import HelpdeskAssistant
    bot = HelpdeskAssistant()
    if args.cmd == "triage":
        print(json.dumps(asdict(bot.triager.triage(args.text)), indent=2))
        return 0
    ans = bot.ask(args.question)
    if args.json:
        print(json.dumps(ans.to_dict(), indent=2))
    else:
        print(ans.answer)
        if ans.sources:
            print("\nSources:\n  " + "\n  ".join(ans.sources))
        print(f"\n[mode={ans.mode} grounded={ans.grounded} triage={ans.triage['category']}/{ans.triage['priority']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
