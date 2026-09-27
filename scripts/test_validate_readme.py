#!/usr/bin/env python3
"""Mutation-test validate_readme.py.

A validator that cannot fail is not a check. This introduces one deliberate
defect at a time into material that currently passes and asserts that the
validator notices it - by the *specific* check that ought to notice, not merely
that something failed. Asserting only "the run went red" would let a defect be
caught by an unrelated check while the one that should catch it sat there dead,
which is how the original seven dead checks survived.

Two classes of seed, because two different things can be wrong:

  README mutations        a defect in the page. 22 seeds.
  Ground-truth mutations  a defect in the validator's own dated snapshot. No
                          README edit can test these, because they compare
                          FACTS against FACTS and against the internal ledger.
                          This class is the only thing that exercises
                          bucket-split, arith-authored, arith-merges and
                          arith-own.

The base document is scripts/fixtures/clean-readme.md, NOT README.md. The suite
used to mutate the live page, which coupled every seed to the exact prose of the
profile: reword a heading or retire a bullet and the seeds that targeted it
silently became no-ops. 20 of 37 did exactly that on the first page edit after
they were written, and the suite still reported PASSED, because a no-op seed was
printed and then skipped rather than counted as a failure. A committed fixture
only changes when somebody deliberately changes it. Pass a path as argv[1] to
point the suite at some other document.

## How a seed is judged caught

A seed is caught when the *findings its expected check produced change*: a
different count, or a different message. Not merely "the check emitted
something", because most checks already emit something on the base document -
the content-model checks warn there precisely because the fixture is a minimal
document, not a profile. Counting a warning the control already produced would
pass a check that had been dead for years.

Two consequences, both deliberate:

  * for a hard check, the run must also exit non-zero, so a check that reports
    a defect it does not gate still gets caught;
  * for an advisory check, exiting 0 is expected and correct, so only the
    finding change counts.

A seed that does not change its document is a failure, not a skip. That was the
other half of why this suite reported green while proving nothing.

Run:  python scripts/test_validate_readme.py [path/to/base-readme.md]
Exit: 0 only if every mutation was caught by its expected check, the control
      still passes, no seed was a no-op, and no check is left unseeded.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import readme_urls as ru  # noqa: E402

VALIDATOR = os.path.join(HERE, "validate_readme.py")
FIXTURE = os.path.join(HERE, "fixtures", "clean-readme.md")
TARGET = sys.argv[1] if len(sys.argv) > 1 else FIXTURE
BASE = open(TARGET, encoding="utf-8").read()
MUTFILE = os.path.join(tempfile.gettempdir(), "readme-mutation.md")
TRUTHDIR = os.path.join(tempfile.gettempdir(), "readme-truthcheck")
VALSRC = open(VALIDATOR, encoding="utf-8").read()

# Mirrors the validator's own ADVISORY set, read from its source rather than
# restated here, so the two cannot drift apart. A seed whose check is advisory
# is allowed to leave the run green - but it still has to change the check's
# findings, so this weakens nothing.
_m = re.search(r"ADVISORY = \{(.*?)\}", VALSRC, re.S)
ADVISORY = set(re.findall(r'"([a-z0-9-]+)"', _m.group(1))) if _m else set()

# The one check no README mutation can reach: it is a live HTTP fetch. What is
# left of it that genuinely needs a network - whether shields still serves a
# given endpoint, and whether a real link is still a link - is verified by hand
# against the img.shields.io/github/repos endpoint, which answers HTTP 200 with
# "404: badge not found" and so cannot be caught by a status code. Everything
# that decides WHICH url to ask about, and whether one bad answer is believed,
# is tested offline in the URL-helpers class below.
NETWORK_ONLY = {"url"}


def add(text):
    return lambda s: s + text


def sub(old, new):
    """Replace exactly one occurrence, and say so loudly if there is not exactly
    one. A seed that quietly replaces nothing is worse than no seed."""
    def fn(s):
        if s.count(old) != 1:
            raise AssertionError(f"seed anchor appears {s.count(old)} times: {old!r}")
        return s.replace(old, new, 1)
    return fn


def sub_re(pattern, repl):
    def fn(s):
        new, n = re.subn(pattern, repl, s, count=1)
        if n != 1:
            raise AssertionError(f"seed pattern matched {n} times: {pattern!r}")
        return new
    return fn


def line_containing(needle, header):
    """Move the line containing `needle` to just after the first line starting
    with `header`.

    Used by the section-placement seeds, which have to relocate an entry without
    changing any number, so that only a check reading section membership can
    notice. Returns the document unchanged if the fixture ever stops matching,
    which the no-op guard then reports.
    """
    def fn(s):
        lines = s.split("\n")
        if not any(needle in l for l in lines):
            return s
        at = next((i for i, l in enumerate(lines) if needle in l), None)
        if at is None:
            return s
        entry = lines.pop(at)
        dest = next((i for i, l in enumerate(lines) if l.startswith(header)), None)
        if dest is None:
            return s
        lines.insert(dest + 1, entry)
        return "\n".join(lines)
    return fn


# ── class 1: defects in the page ──────────────────────────────────────────────
# (name, mutation, check that must catch it)
MUT = [
    # --- forbidden strings: dead services, wrong numbers, wrong logos ---
    ("dead contributions stats return", add("\n\n3,003 contributions in 2026\n"), "banned-string"),
    ("dead last-week stat return",       add("\n\n631 last week\n"), "banned-string"),
    ("dead repo-count badge returns",    add('\n<img src="https://img.shields.io/github/repos/5h4d0wn1k?style=for-the-badge" alt="Repos" />\n'), "banned-string"),
    ("dead stats service returns",       add("\n\ngithub-readme-stats\n"), "banned-string"),
    ("dead activity graph returns",      add("\n\nactivity-graph.vercel.app\n"), "banned-string"),
    ("stale authored total returns",     add("\n\n134 authored\n"), "banned-string"),
    ("streak claim on a last-commit badge", add('\n<img src="https://img.shields.io/github/last-commit/5h4d0wn1k?style=for-the-badge&label=Streak" alt="Streak" />\n'), "banned-string"),
    ("wrong vendor logo on a badge",     sub("logo=python", "logo=hashnode"), "banned-string"),

    # --- authorship disclosure: the owner's hard requirement ---
    ("assistant named",                  add("\n\nAssisted by ChatGPT\n"), "banned-topic"),
    ("AI-assistance phrasing",          add("\n\nThis page was generated with an AI assistant\n"), "banned-topic"),
    ("AI-author phrasing",              add("\n\nWrit by GPT-4\n"), "banned-topic"),

    # --- images ---
    ("alt emptied (not decor)",         sub('alt="Python"', 'alt=""'), "img-alt"),
    ("alt attribute dropped",           sub_re(r'\s+alt="Python"', ""), "img-alt"),
    ("image added with no alt at all",  add('\n<img src="https://img.shields.io/badge/Plain-555555?style=flat-square" />\n'), "img-alt"),

    # --- table geometry on a phone ---
    ("fixed td width too narrow",       sub('width="200"', 'width="110"'), "mobile"),

    # --- markup ---
    ("table row unclosed",              sub("  </tr>\n", ""), "html-balance"),
    ("table unclosed",                  sub("</table>", ""), "html-balance"),

    # --- outline ---
    ("second H1 added",                 add("\n\n# A Second Title\n"), "headings"),
    ("heading duplicated",              add("\n\n## 🧰 Tech Stack\n"), "dup-section"),

    # --- the pull-request ledger ---
    ("invented PR linked",              add("\n\n- [not a real PR](https://github.com/example/never-existed/pull/9999)\n"), "pr-known"),
    ("one PR linked twice",             sub("(merged)\n", "(merged) and again\n\n- **SymPy** — [again](https://github.com/sympy/sympy/pull/30567) (merged)\n"), "pr-dup"),
    ("section count falsified",         sub("### ✅ Merged upstream — 1", "### ✅ Merged upstream — 2"), "section-count"),
    ("merged PR filed under Open",      line_containing("sympy/sympy/pull/30567", "### Open"), "pr-section"),
    ("both ledger PRs vanish",          lambda s: "\n".join(l for l in s.split("\n") if "pull/" not in l), "pr-listed"),
    ("ledger count drifts from the API", add("\n\n- **pandas** — [a real PR, counted twice over](https://github.com/pandas-dev/pandas/pull/69429) (open)\n"), "pr-count"),

    # --- figures the page prints for the reader to check ---
    ("shown sum does not add up",       add("\n\n`2 + 3 = 9`\n"), "shown-arithmetic"),
    ("identity triple wrong",           add("\n\n**17 PRs = 16 distinct changes = 15 repositories**\n"), "shown-identity"),
    ("headline third-party figures wrong", add("\n\n**17 pull requests to repositories I don't own**, across **16 repositories**\n"), "headline-claim"),
    ("own-repo count wrong",            add("\n\nOf the 190 pull requests to my own repositories, 40 are still open and 3 were closed\n"), "own-count"),
    ("own/upstream split falsified",    add("\n\n144 of the 152 merges went to a repository I could already push to\n"), "own-split"),
]

# ── class 2: defects in the validator's own dated snapshot ────────────────────
# (name, patch of the validator source, check that must catch it)
TRUTH = [
    ("authored total does not reconcile",
     lambda s: sub('"prs_authored_alltime": 206,',
                   '"prs_authored_alltime": 999,')(s), "arith-authored"),
    ("merge total does not reconcile",
     lambda s: sub('"prs_merged_alltime": 152,',
                   '"prs_merged_alltime": 999,')(s), "arith-merges"),
    ("own-repo states do not sum",
     lambda s: sub('"own_closed": 3,', '"own_closed": 9,')(s), "arith-own"),
    ("merged bucket does not match the table",
     lambda s: sub('"external_merged": 5,', '"external_merged": 9,')(s), "bucket-split"),
    ("inventory gains a PR the page never mentions",
     lambda s: sub('    ("scipy/scipy", 26242): ("open", False),',
                   '    ("scipy/scipy", 26242): ("open", False),\n'
                   '    ("example/never-mentioned", 1): ("open", False),')(s), "pr-listed"),
]


def run_validator(target, validator=VALIDATOR):
    """Run the validator and return (exit code, {check: sorted list of details}).

    Both verdicts are collected on purpose. FAIL and WARN are different
    severities, but for the purpose of "did this check notice the defect" they
    are the same event - a check that reports a defect it does not gate has
    still noticed it.
    """
    r = subprocess.run([sys.executable, validator, target, "--offline"],
                       capture_output=True, text=True)
    findings = {}
    for check, detail in re.findall(r"\[(?:x|!)\] ([a-z0-9-]+) +(.*)", r.stdout):
        findings.setdefault(check, []).append(detail)
    return r.returncode, {k: sorted(v) for k, v in findings.items()}


def verdict(name, want, code, findings, control, dead, log):
    """A mutation is caught only if its expected check's findings CHANGED.

    Requiring a change rather than mere presence is what keeps this honest: on
    the base document most content-model checks already emit a finding, so
    "the check said something" would be satisfied by a check that had been dead
    since it was written.

    For a hard check the run must also exit non-zero - a check that notices a
    defect but does not gate the build is still caught, and worth catching, so
    the exit code is required from the checks that are supposed to gate.
    """
    want = (want,) if isinstance(want, str) else tuple(want)
    unchanged = [w for w in want if findings.get(w) == control.get(w)]
    if unchanged:
        note = (f"expected {', '.join(unchanged)} to change its findings; "
                f"control had {len(control.get(unchanged[0], []))}, "
                f"mutant had {len(findings.get(unchanged[0], []))}")
        ok = False
    elif not set(want) & ADVISORY and code == 0:
        note = ("the check reported the defect but the run still passed - it is "
                "in ADVISORY so it is routed to WARN, which cannot gate")
        ok = False
    else:
        hit = ", ".join(w for w in want if w in findings)
        # Not "did the run go red" - the run can be red for an unrelated reason,
        # and an advisory check never turns it red on its own.
        kind = "advisory" if set(want) & ADVISORY else "gating"
        note = f"{hit}  ({kind})"
        ok = True
    if not ok:
        dead.append(name)
    log.append((name, code, note, ok))
    return ok


# ── class 3: the URL helpers, tested directly and offline ─────────────────────
# The `url` check is the one check no README mutation can reach, because it is a
# live HTTP fetch, and it was listed as verified-by-hand for exactly as long as
# it took to be wrong in a way hand verification could not see. Hand-checking a
# badge means copying its URL out of the source, which is the one URL the
# validator was not being asked about: the harvester stopped it at the ")". Two
# parenthesised badges were reported broken, the reports were disbelieved, and
# the belief was correct - for the wrong reason.
#
# So the half that decides WHICH url to fetch is now a plain function in
# readme_urls.py and is tested here, and the retry behaviour is tested against
# an injected transport rather than against shields' mood. What is left
# hand-verified is only the part that genuinely needs a network.
class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _seq_opener(responses):
    """An opener that returns each response in turn, repeating the last."""
    calls = []

    def opener(req, timeout=None):
        calls.append(req.full_url)
        r = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return _Resp(r)
    return opener, calls


GOOD_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><title>PASS: build</title></svg>'
DEAD_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><title>404: badge not found</title></svg>'
INACC_SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><title>inaccessible</title></svg>'
IELTS = ("https://img.shields.io/badge/IELTS%207.5%20(C1)-2a9d8f"
         "?style=flat-square")


def _u_harvests_whole_url():
    """The regression: a parenthesised badge must not be cut at the ')'."""
    got = ru.harvest_urls(f'<img src="{IELTS}" alt="IELTS" />')
    assert got == {IELTS}, f"truncated or mangled: {got}"


def _u_harvests_bare_parenthesised():
    """Same, for a markdown image where the URL is not inside an attribute."""
    got = ru.harvest_urls(f"![IELTS]({IELTS})")
    assert got == {IELTS}, f"markdown URL mangled: {got}"


def _u_closes_markdown_link():
    """A balanced-paren rule must not swallow markdown's own ')'."""
    got = ru.harvest_urls("see [x](https://example.com/a) and (trailing prose)")
    assert got == {"https://example.com/a"}, f"over-captured: {got}"


