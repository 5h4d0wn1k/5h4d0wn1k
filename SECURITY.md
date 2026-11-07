# Security Policy

This repository is the GitHub profile page for [`5h4d0wn1k`](https://github.com/5h4d0wn1k):
a `README.md` rendered on the profile, plus a small amount of repository
automation under `.github/`. It contains **no application code, no build step,
and no runtime**, so there is no service to exploit here.

That does not mean there is nothing to attack. This policy explains what does
fall inside scope.

## Scope

| Surface | What could go wrong |
|---|---|
| **Third-party media** | The README embeds dozens of remote images and badges (shields.io, capsule-render, readme-typing-svg, komarev, ghchart, github-profile-summary-cards). A compromised or impersonating host could serve tracking pixels or content that misrepresents this profile. |
| **Repository automation** | `.github/workflows/readme-health.yml` runs on `pull_request`, `push`, and a weekly schedule. Proposed workflow changes are a supply-chain surface. |
| **Contact details** | The README publishes a plaintext email address. Spoofing, impersonation, or phishing that abuses this profile or that address is in scope. |
| **Outbound links** | Links that have been hijacked, typosquatted, or redirected somewhere they should not go. |
| **Account-level** | Lookalike accounts, impersonation of this profile, or forged attribution of work published here. |

**Out of scope:** vulnerabilities in the projects *linked* from this page. Those
belong to their own repositories — report them there, or through the relevant
maintainer or CVE program. Generic badge/bot spam and social-engineering
attempts against the maintainer are also out of scope.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

1. **Preferred:** GitHub private vulnerability reporting —
   [**Security → Report a vulnerability**](https://github.com/5h4d0wn1k/5h4d0wn1k/security/advisories/new).
2. **Alternative:** email **nikhilnagpure203@gmail.com** with `SECURITY` in the subject.

Please include what you found, where it is (file and line, or URL), how to
reproduce it, and the impact you believe it has.

## What to expect

| Stage | Target |
|---|---|
| Acknowledgement | within **3 business days** |
| Initial assessment | within **7 days** |
| Fix or documented decision | within **30 days** for confirmed issues |

This is maintained by one person, not a staffed security team. These are honest
targets, not a contractual SLA.

## Disclosure

Please allow a reasonable window to fix the issue before publishing. **90 days**
from acknowledgement is the default. I will coordinate with you and credit you by
name — or anonymously, if you prefer — once a fix is in place.

## No bounty

This repository has no bug-bounty program and no budget. I cannot pay for
reports, and this policy will not pretend otherwise.

## Safe harbour

If you act in good faith under this policy — no data exfiltration, no
denial-of-service, no access to accounts or data that are not yours, no
disruption to other users — I will not pursue legal action or report you to
GitHub for your research.
