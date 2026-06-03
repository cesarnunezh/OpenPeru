"""
Visual testing script for bill differences.

Reads from the processed DB's bill_differences table:
    python scripts/show_diff.py <bill_id> --list
    python scripts/show_diff.py <bill_id> --step <step_id>

Options:
    --max-lines N     Max diff lines to show (default: 60)
    --snippet N       Chars of each version text to preview (default: 400)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.config import settings
from backend.database.crud.pipeline_bills import get_billtext_for_step
from backend.database.models import Bill, BillDifference, BillStep

GREEN = "\033[92m"
RED = "\033[91m"
GREY = "\033[90m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"
WIDTH = 88


def hr(char="─"):
    print(char * WIDTH)


def section(title):
    print(f"\n{BOLD}{CYAN}{title}{RESET}")
    hr()


# Kept in sync with ``app/diff_render._join_tokens``.
_OPEN_BRACKETS = frozenset("([{¿¡")
_AMBIGUOUS_QUOTES = frozenset("\"'")


def _join_tokens(tokens: list[str]) -> str:
    out: list[str] = []
    pending_open = False
    inside_quote: dict[str, bool] = {}
    for t in tokens:
        if not t:
            continue
        if t in _OPEN_BRACKETS:
            if out and not pending_open:
                out.append(" ")
            out.append(t)
            pending_open = True
            continue
        if t in _AMBIGUOUS_QUOTES:
            if not inside_quote.get(t, False):
                if out and not pending_open:
                    out.append(" ")
                out.append(t)
                pending_open = True
                inside_quote[t] = True
            else:
                out.append(t)
                pending_open = False
                inside_quote[t] = False
            continue
        if not t[0].isalnum():
            out.append(t)
            pending_open = False
            continue
        if out and not pending_open:
            out.append(" ")
        out.append(t)
        pending_open = False
    return "".join(out).lstrip()


def _render_word_diff(runs: list[dict]) -> str:
    parts: list[str] = []
    for run in runs:
        op = run["op"]
        if op == "equal":
            parts.append(_join_tokens(run["a_tokens"]))
        elif op == "delete":
            parts.append(f"{RED}[-{_join_tokens(run['a_tokens'])}-]{RESET}")
        elif op == "insert":
            parts.append(f"{GREEN}{{+{_join_tokens(run['b_tokens'])}+}}{RESET}")
        elif op == "replace":
            parts.append(f"{RED}[-{_join_tokens(run['a_tokens'])}-]{RESET}")
            parts.append(f"{GREEN}{{+{_join_tokens(run['b_tokens'])}+}}{RESET}")
    return " ".join(p for p in parts if p)


def render_structured_diff(payload: dict, max_lines: int) -> None:
    summary = payload.get("summary", {})
    print(
        f"  {GREY}parser_version={payload.get('parser_version', '?')}  "
        f"nodes_total={summary.get('nodes_total', 0)}  "
        f"changed={summary.get('nodes_changed', 0)}  "
        f"inserted={summary.get('nodes_inserted', 0)}  "
        f"deleted={summary.get('nodes_deleted', 0)}  "
        f"renamed={summary.get('nodes_renamed', 0)}{RESET}"
    )
    shown = 0
    for node in payload.get("nodes", []):
        status = node["status"]
        if not node["hunks"] and status == "matched":
            continue
        status_colour = {
            "matched": CYAN,
            "inserted": GREEN,
            "deleted": RED,
        }.get(status, GREY)
        label = node.get("b_label") or node.get("a_label") or node["node_id"]
        print(
            f"\n  {BOLD}{status_colour}[{status}/{node['match_strategy']}]{RESET} "
            f"{BOLD}{node['node_id']}{RESET}  {GREY}{label}{RESET}"
        )
        for hunk in node["hunks"]:
            op = hunk["op"]
            tag_colour = {"insert": GREEN, "delete": RED, "replace": YELLOW}.get(
                op, GREY
            )
            print(
                f"    {tag_colour}{op}{RESET}  "
                f"a[{hunk['a_start']}:{hunk['a_end']}] → b[{hunk['b_start']}:{hunk['b_end']}]"
            )
            for run_text in _hunk_lines(hunk):
                print(f"      {run_text}")
                shown += 1
                if shown >= max_lines:
                    print(
                        f"\n{YELLOW}  … output truncated at {max_lines} lines "
                        f"(use --max-lines N){RESET}"
                    )
                    return


def _hunk_lines(hunk: dict) -> list[str]:
    word_runs = hunk.get("word_diff") or []
    if word_runs:
        return [_render_word_diff(word_runs)]
    if hunk["op"] == "insert":
        return [f"{GREEN}+ {hunk['b_text']}{RESET}"]
    if hunk["op"] == "delete":
        return [f"{RED}- {hunk['a_text']}{RESET}"]
    return [
        f"{RED}- {hunk['a_text']}{RESET}",
        f"{GREEN}+ {hunk['b_text']}{RESET}",
    ]


def _text_snippet(t: str | None, n: int) -> str:
    if t is None:
        return f"{GREY}(none){RESET}"
    body = t[:n].replace("\n", "\n    ")
    suffix = f"{GREY}…{RESET}" if len(t) > n else ""
    return f"    {body}{suffix}"


def processed_list(db, bill):
    steps = (
        db.execute(
            select(BillStep)
            .where(BillStep.bill_id == bill.id)
            .order_by(BillStep.step_date.asc())
        )
        .scalars()
        .all()
    )

    if not steps:
        print(f"{YELLOW}No steps found.{RESET}")
        return

    section(f"Steps for {bill.id} ({len(steps)} total)")
    for step in steps:
        diff = db.get(BillDifference, (bill.id, step.step_id))
        dtype = diff.difference_type if diff else "no diff row"
        colour = {
            "modified": GREEN,
            "first_version": YELLOW,
            "no_change": GREY,
            "unavailable": RED,
            "incomparable": YELLOW,
        }.get(dtype, GREY)
        date_str = step.step_date if step.step_date else "—"
        print(
            f"  {BOLD}{step.step_id:<10}{RESET} {date_str}  {str(step.step_type):<40} {colour}{dtype}{RESET}"
        )


def processed_step(db, bill, step_id: int, max_lines: int, snippet: int):
    step = db.get(BillStep, (bill.id, step_id))
    if not step:
        print(f"{RED}Step {step_id} not found for bill {bill.id}{RESET}")
        return

    diff = db.get(BillDifference, (bill.id, step_id))
    section(
        f"Step {step_id}  ·  {step.step_type}  ·  {step.step_date if step.step_date else '—'}"
    )

    if not diff:
        print(f"{YELLOW}No BillDifference row — run the pipeline first.{RESET}")
        return

    dtype = diff.difference_type
    label = {
        "first_version": f"{YELLOW}FIRST VERSION{RESET}",
        "no_change": f"{GREY}NO CHANGE{RESET}",
        "unavailable": f"{RED}UNAVAILABLE{RESET}",
        "incomparable": f"{YELLOW}INCOMPARABLE (size ratio too large){RESET}",
        "modified": f"{GREEN}MODIFIED{RESET}",
    }.get(dtype, dtype)
    print(
        f"  type={label}  prev_step={diff.prev_step_id if diff.prev_step_id is not None else '—'}"
    )

    new_bt = get_billtext_for_step(db, bill.id, step_id)
    new_text = new_bt.text if new_bt else None
    old_text = None
    if diff.prev_step_id is not None:
        old_bt = get_billtext_for_step(db, bill.id, diff.prev_step_id)
        old_text = old_bt.text if old_bt else None

    print(
        f"\n  {BOLD}VERSION 1:{RESET} {'—' if old_text is None else f'{len(old_text)} chars'}"
    )
    print(_text_snippet(old_text, snippet))
    print(
        f"\n  {BOLD}VERSION 2:{RESET} {'—' if new_text is None else f'{len(new_text)} chars'}"
    )
    print(_text_snippet(new_text, snippet))

    if diff.difference_content:
        payload = json.loads(diff.difference_content)
        print(f"\n  {BOLD}DIFF (structured):{RESET}")
        hr("·")
        render_structured_diff(payload, max_lines)
        hr("·")
    else:
        print(f"\n  {GREY}(no diff content — type is {dtype}){RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Visual testing for bill diffs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("bill_id", help="Bill ID (e.g. 2021_2907)")
    parser.add_argument("--step", type=int, metavar="STEP_ID")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--max-lines", type=int, default=60, metavar="N")
    parser.add_argument(
        "--snippet",
        type=int,
        default=400,
        metavar="N",
        help="Chars of text to preview per version (default: 400)",
    )
    args = parser.parse_args()

    engine = create_engine(settings.DB_URL)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        bill = db.get(Bill, args.bill_id)
        if not bill:
            print(f"{RED}Bill '{args.bill_id}' not found.{RESET}")
            sys.exit(1)

        hr("═")
        print(f"{BOLD}BILL {bill.id}{RESET}  ·  {bill.title}")
        print(f"Status : {bill.status}")
        hr("═")

        if args.list or not args.step:
            processed_list(db, bill)
            if not args.step:
                print(f"\n{GREY}Tip: --step <ID> to inspect a diff.{RESET}\n")
                return
        if args.step:
            processed_step(db, bill, args.step, args.max_lines, args.snippet)

    print()


if __name__ == "__main__":
    main()
