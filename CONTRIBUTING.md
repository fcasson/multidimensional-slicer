# Contributing

## Licensing

All contributions must be licensable under the [MIT License](LICENSE).

**AI-generated code policy:** The contributor must be in a position to license the code under our licence. "Mechanical work" (e.g. search-and-replace, boilerplate wiring) is generally acceptable. Code with a substantive creative or scientific element requires extra scrutiny because of the risk of reproducing code from other projects verbatim in breach of their licences.

Before submitting any contribution (human- or AI-authored), run the licence and originality checks below.

## Pre-Submission Checks

### 1. ScanCode (licence & originality scan)

ScanCode detects embedded licence/copyright notices and flags code snippets matching known open-source projects.

```bash
# Install (once)
pip install scancode-toolkit

# Run on the project (skips venv and data)
scancode -clipeu --json-pp scan-results.json \
  --ignore ".venv/*" --ignore "*.csv" --only-findings .

# Review findings
python -m json.tool scan-results.json | less
```

Any flagged files must be reviewed and either:
- Confirmed as original / sufficiently transformed, or
- Rewritten to avoid the match, or
- Attributed with proper licence headers if incorporating third-party code.

### 2. REUSE (licence header hygiene)

```bash
pip install reuse
reuse lint
```

Every source file should have an SPDX licence header. See https://reuse.software for details.

### 3. Editor Settings

If using GitHub Copilot or similar AI assistants, enable the **public code filter**:
- VS Code: `"editor.inlineSuggest.filterPublicCode": true`
- This blocks suggestions that match public repositories verbatim.

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
python -m pytest -v

# Launch the app
panel serve app.py --show --autoreload
```

## Tests

All changes must pass the existing test suite (25 tests). Add tests for new functionality.

```bash
python -m pytest -v
```