def _u_ampersand_only():
    """&amp; becomes &, but nothing else is entity-decoded."""
    got = ru.harvest_urls('<a href="https://e.com/?a=1&amp;b=2&amp;section=h">')
    assert got == {"https://e.com/?a=1&b=2&section=h"}, f"wrong decode: {got}"


def _u_reads_attributes():
    got = ru.harvest_urls('<img src="https://a.com/1.png"><a href="https://b.com/2">')
    assert got == {"https://a.com/1.png", "https://b.com/2"}, f"missed: {got}"


def _u_bot_blocked():
    assert ru.is_bot_blocked("https://www.linkedin.com/in/x/")
    assert ru.is_bot_blocked("https://cuboidsoft.in")
    assert not ru.is_bot_blocked("https://github.com/x/y")


def _u_badge_healthy_one_fetch():
    op, calls = _seq_opener([GOOD_SVG])
    body, marker = ru.badge_body(IELTS, opener=op, sleeper=lambda *_: None)
    assert marker is None and "<svg" in body and len(calls) == 1, (marker, calls)


def _u_badge_tolerates_one_transient():
    op, calls = _seq_opener([DEAD_SVG, GOOD_SVG])
    _, marker = ru.badge_body(IELTS, opener=op, sleeper=lambda *_: None)
    assert marker is None, f"one transient marker was believed: {marker}"
    assert len(calls) == 2, f"did not retry: {calls}"


