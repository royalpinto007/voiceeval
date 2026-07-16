"""Scoring and regression diff.

A single pass/fail per call tells you nothing on the day a prompt change makes things 5% worse.
What you need is the same suite, scored the same way, diffed against the last version. That turns
"it feels worse" into "these two calls regressed, here is how".
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .checks import analyse
from .turns import Interaction

_WEIGHT = {"high": 1.0, "medium": 0.4, "low": 0.1}


@dataclass
class Score:
    interaction_id: str
    passed: bool
    penalty: float
    findings: list[dict] = field(default_factory=list)


@dataclass
class SuiteResult:
    label: str
    scores: list[Score]

    @property
    def pass_rate(self) -> float:
        return sum(1 for s in self.scores if s.passed) / len(self.scores) if self.scores else 0.0

    def to_json(self) -> str:
        return json.dumps({"label": self.label, "scores": [asdict(s) for s in self.scores]}, indent=2)


def score(inter: Interaction) -> Score:
    findings = analyse(inter)
    penalty = sum(_WEIGHT.get(f.severity, 0) for f in findings)
    # A call fails if anything high fired. High severity means money moved wrongly, the agent acted
    # blind, or policy was broken. There is no partial credit for those.
    passed = not any(f.severity == "high" for f in findings)
    return Score(
        interaction_id=inter.id,
        passed=passed,
        penalty=round(penalty, 2),
        findings=[asdict(f) for f in findings],
    )


def run_suite(interactions: list[Interaction], label: str = "current") -> SuiteResult:
    return SuiteResult(label=label, scores=[score(i) for i in interactions])


def diff(before: SuiteResult, after: SuiteResult) -> dict:
    """What changed between two versions of the same suite.

    Regressions are the headline. A prompt tweak that fixes one call and breaks two is a net loss,
    and an aggregate pass-rate can hide that entirely.
    """
    b = {s.interaction_id: s for s in before.scores}
    a = {s.interaction_id: s for s in after.scores}

    regressed, fixed, changed = [], [], []
    for k in sorted(set(b) & set(a)):
        if b[k].passed and not a[k].passed:
            regressed.append(k)
        elif not b[k].passed and a[k].passed:
            fixed.append(k)
        elif abs(a[k].penalty - b[k].penalty) > 0.01:
            changed.append({"id": k, "before": b[k].penalty, "after": a[k].penalty})

    return {
        "regressed": regressed,
        "fixed": fixed,
        "penalty_changed": changed,
        "pass_rate_before": round(before.pass_rate, 3),
        "pass_rate_after": round(after.pass_rate, 3),
        "verdict": "REGRESSION" if regressed else ("IMPROVED" if fixed else "NO CHANGE"),
    }


def load_result(path: str | Path) -> SuiteResult:
    d = json.loads(Path(path).read_text())
    return SuiteResult(label=d["label"], scores=[Score(**s) for s in d["scores"]])
