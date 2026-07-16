"""voiceeval CLI.

    voiceeval check fixtures/*.json           # what went wrong
    voiceeval run fixtures/*.json -o v1.json  # score a suite, save it
    voiceeval diff v1.json v2.json            # did the prompt change make it worse
"""

from __future__ import annotations

import argparse
import glob
import sys

from rich.console import Console

from .checks import analyse
from .score import diff, load_result, run_suite
from .turns import load

console = Console()
_COLOUR = {"high": "red", "medium": "yellow", "low": "dim"}


def _expand(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        out.extend(sorted(glob.glob(p)) or [p])
    return out


def cmd_check(args) -> int:
    files = _expand(args.files)
    failed = 0
    for f in files:
        inter = load(f)
        findings = analyse(inter)
        status = "[green]PASS[/]" if not any(x.severity == "high" for x in findings) else "[red]FAIL[/]"
        if any(x.severity == "high" for x in findings):
            failed += 1
        console.print(f"\n{status} [bold]{inter.id}[/] [dim]({inter.duration_s:.0f}s call)[/]")
        for x in findings:
            where = f" [dim]turn {x.turn_index}[/]" if x.turn_index is not None else ""
            console.print(f"  [{_COLOUR.get(x.severity,'white')}]{x.severity:<6}[/] [bold]{x.check}[/]{where}")
            console.print(f"         {x.message}")
        if not findings:
            console.print("  [dim]no findings[/]")
    console.print(f"\n[bold]{len(files)-failed}/{len(files)}[/] calls passed")
    return 1 if (failed and args.strict) else 0


def cmd_run(args) -> int:
    files = _expand(args.files)
    result = run_suite([load(f) for f in files], label=args.label)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(result.to_json())
        console.print(f"wrote [bold]{args.out}[/] ({len(result.scores)} calls, pass rate {result.pass_rate:.0%})")
    else:
        print(result.to_json())
    return 0


def cmd_diff(args) -> int:
    d = diff(load_result(args.before), load_result(args.after))
    colour = {"REGRESSION": "red", "IMPROVED": "green", "NO CHANGE": "dim"}[d["verdict"]]
    console.print(f"[{colour}][bold]{d['verdict']}[/][/]")
    console.print(f"  pass rate: {d['pass_rate_before']:.0%} -> {d['pass_rate_after']:.0%}")
    if d["regressed"]:
        console.print(f"  [red]regressed:[/] {', '.join(d['regressed'])}")
    if d["fixed"]:
        console.print(f"  [green]fixed:[/] {', '.join(d['fixed'])}")
    for c in d["penalty_changed"]:
        console.print(f"  [dim]{c['id']}: penalty {c['before']} -> {c['after']}[/]")
    return 1 if (d["regressed"] and args.strict) else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="voiceeval", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="show findings for calls")
    c.add_argument("files", nargs="+")
    c.add_argument("--strict", action="store_true", help="exit 1 if any call fails")
    c.set_defaults(func=cmd_check)

    r = sub.add_parser("run", help="score a suite")
    r.add_argument("files", nargs="+")
    r.add_argument("-o", "--out")
    r.add_argument("--label", default="current")
    r.set_defaults(func=cmd_run)

    d = sub.add_parser("diff", help="compare two suite runs")
    d.add_argument("before")
    d.add_argument("after")
    d.add_argument("--strict", action="store_true")
    d.set_defaults(func=cmd_diff)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