def _u_badge_inaccessible_transient():
    op, calls = _seq_opener([INACC_SVG, GOOD_SVG])
    _, marker = ru.badge_body(IELTS, opener=op, sleeper=lambda *_: None)
    assert marker is None and len(calls) == 2, (marker, calls)


def _u_badge_dead_still_caught():
    op, calls = _seq_opener([DEAD_SVG, DEAD_SVG])
    _, marker = ru.badge_body(IELTS, opener=op, sleeper=lambda *_: None)
    assert marker == "badge not found", f"dead endpoint masked: {marker}"
    assert len(calls) == 2, f"did not retry: {calls}"


def _u_badge_persistently_inaccessible():
    op, _ = _seq_opener([INACC_SVG, INACC_SVG])
    _, marker = ru.badge_body(IELTS, opener=op, sleeper=lambda *_: None)
    assert marker == "inaccessible", f"masked: {marker}"


def _u_fetch_retries_timeout():
    """The profile summary cards cold-start: slow once, then fine."""
    op, calls = _seq_opener([TimeoutError("timed out"), GOOD_SVG])
    ok, detail = ru.fetch_ok("https://cards.example/x.svg", opener=op,
                             sleeper=lambda *_: None)
    assert ok and detail == 200, f"timeout not retried: {ok} {detail}"
    assert len(calls) == 2, f"did not retry: {calls}"


