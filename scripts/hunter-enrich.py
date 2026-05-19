#!/usr/bin/env python3
"""
hunter-enrich.py — find verified emails via the Hunter.io API.

CLI:
  python3 hunter-enrich.py "Stefan Bradham" remixconsulting.com
  python3 hunter-enrich.py "Stefan Bradham" remixconsulting.com remixconsultingllc.com
  python3 hunter-enrich.py --account                # quota check
  python3 hunter-enrich.py --clear-cache            # reset cached lookups

Module:
  from hunter_enrich import find_email
  result = find_email("Stefan", "Bradham", ["remixconsulting.com", "remixconsultingllc.com"])
  # → { "email": "stefan@remixconsulting.com", "score": 95, "status": "valid", "domain": "remixconsulting.com" }
  # or None if no match found above the confidence threshold

Auth: reads key from ~/.agent-os/secrets/hunter-api-key.txt (600 perms).
Cache: ~/.agent-os/secrets/hunter-cache.json — lookups cached forever
       to avoid burning quota on re-runs. Clear with --clear-cache.

Quota: free tier is 75 lookups/month. Each find_email call costs 1.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SECRETS_DIR = Path.home() / ".agent-os" / "secrets"
KEY_FILE = SECRETS_DIR / "hunter-api-key.txt"
CACHE_FILE = SECRETS_DIR / "hunter-cache.json"

# Confidence threshold — Hunter scores 0-100. >= 70 = use the address.
MIN_SCORE = 70


def load_key():
    if not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Hunter API key missing at {KEY_FILE}. "
            "Save your key with: cat > {KEY_FILE} && chmod 600 {KEY_FILE}"
        )
    return KEY_FILE.read_text().strip()


def load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))
    CACHE_FILE.chmod(0o600)


def cache_key(first, last, domain):
    return f"{first.lower()}|{last.lower()}|{domain.lower()}"


def _api(url):
    """Single GET. Returns parsed JSON or raises.
    Sends a real-browser User-Agent because Hunter's WAF rejects
    Python's default urllib UA with 403."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "<NS>-hunter-enrich/1.0 (https://<YOUR_DOMAIN>)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def find_email(first_name, last_name, domains, use_cache=True):
    """
    Look up an email via Hunter.io. Tries each domain in order, returns the
    first one above MIN_SCORE. Returns None if no candidate scores high enough.
    """
    if isinstance(domains, str):
        domains = [domains]

    cache = load_cache() if use_cache else {}
    key = load_key()
    best = None

    for domain in domains:
        ck = cache_key(first_name, last_name, domain)
        if use_cache and ck in cache:
            cached = cache[ck]
            if cached and cached.get("score", 0) >= MIN_SCORE:
                return cached
            if not best and cached:
                best = cached
            continue

        params = urllib.parse.urlencode({
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": key,
        })
        url = f"https://api.hunter.io/v2/email-finder?{params}"
        try:
            resp = _api(url)
        except Exception as e:
            print(f"  ⚠ Hunter API error for {first_name} {last_name} @ {domain}: {e}", file=sys.stderr)
            continue

        data = resp.get("data") or {}
        email = data.get("email")
        if not email:
            cache[ck] = None
            continue

        result = {
            "email": email,
            "score": data.get("score", 0),
            "status": (data.get("verification") or {}).get("status", "unknown"),
            "result": (data.get("verification") or {}).get("result", "unknown"),
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
        }
        cache[ck] = result
        if result["score"] >= MIN_SCORE:
            save_cache(cache)
            return result
        if not best or result["score"] > (best.get("score") or 0):
            best = result

    save_cache(cache)
    # No domain hit the threshold — return the best low-confidence guess if any
    return best


def account_info():
    key = load_key()
    url = f"https://api.hunter.io/v2/account?api_key={key}"
    return _api(url).get("data", {})


def main():
    parser = argparse.ArgumentParser(description="Hunter.io email enrichment.")
    parser.add_argument("name", nargs="?", help='Full name, e.g. "Stefan Bradham"')
    parser.add_argument("domains", nargs="*", help="One or more domains to try, in priority order")
    parser.add_argument("--account", action="store_true", help="Show account info / quota and exit")
    parser.add_argument("--clear-cache", action="store_true", help="Clear the local lookup cache and exit")
    args = parser.parse_args()

    if args.clear_cache:
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            print(f"✓ Cleared cache at {CACHE_FILE}")
        else:
            print("(cache was already empty)")
        return 0

    if args.account:
        info = account_info()
        print(f"Account:       {info.get('email', '?')}")
        print(f"Plan:          {info.get('plan_name', '?')}")
        searches = info.get("calls", {}) or info.get("requests", {}).get("searches", {})
        verifs = info.get("verifications", {}) or info.get("requests", {}).get("verifications", {})
        print(f"Searches used: {searches.get('used', '?')} / {searches.get('available', '?')}")
        print(f"Verif. used:   {verifs.get('used', '?')} / {verifs.get('available', '?')}")
        return 0

    if not args.name or not args.domains:
        parser.print_help()
        return 1

    parts = args.name.strip().split()
    if len(parts) < 2:
        print(f"✗ Need at least first + last name. Got: {args.name!r}", file=sys.stderr)
        return 1
    first, last = parts[0], " ".join(parts[1:])

    result = find_email(first, last, args.domains)
    if result and result["score"] >= MIN_SCORE:
        print(f"✓ {result['email']}  (score {result['score']}, {result['status']}, via {result['domain']})")
        return 0
    if result:
        print(f"⚠ Best guess (below threshold): {result['email']} (score {result['score']}) — verify manually")
        return 2
    print(f"✗ No match found for {first} {last} on {args.domains}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
