# Security Policy

## Scope

This repository holds a profile `README.md`, a Python validator, and one GitHub
Actions workflow. There is no application code, no package manifest, no
database, and no credential of any kind — `permissions: contents: read` is the
only permission the workflow holds.

So there is very little here to exploit, and a report that describes an attack
against "the site" is almost certainly aimed at something that does not exist
in this repository. Those reports are welcome, and the answer will usually be
that the surface is empty.

## What is actually in scope

**1. The workflow.** It runs on `pull_request`, `push` to `main`, and weekly on
a schedule. It holds one permission, `contents: read`, and it executes code from
the repository — the validator in `scripts/`, which parses `README.md` and, for
the link check, makes outbound HTTP requests — alongside three third-party
actions, pinned to commit SHAs.

- A vulnerability in `scripts/validate_readme.py` or `scripts/readme_urls.py`
  that lets a pull request's content execute code, exfiltrate
  `GITHUB_TOKEN`, or write outside the workspace.
- A supply-chain path to the pinned actions — a compromised tag, a hijacked
  maintainer account, or a dependency confusion in the Python imports.
- Anything that makes `permissions: contents: read` behave as more than read.

**2. The third-party image hosts.** The README is mostly remote images, which
means every page view tells a third party the reader's IP address and user
agent, and passes the badge path along in the URL. The current set is
`img.shields.io` (46), `github-profile-summary-cards.vercel.app`,
`streak-stats.demolab.com`, `capsule-render.vercel.app`, `komarev.com`,
`ghchart.rshah.org` and `readme-typing-svg.demolab.com`.

- A new host being added that is not on that list, without it being noted.
- A host compromised in a way that serves hostile content in place of a badge.
- A query string on any of those URLs that starts carrying a secret, a token,
  or an identifier that is not already public in the README.

**3. The workflow's own gates.** The health check is the only automated review
in this repository, so a way to make it pass while the page is wrong is worth
reporting: a validator check that cannot fail, a mutation suite entry that no
longer applies, or a check that has been made advisory without saying so in the
same commit.

**4. Personal contact details.** The README publishes an email address and a
LinkedIn handle in plaintext. That is a deliberate choice, but scraping them is
not, and it is worth a report if you see it happening at scale.

## Out of scope

- The projects this account has built. They are separate repositories with their
  own disclosure routes — and their own maintainers, who are the people to tell.
- Vulnerabilities in shields.io, Vercel, or any other host listed above. Report
  those to the host, not here.
- Missing hardening suggestions with no demonstrated impact. Pull requests
  asking for improvements are welcome, but they do not need to go through this
  process.
- The content of the README as such. Disagreement with a claim on the page is an
  [issue](https://github.com/5h4d0wn1k/5h4d0wn1k/issues), not a vulnerability.

## Reporting

Use **GitHub private vulnerability reporting** on this repository — the
*Security* tab → *Report a vulnerability*. It opens a private thread visible
only to the maintainer, which avoids putting a live exploit description in a
public issue.

If that is unavailable, or you need to attach something, email
[nikhilnagpure203@gmail.com](mailto:nikhilnagpure203@gmail.com) — the address
already published in the README.

Please include:

- what an attacker gains, not only what breaks;
- the file and line, or the commit;
- how to reproduce it, ideally a `curl` command or a pull request on a fork;
- whether it is already public anywhere.

Please give a reasonable window to fix before disclosing. There is one
maintainer and no on-call rotation, so a week is usually enough, and asking for
more is fine.

### What happens next

| Step | What to expect |
|---|---|
| Acknowledged | Within a few days |
| Triaged | A fix, or an explanation of why it is not a vulnerability |
| Fixed | A pull request, linked from the report |
| Credit | Whatever you ask for, including nothing |

Reports are not met with a legal threat, a takedown demand, or an NDA request.
If disclosure turns out to be a risk to someone who reported in good faith, that
is a conversation to have explicitly, not a default.

## Supported versions

There is nothing to install and no released version. `main` is the only thing
that exists, and it is what gets fixed.
