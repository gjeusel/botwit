<p align="center">
  <h1> botwit </h1>
</p>
<p align="center">
  <em>My Twitter Bot.</em>
</p>
<p align="center">
  <a href="https://github.com/gjeusel/botwit/actions?query=workflow%3ACI+branch%3A+main+">
      <img src="https://github.com/gjeusel/botwit/workflows/Test%20Suite/badge.svg?event=push&branch=main" alt="Test Suite" onerror="this.style.display='none'">
  </a>
  <a href="https://coverage-badge.samuelcolvin.workers.dev/redirect/gjeusel/botwit" alt="Test Coverage" onerror="this.style.display='none'">
      <img src="https://coverage-badge.samuelcolvin.workers.dev/gjeusel/botwit.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/botwit/">
      <img src="https://badge.fury.io/py/botwit.svg" alt="Package version" onerror="this.style.display='none'">
  </a>
  <a href="https://gjeusel.github.io/botwit/">
    <img src="https://img.shields.io/badge/mkdocs-pages-brightgreen" alt="MKDocs github page">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
      <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white" alt="pre-commit">
  </a>
</p>
<br/>
</p>

---

## Installation

```bash
pip install botwit
```

### Developper

##### Install

```bash
make install
```

##### Launch tests:

```bash
pytest
```

##### Write docs:

```bash
mkdocs serve --watch .
```

### Update Cookiecutter Template

```bash
cruft update --skip-apply-ask --allow-untracked-files --project-dir .
```
