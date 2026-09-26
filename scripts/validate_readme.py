#!/usr/bin/env python3
"""
Deterministic validator for the 5h4d0wn1k profile README.

Design rule: this script checks the README against GROUND TRUTH captured from the
GitHub API on 2026-09-26. It never checks the README against itself. A number in
the README is correct only if it matches this table.

Run:  python3 validate_readme.py [path/to/README.md]
Exit: 0 = all checks pass, 1 = at least one FAIL
      (WARN does not fail the build; see --strict)
"""

import re
import sys
import json
import time
import urllib.request
import urllib.error
from html import unescape  # noqa: F401  (kept for callers; see note below)

STRICT = "--strict" in sys.argv
NET = "--offline" not in sys.argv
path = next((a for a in sys.argv[1:] if not a.startswith("--")), "README.md")

FAIL, WARN, OK = [], [], []


def fail(check, detail):
    FAIL.append((check, detail))


def warn(check, detail):
    WARN.append((check, detail))


def ok(check, detail=""):
    OK.append((check, detail))


# ───────────────────────── ground truth (from `gh`, 2026-09-26) ─────────────────────────

PR_STATE = {
    # (owner/repo, number): (state, merged)
    ("sympy/sympy", 30567): ("closed", True),
    ("TheAlgorithms/Python", 15402): ("closed", True),
    ("TheAlgorithms/Python", 15405): ("closed", True),
    ("freeCodeCamp/freeCodeCamp", 70289): ("closed", True),
    ("EbookFoundation/free-programming-books", 13472): ("closed", True),
    ("Deb07-Ops/green-mart", 1): ("closed", True),   # disclosed, not counted upstream
    ("scipy/scipy", 26242): ("open", False),
    ("scipy/xsf", 284): ("open", False),
    ("pandas-dev/pandas", 69429): ("open", False),
    ("google/or-tools", 5426): ("open", False),
    ("anomalyco/opencode", 51514): ("open", False),
    ("pandas-dev/pandas", 69428): ("closed", False),
    ("networkx/networkx", 8926): ("closed", False),
    ("networkx/networkx", 8927): ("closed", False),
    ("github/docs", 46017): ("closed", False),
    ("hydra-ecosystem/hydra", 3465): ("closed", False),
    ("jwadow/kiro-gateway", 240): ("closed", False),
}

# GROUND TRUTH — a dated snapshot, not a live figure.
#
# Re-derived 2026-09-26 by enumerating every `author:5h4d0wn1k type:pr` result
# (206 total, all 3 pages) and classifying by repository owner.
#
# "Own" = the viewer's account, the 4 orgs they are a member of (each confirmed
# HTTP 204 on /orgs/{org}/members/5h4d0wn1k), and Deb07-Ops. Deb07-Ops is a
# personal account, not an org, but the viewer holds `viewerPermission: WRITE`
# on Deb07-Ops/green-mart, the repo is not a fork, and Deb07-OOps is a member of
# Shadownik-official alongside the viewer. Same team -> not upstream.
#
# Every genuine external repo returns viewerPermission READ. green-mart returned
# WRITE, which is how it was caught being wrongly counted as upstream.
#
# These totals MOVE: they went 201 -> 203 -> 206 during one review pass, because
# the account is actively opening pull requests. The README therefore quotes
# rounded lifetime figures and dates the exact measurement, and this table is the
# dated snapshot it is checked against. Re-derive before trusting it.
FACTS = {
    # PRs to repositories with no write access for the viewer -> the upstream ledger
    "external_prs": 16,
    "external_repos": 13,
    "external_merged": 5,
    "external_open": 5,
    "external_closed": 6,
    # PRs to repositories the viewer does not own, including the one where they
    # hold collaborator write access and which is therefore disclosed, not counted
    "third_party_prs": 17,
    "third_party_repos": 14,
    "collaborator_merged": 1,
    # Own side EXCLUDES green-mart: that repo is owned by Deb07-Ops, a different
    # person. It is counted once, on the third-party side, under collaborator access.
    "own_total": 189,
    "own_merged": 146,
    "own_open": 40,
    "own_closed": 3,
    "prs_authored_alltime": 206,
    "prs_merged_alltime": 152,
}