def _u_fetch_persistent_failure_reported():
    op, calls = _seq_opener([TimeoutError("timed out")])
    ok, detail = ru.fetch_ok("https://cards.example/x.svg", opener=op,
                             sleeper=lambda *_: None)
    assert not ok and detail == "TimeoutError", f"masked: {ok} {detail}"
    assert len(calls) == 2, f"did not retry: {calls}"


def _u_fetch_http_error_not_retried():
    """A 404 is an answer, not a hiccup - retrying it only wastes time."""
    op, calls = _seq_opener([urllib.error.HTTPError("u", 404, "n", {}, None)])
    ok, detail = ru.fetch_ok("https://e.com/gone", opener=op, sleeper=lambda *_: None)
    assert not ok and detail == 404, f"wrong: {ok} {detail}"
    assert len(calls) == 1, f"retried a definitive answer: {calls}"


# ── the concurrency must not change a single verdict ───────────────────────────
# check_all() runs the fetches in a thread pool, which means a URL can be judged
# in any order and a shared transport can be entered at any point. The report
# therefore has to be a function of the inputs alone, or the same page would
# produce different output depending on which host happened to be slow.
def _route_opener(routes):
    """An opener that answers from a {url: response} map, and records the order."""
    seen = []

    def opener(req, timeout=None):
        seen.append(req.full_url)
        r = routes.get(req.full_url, GOOD_SVG)
        if isinstance(r, Exception):
            raise r
        return _Resp(r)
    return opener, seen


