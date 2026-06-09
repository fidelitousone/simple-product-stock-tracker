#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

PRODUCT_ID = 207987
API_URL = f"https://protectli.com/wp-json/wc/store/v1/products/{PRODUCT_ID}"
PRODUCT_PAGE = "https://protectli.com/product/vp2430/"
PRODUCT_NAME = "Protectli VP2430"
STATE_FILE = "last_status.json"


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

REQUEST_TIMEOUT = 20  # seconds


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def parse_stock(data):
    """
    Extract the in-stock bool from a decoded Store API payload.

    Return True/False, or None if the payload does not let us determine it.
    None means 'unknown', and the caller must never treat it as a change.
    Pure function (no I/O) so the parsing rules can be tested directly.
    """
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict) or "is_in_stock" not in data:
        log("Response missing 'is_in_stock'; treating as unknown.")
        return None

    return bool(data["is_in_stock"])


def fetch_stock():
    """
    Return True/False for in-stock, or None if we could not determine it.
    None means 'unknown', and the caller must never treat it as a change.
    """
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                log(f"Unexpected HTTP status {resp.status}; treating as unknown.")
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        log(f"Request failed: {e}; treating as unknown.")
        return None
    except json.JSONDecodeError as e:
        log(f"Could not parse JSON: {e}; treating as unknown.")
        return None

    return parse_stock(data)


def load_previous():
    """Return the last known in-stock bool, or None if there is no state yet."""
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE) as f:
            return bool(json.load(f).get("in_stock"))
    except (json.JSONDecodeError, OSError) as e:
        log(f"Could not read state file: {e}; treating previous as unknown.")
        return None


def save_state(in_stock):
    with open(STATE_FILE, "w") as f:
        json.dump(
            {
                "in_stock": in_stock,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )


def should_notify(current, previous):
    """Alert only on a rising edge into in-stock (never when already in stock)."""
    return current and previous is not True


def notify():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        log("NTFY_TOPIC not set; skipping notification.")
        return
    body = f"{PRODUCT_NAME} is BACK IN STOCK. Order now: {PRODUCT_PAGE}".encode("utf-8")
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body,
        headers={
            "Title": f"{PRODUCT_NAME} in stock",
            "Priority": "urgent",
            "Tags": "rotating_light,shopping",
            "Click": PRODUCT_PAGE,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            log(f"Notification sent (HTTP {resp.status}).")
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        log(f"Failed to send notification: {e}")


def main():
    current = fetch_stock()
    if current is None:
        log("Stock status unknown this run; leaving state unchanged, no alert.")
        return 0  # a transient failure should not fail the whole job

    previous = load_previous()
    log(f"Previous: {previous} | Current: {'in stock' if current else 'out of stock'}")

    if should_notify(current, previous):
        log("Item is available -> sending alert.")
        notify()

    save_state(current)
    return 0


if __name__ == "__main__":
    sys.exit(main())