# Names that must never appear: unverifiable, or factually wrong claims.
BANNED_STRINGS = [
    "3,003", "631 last week", "Repositories-243", "134 authored", "95 merged",
    "201 authored", "150 merged", "144 of those", "5 + 4 + 6 + 2",
    "4 under review", "Not counted as fixes",
    "203 authored", "17 upstream", "14 external", "Merged upstream — 6",
    "6 + 5 + 6", "closed in favour of", "closed in its favour",
    # implies additional engineering; the second PR was a rebase onto a moved main
    "with a later commit",
    # a shields last-commit endpoint renders a date; calling that a streak is false
    "label=Streak",
    # CONTRIBUTING rule 4. These services are known-dead; the workflow this
    # replaces grepped for them, so the guard has to live here or replacing it
    # would quietly drop the check.
    "github-readme-stats", "github-readme-activity-graph", "activity-graph.vercel",
    # shields removed the github/repos endpoint: it answers HTTP 200 with a
    # "404: badge not found" body, so only a body check can catch its return
    "github/repos",
    "ApiSecPlatform", "Portable Wireless Pentest",
    "logo=hashnode", "Hashcat-123456", "logo=hackaday",
    "label=Last+Commit",  # superseded by a correct streak badge
]
# Content that must not appear anywhere (hard requirement from the owner).
# Authorship-disclosure phrasing only. "AI/LLM" also appears legitimately on this
# page as a *focus area* and in product names, so it is not banned wholesale.
BANNED_TOPICS = [
    "co-authored-by", "coauthored-by", "co-authored by",
    "generated by", "generated with", "ai-generated", "ai generated",
    "ai-assisted", "ai assisted", "assistance from", "drafted by",
    "language model", "llm-generated", "written by an ai", "chatgpt",
    "copilot", "claude", "gemini", "gpt-4", "gpt-5",
]
# Paraphrase-proof patterns. Literal matching missed "drafted with AI assistance".
BANNED_TOPIC_RE = [
    r"\b(?:with|via|using|by)\s+(?:an?\s+)?(?:ai|llm|ml)\b[^.\n]{0,40}\bassist",
    r"\bassist(?:ed|ance)\s+by\b",
    r"\b(?:ai|llm)[- ]?(?:assist|assist(ed|ance)|generat|auth(or|ored)|writ|creat)",
    r"\b(?:generat|auth(or|ored)|writ|creat)\w*\s+by\s+(?:an?\s+)?(?:ai|llm|gpt|chatgpt|claude|gemini|copilot)\b",
    r"\b(?:chatgpt|claude|gemini|copilot|gpt-?[45])\b",
    r"\bprompt(?:ed)?\s+(?:by|to)\s+(?:an?\s+)?(?:ai|llm)\b",
]
# Editorial rule: the open section lists 5 open PRs but one is explicitly held
# back, so calling the section "Under review" would overstate reviewer attention.
BANNED_TOPICS += ["under review", "awaiting review"]

# ───────────────────────── load ─────────────────────────

try:
    raw = open(path, encoding="utf-8").read()
except OSError as e:
    print(f"FATAL: cannot read {path}: {e}")
    sys.exit(1)

# ───────────────────────── 1. HTML well-formedness ─────────────────────────

for tag in ("div", "table", "tr", "td", "th", "p", "a", "details", "summary", "sub", "b"):
    o = len(re.findall(rf"<{tag}[\s>]", raw, re.I))
    c = len(re.findall(rf"</{tag}>", raw, re.I))
    if o != c:
        fail("html-balance", f"<{tag}>: {o} open vs {c} close")
    else:
        ok("html-balance", f"<{tag}> balanced ({o})")

if re.search(r"<br>\s*$", raw, re.M) is None and "<br/>" not in raw:
    warn("html-balance", "no <br/> found - verify line breaks render")

# ───────────────────────── 2. alt text on every image ─────────────────────────