MIXED = {
    IELTS: GOOD_SVG,
    "https://img.shields.io/github/repos-5h4d0wn1k": DEAD_SVG,
    "https://img.shields.io/badge/x%20(y)-blue": GOOD_SVG,
    "https://www.linkedin.com/in/x/": GOOD_SVG,
    "https://cuboidsoft.in": GOOD_SVG,
    "https://e.com/ok": GOOD_SVG,
    "https://e.com/forbidden": urllib.error.HTTPError("u", 403, "no", {}, None),
    "https://e.com/gone": urllib.error.HTTPError("u", 404, "no", {}, None),
}
MIXED_URLS = sorted(MIXED)


def _u_check_one_badge_ok():
    op, _ = _route_opener(MIXED)
    assert ru.check_one(IELTS, opener=op, sleeper=lambda *_: None) == ("ok", "badge")


def _u_check_one_badge_dead():
    op, _ = _route_opener(MIXED)
    v, d = ru.check_one("https://img.shields.io/github/repos-5h4d0wn1k",
                        opener=op, sleeper=lambda *_: None)
    assert v == "bad" and "badge not found" in d, (v, d)


def _u_check_one_badge_not_svg():
    op, _ = _route_opener({"https://img.shields.io/x": b"<html>nope</html>"})
    v, d = ru.check_one("https://img.shields.io/x", opener=op, sleeper=lambda *_: None)
    assert v == "bad" and d == "not an SVG", (v, d)


