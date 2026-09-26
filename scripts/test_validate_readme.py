#!/usr/bin/env python3
"""Mutation-test validate_readme.py.

A validator that cannot fail is not a check. This introduces one deliberate
defect at a time into material that currently passes and asserts that the
validator rejects it - by the *specific* check that ought to catch it, not
merely that something failed. Asserting only "the run went red" would let a
defect be caught by an unrelated check while the one that should catch it sat
there dead, which is how the original seven dead checks survived.

Two classes of seed, because two different things can be wrong:

  README mutations        a defect in the page. 36 seeds.
  Ground-truth mutations  a defect in the validator's own dated snapshot. No
                          README edit can test these, because they compare
                          FACTS against FACTS and against the internal ledger.
                          This class is the only thing that exercises
                          bucket-split, arith-authored, arith-merges, arith-own
                          and pr-listed.

Eight checks had no seed at all when this was measured, and four of them were
the arithmetic guards over the headline numbers. That is the gap worth closing:
a check with no seed cannot be shown to work, and a check that cannot be shown
to work is the same problem one level up. The suite therefore fails if any
check the validator can emit is neither seeded here nor listed in NETWORK_ONLY.

Network-dependent checks are verified separately, by seeding a real badge
endpoint that answers HTTP 200 with an error body into a passing README.

Run:  python scripts/test_validate_readme.py [path/to/README.md]
Exit: 0 only if every mutation was caught by its expected check, the control
      still passes, and no check is left without a seed.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VALIDATOR = os.path.join(HERE, "validate_readme.py")
TARGET = sys.argv[1] if len(sys.argv) > 1 else "README.md"
BASE = open(TARGET, encoding="utf-8").read()
MUTFILE = os.path.join(tempfile.gettempdir(), "readme-mutation.md")
TRUTHDIR = os.path.join(tempfile.gettempdir(), "readme-truthcheck")
VALSRC = open(VALIDATOR, encoding="utf-8").read()


def add(text):
    return lambda s: s + text


# ── class 1: defects in the page ──────────────────────────────────────────────
# (name, mutation, check that must catch it)
def _move_merged_under_open(s):
    """Relocate a merged pull request into the open section, leaving the sums
    intact. Every count still adds up and the inventory still matches, so only a
    check that reads which section a PR sits in can notice."""
    lines = s.split("\n")
    moved = next(i for i, l in enumerate(lines)
                 if "sympy/sympy/pull/30567" in l)
    entry = lines.pop(moved)
    entry = entry.replace("- **SymPy", "- **SymPy (merged, misplaced)", 1)
    at = next(i for i, l in enumerate(lines) if l.startswith("### ") and "Open" in l)
    lines.insert(at + 1, entry)
    return "\n".join(lines)


MUT=[
 # --- the round-3 findings, as regression guards ---
 ("D1 auto-close error returns", lambda s:s.replace("A GitHub Actions workflow in the pandas repo (`github-actions[bot]`) auto-closed this one 14 seconds after it opened","was closed in favour of the live #69429",1), 'banned-string'),
 ("D1 wording 'in its favour'",   add("\nclosed in its favour\n"), 'banned-string'),
 ("D2 190 own-PRs returns",       lambda s:s.replace("Of the 189 pull requests","Of the 190 pull requests",1), 'own-count'),
 ("D2 green-mart drop from page", lambda s:re.sub(r"### Excluded from the upstream count.*\Z","",s,flags=re.S), ('pr-count', 'pr-listed')),
 ("D3 'later commit' re-added",   lambda s:s.replace("after a rebase onto the moved `main`","with a later commit",1), 'banned-string'),
 # --- structural / arithmetic ---
 ("ledger count falsified",       lambda s:s.replace("### ✅ Merged upstream — 5","### ✅ Merged upstream — 6"), ('banned-string', 'section-count')),
 ("bucket sum falsified",         lambda s:s.replace("`5 + 5 + 6 = 16`","`5 + 5 + 6 + 1 = 17`",1), 'shown-arithmetic'),
 ("identity 17/16/14 -> 17/17/14",lambda s:s.replace("17 PRs = 16 distinct changes = 14 repositories","17 PRs = 17 distinct changes = 14 repositories",1), 'shown-identity'),
 ("identity repo count wrong",    lambda s:s.replace("= 14 repositories","= 15 repositories",1), 'shown-identity'),
 ("own/upstream split falsified", lambda s:s.replace("147 of the 152 merges","144 of the 152 merges",1), 'own-split'),
 ("upstream merge count wrong",   lambda s:s.replace("leaves **5** as the merge count","leaves **7** as the merge count",1), 'own-split'),
 ("rounded 200+ -> exact 203",    lambda s:s.replace("200+ authored","203 authored",1), 'banned-string'),
 # --- inventory integrity ---
 ("PR silently removed",          lambda s:re.sub(r"- \*\*Hydra\*\*[^\n]*\n","",s,count=1), ('pr-count', 'pr-listed', 'section-count')),
 ("PR double-linked",             lambda s:s.replace("**5 merged** (SymPy 1","**5 merged** ([sympy#30567](https://github.com/sympy/sympy/pull/30567) 1",1), ('pr-count', 'pr-dup')),
 ("PR number falsified",          lambda s:s.replace("pull/30567","pull/999999",1), ('pr-known', 'pr-listed')),
 ("ledger gains a duplicate link",lambda s:s.replace("- **green-mart** &nbsp;·&nbsp; [#1](https://github.com/Deb07-Ops/green-mart/pull/1) — added","- **green-mart** &nbsp;·&nbsp; [#1](https://github.com/Deb07-Ops/green-mart/pull/1) again — added",1).replace("### ✅ Merged upstream — 5","### ✅ Merged upstream — 6"), ('banned-string', 'section-count')),
 # --- a11y / layout ---
 ("alt emptied (not decor)",      lambda s:s.replace('alt="Hashcat"','alt=""',1), 'img-alt'),
 ("H1 deleted",                   lambda s:s.replace("# Nikhil Nagpure\n\n","",1), 'headings'),
 ("fixed td width returns",       lambda s:s.replace('<td align="center">','<td width="150" align="center">',1), 'mobile'),
 ("table row unclosed",           lambda s:s.replace("</tr>","",1), 'html-balance'),
 ("div unbalanced",               lambda s:s.replace("</div>","",1), 'html-balance'),
 ("heading duplicated",           add("\n\n## \U0001F30D Open Source Contributions\n"), 'dup-section'),
 ("second H1 added",              add("\n\n# Another Name\n"), 'headings'),
 # --- content guards ---
 ("dead 404 repo re-linked",      add("\n\n[ApiSecPlatform](https://github.com/5h4d0wn1k/ApiSecPlatform)\n"), 'banned-string'),
 ("wrong badge logo returns",     lambda s:s.replace("Hashcat-334155?style=for-the-badge","Hashcat-123456?style=for-the-badge&logo=hashnode"), 'banned-string'),
 ("hackaday logo returns",        lambda s:s.replace("Offensive%20Security-22d3ee?style=for-the-badge","Offensive%20Security-22d3ee?style=for-the-badge&logo=hackaday"), 'banned-string'),
 ("dead stats return",            add("\n3,003 contributions in 2026 - 631 last week\n"), 'banned-string'),
 ("disclosure phrasing",          add("\n\nCo-authored-by: someone <a@b.c>\n"), 'banned-topic'),
 ("AI-assistance phrasing",       add("\n\nThis page was drafted with AI assistance.\n"), 'banned-topic'),
 ("LLM named",                    add("\n\nWritten with Claude.\n"), 'banned-topic'),
 ("dead shields endpoint returns",add("\n<img src=\"https://img.shields.io/github/repos/5h4d0wn1k?style=for-the-badge&label=Repositories\" alt=\"Repository count\" />\n"), 'banned-string'),
 ("dead github-readme-stats",     add("\n<img src=\"https://github-readme-stats.vercel.app/api?username=5h4d0wn1k\" alt=\"stats\" />\n"), 'banned-string'),
 ("dead activity-graph",          add("\n<img src=\"https://github-readme-activity-graph.vercel.app\" alt=\"graph\" />\n"), 'banned-string'),
 ("headline PR count inflated",   lambda s:s.replace("**17 pull requests to repositories I don't own**","**18 pull requests to repositories I don't own**",1), 'headline-claim'),
 ("headline repo count wrong",    lambda s:s.replace("across **14 repositories**","across **15 repositories**",1), 'headline-claim'),
 ("headline bullet deleted",      lambda s:re.sub(r"- \*\*17 pull requests to repositories.*\n","",s,count=1), 'headline-claim'),
 ("merged PR moved under Open",   _move_merged_under_open,            'pr-section'),
]

# ── class 2: defects in the validator's own snapshot ──────────────────────────
# These patch a copy of the validator, then run it against the untouched page.
# (name, patch to the validator source, check that must catch it)
TRUTH = [
    ("external merged count wrong",
     lambda s: s.replace('"external_merged": 5,', '"external_merged": 6,', 1),
     "bucket-split"),
    ("external open count wrong",
     lambda s: s.replace('"external_open": 5,', '"external_open": 4,', 1),
     "bucket-split"),
    ("authored total does not reconcile",
     lambda s: s.replace('"prs_authored_alltime": 206,',
                         '"prs_authored_alltime": 999,', 1),
     "arith-authored"),
    ("merge total does not reconcile",
     lambda s: s.replace('"prs_merged_alltime": 152,',
                         '"prs_merged_alltime": 999,', 1),
     "arith-merges"),
    ("own-repo states do not sum",
     lambda s: s.replace('"own_closed": 3,', '"own_closed": 9,', 1),
     "arith-own"),
    ("inventory gains a PR the page never mentions",
     lambda s: s.replace('    ("scipy/scipy", 26242): ("open", False),',
                         '    ("scipy/scipy", 26242): ("open", False),\n'
                         '    ("example/never-mentioned", 1): ("open", False),', 1),
     "pr-listed"),
]

# The one check that cannot be seeded offline: it is a live HTTP fetch. It is
# verified by hand against a real endpoint that returns 200 with an error body.
NETWORK_ONLY = {"url"}


def run_validator(target, validator=VALIDATOR):
    r = subprocess.run([sys.executable, validator, target, "--offline"],
                       capture_output=True, text=True)
    fired = set(re.findall(r"\[x\] (\S+)", r.stdout))
    return r.returncode, fired


def verdict(name, want, code, fired, dead, log):
    """A mutation is caught only if its expected check fired AND the run failed.

    Requiring both matters: a check that fires but is merely a warning would
    report success, and a run that fails for an unrelated reason would mask a
    dead check entirely.
    """
    want = (want,) if isinstance(want, str) else tuple(want)
    missing = [w for w in want if w not in fired]
    if missing and code != 0:
        ok = False
        note = "run failed but not from " + ", ".join(missing)
    elif missing:
        ok = False
        note = "expected " + ", ".join(missing) + " did not fire"
    elif code == 0:
        ok = False
        note = "check fired but the run still passed"
    else:
        ok = True
        note = ",".join(want)
    if not ok:
        dead.append(name)
    log.append((name, code, note, ok))
    return ok


def main():
    dead, noop, log = [], [], []

    print("README mutations - a defect in the page")
    print(f"  {'mutation':40} {'exit':>4}  caught by")
    print("  " + "-" * 78)
    for item in MUT:
        name, fn, want = item[0], item[1], item[2]
        mutated = fn(BASE)
        if mutated == BASE:
            noop.append(name)
            log.append((name, -1, "seed did not apply", False))
            print(f"  {name:40} {'NOOP':>4} <-- proves nothing")
            continue
        with open(MUTFILE, "w", encoding="utf-8") as fh:
            fh.write(mutated)
        code, fired = run_validator(MUTFILE)
        verdict(name, want, code, fired, dead, log)
        row = log[-1]
        print(f"  {name:40} {code:>4}  {row[2]}")

    print()
    print("Ground-truth mutations - a defect in the validator's snapshot")
    print(f"  {'mutation':40} {'exit':>4}  caught by")
    print("  " + "-" * 78)
    os.makedirs(os.path.join(TRUTHDIR, "scripts"), exist_ok=True)
    for name, patch, want in TRUTH:
        patched = patch(VALSRC)
        if patched == VALSRC:
            noop.append(name)
            log.append((name, -1, "seed did not apply", False))
            print(f"  {name:40} {'NOOP':>4} <-- proves nothing")
            continue
        dest = os.path.join(TRUTHDIR, "scripts", "validate_readme.py")
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(patched)
        code, fired = run_validator(TARGET, dest)
        verdict(name, want, code, fired, dead, log)
        row = log[-1]
        print(f"  {name:40} {code:>4}  {row[2]}")

    print()
    code, _ = run_validator(TARGET)
    print(f"  control exit: {code} (must be 0)")

    # Coverage: a check with no seed cannot be shown to work.
    emitted = sorted(set(re.findall(r'(?:ok|warn|fail)\("([a-z0-9-]+)"', VALSRC)))
    covered = set()
    for item in MUT:
        covered.update((item[2],) if isinstance(item[2], str) else item[2])
    for _, _, want in TRUTH:
        covered.update((want,) if isinstance(want, str) else want)
    untested = [c for c in emitted if c not in covered and c not in NETWORK_ONLY]
    print(f"  checks emitted by the validator : {len(emitted)}")
    print(f"  checks with at least one seed    : {len([c for c in emitted if c in covered])}")
    print(f"  network-only (verified by hand)  : {sorted(NETWORK_ONLY)}")
    if untested:
        print(f"  CHECKS WITH NO SEED             : {untested}")

    applied = len(MUT) + len(TRUTH) - len(noop)
    print(f"  applied: {applied}   seed-failures: {len(noop)}   UNDETECTED: {len(dead)}")
    if noop:
        print("  SEEDS THAT DID NOT APPLY:")
        for n in noop:
            print(f"    - {n}")
    if dead:
        print("  NOT CAUGHT:")
        for n, code_, note, _ in [r for r in log if not r[3]]:
            print(f"    - {n} (exit {code_}): {note}")

    bad = []
    if dead:
        bad.append(f"{len(dead)} mutation(s) not caught by the expected check")
    if code != 0:
        bad.append(f"control failed with exit {code}")
    if noop:
        bad.append(f"{len(noop)} seed(s) did not apply")
    if untested:
        bad.append(f"{len(untested)} check(s) have no seed: {', '.join(untested)}")
    if bad:
        print("\nFAILED: " + "; ".join(bad))
        return 1
    print(f"\nPASSED: {applied} mutations all caught by their expected check, "
          f"the control passed, and every check has a seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