imgs = re.findall(r"<img\b[^>]*>", raw, re.I)
decorative = 0
for tag in imgs:
    m = re.search(r'\balt\s*=\s*"([^"]*)"', tag, re.I)
    if not m:
        fail("img-alt", f"missing alt attribute entirely: {tag[:90]}")
    elif not m.group(1).strip():
        # alt="" is only correct when the image is explicitly marked decorative.
        if re.search(r'aria-hidden\s*=\s*"true"', tag, re.I) or \
           re.search(r'role\s*=\s*"presentation"', tag, re.I):
            decorative += 1
        else:
            fail("img-alt", f'alt="" without aria-hidden/role=presentation: {tag[:90]}')
ok("img-alt", f"{len(imgs)} <img> tags carry alt ({decorative} explicitly decorative, "
              f"{len(imgs) - decorative} descriptive)")

# ───────────────────────── 3. heading outline ─────────────────────────

h1 = re.findall(r"^# (.+)$", raw, re.M)
if len(h1) == 0:
    fail("headings", "no H1 - the profile subject is not a text heading, so the "
                     "heading outline starts at H2 and screen readers announce no name")
elif len(h1) > 1:
    fail("headings", f"{len(h1)} H1s: {h1}")
else:
    ok("headings", f"H1 = {h1[0]!r}")

# ───────────────────────── 4. forbidden strings ─────────────────────────

low = raw.lower()
for s in BANNED_STRINGS:
    if s.lower() in low:
        fail("banned-string", f"contains {s!r}")
for t in BANNED_TOPICS:
    if t.lower() in low:
        fail("banned-topic", f"contains {t!r}")
for pat in BANNED_TOPIC_RE:
    m = re.search(pat, raw, re.I)
    if m:
        fail("banned-topic", f"disclosure phrasing matches /{pat}/: {m.group(0)!r}")
# No summary line here on purpose. The previous one was an ok() with no
# matching fail(), so it could only ever print success; it restated banned-string
# and banned-topic, which assert the same thing for each entry.

# ───────────────────────── 5. every referenced PR is real and in the right section ─────────────────────────

pr_links = re.findall(r"https://github\.com/([\w.\-]+/[\w.\-]+)/pull/(\d+)", raw)
seen = set()
for repo, num in pr_links:
    key = (repo, int(num))
    if key not in PR_STATE:
        fail("pr-known", f"{repo}#{num} is not in the verified inventory")
    elif key in seen:
        fail("pr-dup", f"{repo}#{num} linked more than once")
    else:
        seen.add(key)

_unlisted = sorted(set(PR_STATE) - seen)
if _unlisted:
    for key in _unlisted:
        fail("pr-listed",
             f"{key[0]}#{key[1]} is in the verified inventory but the page never "
             f"mentions it, so a pull request that was really opened goes uncounted")
else:
    ok("pr-listed", f"all {len(PR_STATE)} inventory pull requests appear on the page")

# The ledger sections carry the counted PRs; the disclosure section carries the
# collaborator one. Counting every link would conflate the two.
LEDGER_RE = re.compile(
    r"### \u2705 Merged upstream.*?(?=### Excluded from the upstream count|\Z)", re.S)
ledger = LEDGER_RE.search(raw)
ledger_links = (len(re.findall(r"github\.com/[\w.\-]+/[\w.\-]+/pull/\d+", ledger.group(0)))
                if ledger else 0)
if ledger_links != FACTS["external_prs"]:
    fail("pr-count",
         f"ledger lists {ledger_links} PRs; verified no-write-access total is "
         f"{FACTS['external_prs']}")
else:
    ok("pr-count", f"ledger lists {ledger_links} PRs = verified no-write-access total")

third_party = len(pr_links)
if third_party != FACTS["third_party_prs"]:
    fail("pr-count",
         f"README links {third_party} third-party PRs; verified total is "
         f"{FACTS['third_party_prs']}")
else:
    ok("pr-count", f"{third_party} third-party PRs linked = verified total (16 ledger + 1 disclosed)")