def _u_check_one_bot_blocked_warns():
    op, calls = _route_opener(MIXED)
    v, d = ru.check_one("https://www.linkedin.com/in/x/", opener=op, sleeper=lambda *_: None)
    assert (v, d) == ("warn", "bot-blocked host, skipped"), (v, d)
    assert calls == [], f"should not have been fetched at all: {calls}"


def _u_check_one_link_ok():
    op, _ = _route_opener(MIXED)
    assert ru.check_one("https://e.com/ok", opener=op, sleeper=lambda *_: None) == ("ok", "")


def _u_check_one_403_warns():
    op, _ = _route_opener(MIXED)
    v, d = ru.check_one("https://e.com/forbidden", opener=op, sleeper=lambda *_: None)
    assert v == "warn" and d == "403 bot-blocked", (v, d)


def _u_check_one_404_fails():
    op, calls = _route_opener(MIXED)
    v, d = ru.check_one("https://e.com/gone", opener=op, sleeper=lambda *_: None)
    assert v == "bad" and d == "404 on two consecutive attempts", (v, d)
    assert len(calls) == 1, f"a definitive 404 was retried: {calls}"


def _u_check_all_matches_sequential():
    """The whole point: 1 worker and 8 workers must agree exactly."""
    op1, seen1 = _route_opener(MIXED)
    op8, seen8 = _route_opener(MIXED)
    seq = ru.check_all(MIXED_URLS, workers=1, opener=op1, sleeper=lambda *_: None)
    par = ru.check_all(MIXED_URLS, workers=8, opener=op8, sleeper=lambda *_: None)
    assert seq == par, f"\n  sequential: {seq}\n  parallel:   {par}"
    # and the outcome is the one the table above says it should be
    bad, warned, good, total = par
    assert total == len(MIXED_URLS)
    assert good == 2, f"badges counted: {good}"
    assert len(warned) == 3, f"warned: {warned}"
    assert len(bad) == 2, f"bad: {bad}"


def _u_check_all_single_url_sequential():
    """A one-URL page must not spin up a pool."""
    op, _ = _route_opener({"https://e.com/ok": GOOD_SVG})
    assert ru.check_all(["https://e.com/ok"], workers=8,
                        opener=op, sleeper=lambda *_: None)[3] == 1


UNIT = [v for k, v in sorted(globals().items()) if k.startswith("_u_")]


def run_units(dead, log):
    print("URL helpers - tested directly, no network")
    print(f"  {'test':38} result")
    print("  " + "-" * 78)
    for fn in UNIT:
        try:
            fn()
            print(f"  {fn.__name__[3:]:38} ok")
            log.append((fn.__name__[3:], 0, "ok", True))
        except AssertionError as e:
            dead.append(fn.__name__[3:])
            print(f"  {fn.__name__[3:]:38} FAILED  {e}")
            log.append((fn.__name__[3:], 1, str(e), False))
        except Exception as e:                       # noqa: BLE001
            dead.append(fn.__name__[3:])
            print(f"  {fn.__name__[3:]:38} ERROR   {type(e).__name__}: {e}")
            log.append((fn.__name__[3:], 1, f"{type(e).__name__}: {e}", False))
    print()


