#!/usr/bin/env python3
"""URL collection and fetching for validate_readme.py.

Split out of the validator so it can be imported and unit-tested. The network
half of the `url` check cannot be exercised offline, but the half that decides
*which* URL to fetch can - and that half was wrong for a long time without
anything noticing, because a wrong URL and a broken link produce the same
failure and look equally convincing.

Standard library only, so the workflow needs no install step.
"""
import re
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; readme-link-check)"}

# A bare URL, for the markdown-link and plain-text cases an HTML-attribute pass
# cannot see. Parentheses and brackets are allowed when they BALANCE, because
# shields badge text is parenthesised and a regex that stops at the first ")"
# silently truncates:
#
#   .../badge/IELTS%207.5%20(C1     -> shields answers 404: badge not found
#
# That reported a broken badge on a badge that renders perfectly, and it was
# easy to believe, because checking the badge by hand means copying the full URL
# out of the source - which is the one URL the validator never requested. An
# unbalanced ")" or "]" is still a terminator, so markdown's "](url)" closes
# correctly and a stray ")" in prose does not swallow the rest of the line.
#
# The group bodies exclude their own delimiter. Without that the group is greedy
# and runs from the first "(" to the LAST ")" with no whitespace in between, so
# ![x](https://e.com/a%20(b)-c) harvests "https://e.com/a%20(b)-c)" - markdown's
# own closing paren, swallowed. Caught by the suite, which is the only reason it
# is known. One level of nesting is all a badge path needs.
BARE_URL = re.compile(
    r"https?://(?:[^\s\"'<>()\[\]]|\([^()\s\"'<>]*\)|\[[^\[\]\s\"'<>]*\])+")


# Hosts that answer any automated request with a challenge, so a status check
# measures their bot defence rather than the page.
BOT_BLOCKED = {"linkedin.com", "www.linkedin.com", "cuboidsoft.in", "www.cuboidsoft.in"}

# What shields.io puts in an SVG instead of a value. It answers HTTP 200 for an
# endpoint it no longer serves, and "inaccessible" when it cannot reach the data
# source itself - which is what a rate-limited CI runner's request looks like
# from here.
BADGE_MARKERS = ("badge not found", "inaccessible")


def harvest_urls(raw):
    """Every URL on the page, from HTML attributes and from bare text.

    Decode ONLY the ampersand entity. A full html.unescape() corrupts URLs:
    "&section=header" decodes to the section sign followed by "ion=header"
    (&sect), and "&cent=true" to a cent sign followed by "er=true" (&cent),
    producing phantom 404s.
    """
    found = set()
    for pat in (r'(?:href|src)="(https?://[^"]+)"', BARE_URL):
        for m in re.findall(pat, raw):
            found.add(m.replace("&amp;", "&"))
    return found


def is_bot_blocked(url):
    return any(b in url for b in BOT_BLOCKED)


def badge_body(url, attempts=2, opener=None, sleeper=None):
    """(body, marker) for a badge, re-fetched once if it looks like an error.

    A marker must survive two consecutive fetches before it counts, because a
    single fetch can catch a rate limit or a cold cache and fail a build over a
    badge that is fine. A genuinely dead endpoint still trips it: the
    img.shields.io/github/repos endpoint returns the marker on every fetch,
    which is the case this exists for.

    The retry is not a licence to believe one bad fetch, and it is worth being
    precise about why it is here at all. Two parenthesised badges were once
    reported as broken. They were not transient: harvest_urls() was truncating
    them at the ")", so this function was asked about a URL that could not
    exist, and it answered correctly. Checking a badge by hand means copying the
    full URL out of the source, which is the one URL this function was never
    given - so the report looked like a false positive and nearly was treated as
    one. Retry does not excuse a wrong URL; that is fixed where the URL is built.

    opener and sleeper are injectable so the retry behaviour can be tested
    without a network or a real delay.
    """
    opener = opener or urllib.request.urlopen
    sleeper = sleeper if sleeper is not None else time.sleep
    body, marker = "", None
    for i in range(attempts):
        req = urllib.request.Request(url, method="GET", headers=UA)
        with opener(req, timeout=15) as r:
            body = r.read(4096).decode("utf-8", "replace")
        marker = next((m for m in BADGE_MARKERS if m in body), None)
        if marker is None:
            return body, None
        if i + 1 < attempts:
            sleeper(2.0)
    return body, marker


def fetch_ok(url, attempts=2, opener=None, sleeper=None):
    """(ok, detail) for a non-badge URL, retried before it is believed.

    Retried for the same shared-egress reason as a badge body, and for one
    specific case: the profile summary cards are a serverless render, so the
    first request after a quiet period compiles the function, and that exceeded
    the timeout on a resource which then answered 200 immediately. A resource
    that never answers is still a failure; this only stops one slow response
    from failing a build on its own.
    """
    opener = opener or urllib.request.urlopen
    sleeper = sleeper if sleeper is not None else time.sleep
    last = None
    for i in range(attempts):
        req = urllib.request.Request(url, method="HEAD", headers=UA)
        try:
            with opener(req, timeout=25) as r:
                if r.status == 200:
                    return True, 200
                last = r.status
        except urllib.error.HTTPError as e:
            return False, e.code
        except Exception as e:            # timeout, DNS, TLS, reset
            last = type(e).__name__
        if i + 1 < attempts:
            sleeper(2.0)
    return False, last