if len({r for r, _ in pr_links}) != FACTS["third_party_repos"]:
    fail("pr-count", f"{len({r for r, _ in pr_links})} distinct third-party repos, "
                     f"verified {FACTS['third_party_repos']}")
else:
    ok("pr-count", f"{FACTS['third_party_repos']} distinct third-party repos, matches")

# A merged pull request listed under "Open", or an unmerged one listed under
# "Merged upstream", is a factual error - the single easiest way for this ledger
# to become wrong while every count still adds up.
LEDGER_HEADS = [(m.start(), m.group(0).lower())
                for m in re.finditer(r"^### .*?—\s*\d+\s*$", raw, re.M)]
LEDGER_BOUNDS = []
for _i, (_pos, _title) in enumerate(LEDGER_HEADS):
    _end = LEDGER_HEADS[_i + 1][0] if _i + 1 < len(LEDGER_HEADS) else len(raw)
    LEDGER_BOUNDS.append((_pos, _end, _title))


def _which_section(idx):
    for _s, _e, _t in LEDGER_BOUNDS:
        if _s <= idx < _e:
            return _t
    return None


_wrong, _placed = [], 0
for _key in sorted(seen):
    _repo, _num = _key
    _state, _merged = PR_STATE[_key]
    _url = f"github.com/{_repo}/pull/{_num}"
    _at = raw.find(_url)
    if _at < 0:
        continue
    _title = _which_section(_at) or ""
    if _merged:
        _good = "merged upstream" in _title or "excluded from the upstream count" in _title
        _want = "a merged or explicitly excluded section"
    elif _state == "open":
        _good = "open" in _title
        _want = "the open section"
    else:
        _good = "closed" in _title
        _want = "the closed-without-merge section"
    if _good:
        _placed += 1
    else:
        _wrong.append(f"{_repo}#{_num} is {'merged' if _merged else _state} "
                      f"but is listed under {_title.strip()!r}, not {_want}")

if _wrong:
    for _m in _wrong:
        fail("pr-section", _m)
else:
    ok("pr-section",
       f"all {_placed} pull requests sit in the section matching their state")

# ───────────────────────── 5b. each section's stated count matches its contents ─────────────────────────

SECTION_RE = re.compile(r"^### .*?—\s*(\d+)\s*$", re.M)
heads = [(m.start(), int(m.group(1)), m.group(0)) for m in SECTION_RE.finditer(raw)]
for idx, (pos, claimed, title) in enumerate(heads):
    end = heads[idx + 1][0] if idx + 1 < len(heads) else len(raw)
    body = raw[pos:end]
    if "pull/" not in body:            # not a PR section (e.g. a numbered heading)
        continue
    actual = len(re.findall(r"https://github\.com/[\w.\-]+/[\w.\-]+/pull/\d+", body))
    if actual != claimed:
        fail("section-count", f"{title!r} claims {claimed} but lists {actual} PR links")
    else:
        ok("section-count", f"{title!r} -> {actual} links, matches")

# bucket totals must equal the API's split
LEDGER = {k: v for k, v in PR_STATE.items() if k[0] != "Deb07-Ops/green-mart"}
n_merged = sum(1 for st, mg in LEDGER.values() if mg)
n_open = sum(1 for st, mg in LEDGER.values() if st == "open" and not mg)
n_closed = sum(1 for st, mg in LEDGER.values() if st == "closed" and not mg)
for name, want, got in (("merged", FACTS["external_merged"], n_merged),
                        ("open", FACTS["external_open"], n_open),
                        ("closed", FACTS["external_closed"], n_closed)):
    if want != got:
        fail("bucket-split", f"ground truth says {name}={want} but the PR table yields {got}")
if n_merged + n_open + n_closed == FACTS["external_prs"]:
    ok("bucket-split", f"external {n_merged} merged + {n_open} open + {n_closed} closed "
                       f"= {FACTS['external_prs']}")
else:
    fail("bucket-split", "external buckets do not sum to the PR total")