def main():
    dead, noop, log = [], [], []
    run_units(dead, log)

    ctl_code, control = run_validator(TARGET)
    print(f"base document: {os.path.relpath(TARGET)}   control exit: {ctl_code} (must be 0)")
    print(f"control findings: {sum(len(v) for v in control.values())} across "
          f"{len(control)} checks")
    print()
    print("README mutations - a defect in the page")
    print(f"  {'mutation':38} {'exit':>4}  caught by")
    print("  " + "-" * 78)
    for name, fn, want in MUT:
        try:
            mutated = fn(BASE)
        except AssertionError as e:
            noop.append(name)
            log.append((name, -1, f"seed did not apply: {e}", False))
            print(f"  {name:38} {'NOOP':>4} <-- proves nothing")
            continue
        if mutated == BASE:
            noop.append(name)
            log.append((name, -1, "seed did not apply", False))
            print(f"  {name:38} {'NOOP':>4} <-- proves nothing")
            continue
        with open(MUTFILE, "w", encoding="utf-8") as fh:
            fh.write(mutated)
        code, findings = run_validator(MUTFILE)
        verdict(name, want, code, findings, control, dead, log)
        print(f"  {name:38} {code:>4}  {log[-1][2]}")

    print()
    print("Ground-truth mutations - a defect in the validator's snapshot")
    print(f"  {'mutation':38} {'exit':>4}  caught by")
    print("  " + "-" * 78)
    os.makedirs(os.path.join(TRUTHDIR, "scripts"), exist_ok=True)
    dest = os.path.join(TRUTHDIR, "scripts", "validate_readme.py")
    # The validator imports readme_urls.py from its own directory, so the patched
    # copy needs its sibling beside it. Without this the patched run dies on
    # ImportError before any check runs, and every ground-truth seed reports
    # "not caught" for a reason that has nothing to do with the check.
    shutil.copy(os.path.join(HERE, "readme_urls.py"),
                os.path.join(TRUTHDIR, "scripts", "readme_urls.py"))
    for name, patch, want in TRUTH:
        try:
            patched = patch(VALSRC)
        except AssertionError as e:
            noop.append(name)
            log.append((name, -1, f"seed did not apply: {e}", False))
            print(f"  {name:38} {'NOOP':>4} <-- proves nothing")
            continue
        if patched == VALSRC:
            noop.append(name)
            log.append((name, -1, "seed did not apply", False))
            print(f"  {name:38} {'NOOP':>4} <-- proves nothing")
            continue
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(patched)
        code, findings = run_validator(TARGET, dest)
        verdict(name, want, code, findings, control, dead, log)
        print(f"  {name:38} {code:>4}  {log[-1][2]}")

    # Coverage: a check with no seed cannot be shown to work.
    emitted = sorted(set(re.findall(r'(?:ok|warn|fail)\("([a-z0-9-]+)"', VALSRC)))
    covered = set()
    for _, _, want in MUT:
        covered.update((want,) if isinstance(want, str) else want)
    for _, _, want in TRUTH:
        covered.update((want,) if isinstance(want, str) else want)
    untested = [c for c in emitted if c not in covered and c not in NETWORK_ONLY]
    seeded = [c for c in emitted if c in covered]
    print()
    print(f"  checks emitted by the validator : {len(emitted)}")
    print(f"  checks with at least one seed    : {len(seeded)}")
    print(f"  network-only (verified by hand)  : {sorted(NETWORK_ONLY)}")
    if untested:
        print(f"  CHECKS WITH NO SEED             : {untested}")

    applied = len(MUT) + len(TRUTH) + len(UNIT) - len(noop)
    print(f"  applied: {applied}   no-op seeds: {len(noop)}   UNDETECTED: {len(dead)}")
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
    if ctl_code != 0:
        bad.append(f"control failed with exit {ctl_code}")
    if noop:
        bad.append(f"{len(noop)} seed(s) did not apply")
    if untested:
        bad.append(f"{len(untested)} check(s) have no seed: {', '.join(untested)}")
    if bad:
        print("\nFAILED: " + "; ".join(bad))
        return 1
    print(f"\nPASSED: {len(MUT) + len(TRUTH)} mutations caught by their expected check, "
          f"{len(UNIT)} URL-helper tests passed, the control passed, no seed was a "
          f"no-op, and every check has a seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
