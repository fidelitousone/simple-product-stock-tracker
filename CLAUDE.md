# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-file Python stock checker for the Protectli VP2430. It polls the
WooCommerce Store API, and when the item flips from not-in-stock to in-stock it
sends a push notification via [ntfy.sh](https://ntfy.sh). It runs on a schedule
in GitHub Actions and persists state between runs by committing a JSON file back
to the repo.

## Commands

```bash
# Run a check locally (no notification unless NTFY_TOPIC is set)
python check_stock.py

# Run with notifications enabled
NTFY_TOPIC=your-topic python check_stock.py

# Run the test suite
python -m unittest -v
```

There is no build step and no dependency install (stdlib only — `urllib`,
`unittest`). The script targets Python 3.12 (the version pinned in CI). Tests
live in `test_check_stock.py` and run in CI via `.github/workflows/tests.yml` on
push/PR — separate from the scheduled stock-check workflow.

## Architecture

Everything lives in `check_stock.py`. The flow in `main()`:

1. `fetch_stock()` — GET the Store API and JSON-decode it, then delegate to the
   pure `parse_stock(data)` helper, which returns `True`/`False` for
   `is_in_stock` or `None` if the status could not be determined.
2. `load_previous()` — read the last known bool from `last_status.json`.
3. `should_notify(current, previous)` — pure rising-edge rule
   (`current and previous is not True`); notify only when it returns true.
4. `save_state()` — write the new status + timestamp back to `last_status.json`.

`parse_stock` and `should_notify` are deliberately I/O-free so the tests in
`test_check_stock.py` can exercise the parsing rules and notification logic
without network or filesystem access.

### The `None`/"unknown" invariant

`parse_stock()` (via `fetch_stock()`) and `load_previous()` return `None` for *any* uncertainty —
non-200 status, network error, malformed JSON, missing `is_in_stock`, or no
state file yet. `None` must never be treated as a status change: when
`fetch_stock()` returns `None`, `main()` leaves state untouched, sends no alert,
and **still exits 0** so a transient upstream failure never fails the CI job.
Preserve this when modifying logic — collapsing `None` into `False` would cause
false "out of stock" transitions and spurious alerts.

### State persistence via git

`last_status.json` is the durable memory across runs. The GitHub Action
(`.github/workflows/check-stock.yml`) commits it back to the repo after each run
(with `[skip ci]` to avoid re-triggering). This is why CI needs
`contents: write` and why the workflow only commits when the file actually
changed. The file is not present in a fresh checkout until the first run creates
it.

## Configuration

- Product is hard-coded at the top of `check_stock.py` (`PRODUCT_ID`, `API_URL`,
  `PRODUCT_PAGE`, `PRODUCT_NAME`). Changing the watched product means editing
  these constants.
- `NTFY_TOPIC` (env var / GitHub secret) selects the ntfy.sh topic. If unset,
  the script runs normally but skips the notification.
- Poll cadence is the `cron` in the workflow (currently `0 13 * * *`, daily at
  13:00 UTC). `workflow_dispatch` allows manual runs.
- Requests send a browser-like `User-Agent`; the Store API may reject the
  default urllib agent.