# ───────────────────────── 6. arithmetic the reader can perform ─────────────────────────

def has_number(n):
    return re.search(rf"(?<![\d,]){re.escape(str(n))}(?![\d,])", raw) is not None

# The opening bullet is the page's headline claim, so parse the sentence itself
# rather than asking whether the digits appear somewhere in the document. The
# previous version tested has_number(13) - the no-access repository count - while
# the page states 14, so it warned on a correct page and would not have caught a
# wrong one, because "does this number occur anywhere" is close to meaningless.
m = re.search(r"\*\*(\d+)\s+pull requests to repositories I don't own\*\*"
              r"[,\s]*across\s*\*\*(\d+) repositor", raw)
if not m:
    fail("headline-claim",
         "the opening bullet states no third-party PR and repository count, so the "
         "page has no headline figure left to verify")
elif (int(m.group(1)), int(m.group(2))) != (FACTS["third_party_prs"],
                                            FACTS["third_party_repos"]):
    fail("headline-claim",
         f"opening bullet claims {m.group(1)} PRs across {m.group(2)} repositories; "
         f"ground truth is {FACTS['third_party_prs']} across {FACTS['third_party_repos']}")
else:
    ok("headline-claim",
       f"{m.group(1)} PRs across {m.group(2)} repositories, matches ground truth")

if (FACTS["own_merged"] + FACTS["collaborator_merged"] + FACTS["external_merged"]
        == FACTS["prs_merged_alltime"]):
    ok("arith-merges",
       f"{FACTS['own_merged']} own + {FACTS['collaborator_merged']} collaborator "
       f"+ {FACTS['external_merged']} no-access = {FACTS['prs_merged_alltime']} total merges")
else:
    fail("arith-merges",
         f"{FACTS['own_merged']} + {FACTS['external_merged']} != "
         f"{FACTS['prs_merged_alltime']} - ground truth is internally inconsistent")

if FACTS["own_total"] + FACTS["third_party_prs"] == FACTS["prs_authored_alltime"]:
    ok("arith-authored",
       f"{FACTS['own_total']} own + {FACTS['third_party_prs']} third-party "
       f"= {FACTS['prs_authored_alltime']} authored")
else:
    fail("arith-authored", "authored total does not reconcile")

if (FACTS["own_merged"] + FACTS["own_open"] + FACTS["own_closed"]
        != FACTS["own_total"]):
    fail("arith-own",
         f"{FACTS['own_merged']} merged + {FACTS['own_open']} open + "
         f"{FACTS['own_closed']} closed != {FACTS['own_total']} own-repo total")
else:
    ok("arith-own",
       f"{FACTS['own_merged']} + {FACTS['own_open']} + {FACTS['own_closed']} "
       f"= {FACTS['own_total']} own-repository PRs")

# ───────────────────────── 6a. arithmetic the page shows the reader ─────────────────────────

# The page prints its own sums, so a reader can check them. Verify they are true.
for m in re.finditer(r"`(\d+(?:\s*\+\s*\d+)+)\s*=\s*(\d+)`", raw):
    lhs = [int(x) for x in re.split(r"\s*\+\s*", m.group(1))]
    rhs = int(m.group(2))
    if sum(lhs) != rhs:
        fail("shown-arithmetic", f"page prints '{m.group(1)} = {rhs}' but that sums to {sum(lhs)}")
    elif rhs != FACTS["external_prs"]:
        fail("shown-arithmetic",
             f"page prints a sum totalling {rhs}; the verified upstream total is "
             f"{FACTS['external_prs']}")
    else:
        ok("shown-arithmetic", f"'{m.group(1)} = {rhs}' is arithmetically true and matches ground truth")

# "16 PRs = 15 distinct fixes = 13 repositories"
m = re.search(r"`?\*\*`?(\d+) PRs = (\d+) distinct (?:fixes|changes) = (\d+) repositor", raw)
if not m:
    warn("shown-identity", "the PRs/fixes/repositories identity line is absent")
