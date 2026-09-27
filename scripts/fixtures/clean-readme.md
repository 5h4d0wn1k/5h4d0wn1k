# Fixture

This file is **not** the profile. It is a deliberately small, self-contained
README used as the base document by `test_validate_readme.py`.

It exists because the suite used to mutate the live `README.md`. That coupled
every seed to the exact prose of the page, so editing a heading or rewording a
bullet silently killed the seeds that targeted it — 20 of 37 went no-op the
first time the page changed under them, and a suite full of no-op seeds still
reports green while proving nothing. A committed fixture only changes when
somebody deliberately changes it.

It is written to pass every hard check, so a seed that injects a defect is
caught by the check that ought to catch it and by nothing else.

Deliberately omitted, because no hard check needs them and each one would drag
in ground truth that has nothing to do with the check under test: the real
contribution figures, the analytics table, the tech-stack badges.

## 🧰 Tech Stack

<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />

<table>
  <tr>
    <td width="200" align="center"><b>Identity</b></td>
    <td><b>Nikhil Nagpure</b> · <code>5h4d0wn1k</code></td>
  </tr>
</table>

## 🌍 Open Source Contributions

### ✅ Merged upstream — 1

- **SymPy** — [solve domain fix](https://github.com/sympy/sympy/pull/30567) (merged)

### Open — 1

- **scipy** — [graph.copy() necessity](https://github.com/scipy/scipy/pull/26242) (open)