else:
    n_prs, n_fixes, n_repos = (int(m.group(i)) for i in (1, 2, 3))
    real_prs = FACTS["third_party_prs"]
    real_repos = FACTS["third_party_repos"]
    # distinct fixes = PRs, minus each same-branch duplicate pair counted once
    dupes = 1 if "one fix opened twice" in raw else 0
    real_fixes = real_prs - dupes
    for label, claimed, real in (("PRs", n_prs, real_prs),
                                 ("fixes", n_fixes, real_fixes),
                                 ("repositories", n_repos, real_repos)):
        if claimed != real:
            fail("shown-identity",
                 f"page claims {claimed} {label}; the verified figure is {real}")
    if n_prs == real_prs and n_fixes == real_fixes and n_repos == real_repos:
        ok("shown-identity", f"{n_prs} PRs = {n_fixes} distinct fixes = {n_repos} repositories, all match")

# ───────────────────────── 6b. the own/upstream merge split, read from the prose ─────────────────────────

flat = re.sub(r"\n>\s*", " ", raw)          # unwrap the blockquote
m = re.search(r"(\d+)\s+of the\s+(\d+)\s+merges went to a\s+repository I could already push to", flat)
# 147 = own_merged + collaborator_merged: everything the viewer could already push to
if not m:
    fail("own-split", "the page never states how many merges went into an own repo")
else:
    pushable = FACTS["own_merged"] + FACTS["collaborator_merged"]
    if (int(m.group(1)), int(m.group(2))) != (pushable, FACTS["prs_merged_alltime"]):
        fail("own-split",
             f"page says {m.group(1)} of {m.group(2)} merges were to pushable repos; "
             f"ground truth is {pushable} of {FACTS['prs_merged_alltime']}")
    else:
        ok("own-split", f"{m.group(1)} of {m.group(2)} merges were to pushable repos "
                        f"({FACTS['own_merged']} own + {FACTS['collaborator_merged']} collaborator)")

m3 = re.search(r"Of the\s+(\d+)\s+pull requests to my own\s+repositor(?:ies|ies and orgs)", flat)
if not m3:
    fail("own-count", "the page never states how many PRs went to the author's own repositories")
else:
    own_prs, own_open_p, own_closed_p = (int(m3.group(1)),
        *(int(x) for x in re.search(r"(\d+) are still open and (\d+) were closed", flat).groups()))
    if own_prs != FACTS["own_total"]:
        fail("own-count", f"page says {own_prs} own-repository PRs; ground truth is {FACTS['own_total']}")
    elif (own_open_p, own_closed_p) != (FACTS["own_open"], FACTS["own_closed"]):
        fail("own-count", f"page says {own_open_p} open / {own_closed_p} closed; ground truth is "
                          f"{FACTS['own_open']} / {FACTS['own_closed']}")
    elif own_prs != FACTS["own_merged"] + own_open_p + own_closed_p:
        fail("own-count", "own-repository states do not sum to the stated total")
    else:
        ok("own-count", f"{own_prs} own PRs = {FACTS['own_merged']} merged + {own_open_p} open "
                        f"+ {own_closed_p} closed, all match")

m2 = re.search(r"leaves\s+\*\*(\d+)\*\*\s+as the merge count for\s+repositories I have no write access", flat)
if not m2:
    fail("own-split", "the page never states the resulting upstream merge count")
elif int(m2.group(1)) != FACTS["external_merged"]:
    fail("own-split",
         f"page says the upstream merge count is {m2.group(1)}; ground truth is "
         f"{FACTS['external_merged']}")
else:
    ok("own-split", f"upstream merge count {m2.group(1)}, matches ground truth")

# ───────────────────────── 7. links resolve ─────────────────────────

urls = set()
for m in re.findall(r'(?:href|src)="(https?://[^"]+)"', raw):
    # Decode ONLY the ampersand entity. A full html.unescape() corrupts URLs:
    # "&section=header" decodes to "§ion=header" (&sect is the section sign),
    # and "&cent=true" to "¢er=true" (&cent), producing phantom 404s.
    urls.add(m.replace("&amp;", "&"))
for m in re.findall(r"https?://[^\s\"'<>)\]]+", raw):
    urls.add(m.replace("&amp;", "&"))

BOT_BLOCKED = {"linkedin.com", "www.linkedin.com", "cuboidsoft.in", "www.cuboidsoft.in"}
if NET:
    bad = []
    good_badges = 0
    for u in sorted(urls):
        if any(b in u for b in BOT_BLOCKED):
            warn("url", f"{u} - bot-blocked host, skipped")
            continue
        try:
            # Badge hosts are asked for the body, not just the status. shields.io
            # answers 200 for an endpoint it no longer serves and puts
            # "404: badge not found" in the SVG, so a HEAD-only check certifies a
            # broken badge. This was found the hard way: the Repositories badge had
            # been returning an error body for months and passed every check.
            is_badge = "img.shields.io" in u
            req = urllib.request.Request(
                u, method="GET" if is_badge else "HEAD",
                headers={"User-Agent": "Mozilla/5.0 (compatible; readme-link-check)"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status != 200:
                    bad.append(f"{u} -> {r.status}")
                elif is_badge:
                    body = r.read(4096).decode("utf-8", "replace")
                    for marker in ("badge not found", "inaccessible"):
                        if marker in body:
                            bad.append(f"{u} -> renders {marker!r} despite HTTP 200")
                            break
                    else:
                        if "<svg" not in body:
                            bad.append(f"{u} -> not an SVG")
                        else:
                            good_badges += 1
                    time.sleep(0.3)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 999):
                warn("url", f"{u} -> {e.code} bot-blocked")
            else:
                bad.append(f"{u} -> {e.code}")
        except Exception as e:
            bad.append(f"{u} -> {type(e).__name__}")
    for b in bad:
        fail("url", b)
    ok("url", f"{len(urls)} unique URLs checked, "
       f"{good_badges} badge bodies inspected and rendering a real value")
else:
    warn("url", f"{len(urls)} URLs NOT checked (--offline)")

# ───────────────────────── 8. mobile width risk ─────────────────────────

widths = [int(m.group(1)) for m in re.finditer(r"<td width=\"(\d+)\"", raw, re.I)]
bad_w = [w for w in widths if w < 200]
if bad_w:
    fail("mobile", f"fixed <td width> under 200px forces horizontal scroll at 375px: {bad_w}")
else:
    ok("mobile", f"no fixed <td width> below 200px ({len(widths)} fixed widths, all >=200)")

# ───────────────────────── 9. duplicate sections ─────────────────────────

heads = re.findall(r"^#{2,3} (.+)$", raw, re.M)
dupes = {h for h in heads if heads.count(h) > 1}
if dupes:
    fail("dup-section", f"duplicate headings: {dupes}")
else:
    ok("dup-section", f"{len(heads)} unique headings")

# ───────────────────────── report ─────────────────────────

W = 74
print("=" * W)
print(f"README VALIDATOR  {path}   ({len(raw)} bytes, {len(raw.splitlines())} lines)")
print("=" * W)
for label, rows in (("FAIL", FAIL), ("WARN", WARN), ("PASS", OK)):
    if not rows:
        continue
    print(f"\n{label}  ({len(rows)})")
    for check, detail in rows:
        mark = {"FAIL": "x", "WARN": "!", "PASS": "+"}[label]
        print(f"  [{mark}] {check:14} {detail}")
print("\n" + "=" * W)
# The RESULT line and the exit code must never disagree. Under --strict a warning
# fails the run, and saying "PASSED" immediately before exiting 1 made the CI log
# read as a pass followed by a failure with nothing connecting the two.
strict_fail = bool(WARN) and STRICT
if FAIL or strict_fail:
    detail = f"{len(FAIL)} error(s)"
    if strict_fail:
        detail += f" and {len(WARN)} warning(s) treated as failures by --strict"
    print(f"RESULT: FAILED - {detail}")
    sys.exit(1)
print(f"RESULT: PASSED - {len(OK)} checks, {len(WARN)} warning(s)")
sys.exit(0)