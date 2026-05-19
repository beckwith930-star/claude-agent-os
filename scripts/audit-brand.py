#!/usr/bin/env python3
"""
audit-brand.py — scan BRAND.md for canonical sections and flag gaps.

Spec: ~/.agent-os/agents/brand-auditor.md

Exit codes:
  0 — all canonical sections present with content
  1 — one or more sections missing or thin
  2 — BRAND.md not found
"""

import re
import sys
from datetime import date
from pathlib import Path

BRAND_MD = Path.home() / ".agent-os" / "BRAND.md"
CONTENT_THRESHOLD = 50  # chars of actual content under a header to count as "present"

# Canonical sections. Order matters — printed top-down.
# (header_regex, display_name, suggested_persona, drafting_guidance)
CANONICAL_SECTIONS = [
    (
        r"^##\s+Identity\b",
        "Identity",
        "solo-founder",
        "Name, role, contact, public surface.",
    ),
    (
        r"^##\s+Mission\b",
        "Mission",
        "solo-founder",
        "Single sentence, 12-20 words. Why we exist.",
    ),
    (
        r"^##\s+Vision\b|^##\s+North\s+Star\b|^##\s+Vision\s*/?\s*North\s+Star\b",
        "Vision / North Star",
        "solo-founder",
        "The future state we're building toward.",
    ),
    (
        r"^##\s+Anti-mission\b|^##\s+What\s+we\s+don't\s+do\b",
        "Anti-mission",
        "solo-founder",
        "What we explicitly don't do. 3-5 bullets.",
    ),
    (
        r"^##\s+Ideal\s+Customer\s+Profile\b|^##\s+ICP\b",
        "ICP",
        "solo-founder + marketing",
        "Segment, buyer, comp range, vertical.",
    ),
    (
        r"^##\s+Anti-ICP\b|^##\s+Who\s+we\s+don't\s+sell\s+to\b",
        "Anti-ICP",
        "solo-founder",
        "Buyer types we explicitly skip.",
    ),
    (
        r"^##\s+What\s+I?\s*sell\b|^##\s+Products?\b",
        "What we sell",
        "solo-founder + finance",
        "Products, pricing, packaging.",
    ),
    (
        r"^###?\s+(?:The\s+)?strategic\s+model\b",
        "Strategic model",
        "solo-founder",
        "Land / retain / expand math.",
    ),
    (
        r"^##\s+Voice\s+principles\b",
        "Voice principles",
        "gtm-engineer + solo-founder",
        "How we sound. Cross-ref SOUL.md.",
    ),
    (
        r"^##\s+(?:Things\s+I?\s*never\s+do|Anti-patterns)\b",
        "Anti-patterns",
        "solo-founder",
        "What we never write/do.",
    ),
    (
        r"^##\s+Off-limits\s+prospects\b",
        "Off-limits prospects",
        "solo-founder",
        "Industry conflict zone. Refs off-limits.md.",
    ),
    (
        r"^##\s+Brand-doc\s+maintenance\b",
        "Brand-doc maintenance",
        "brand-auditor",
        "Last reviewed + audit cadence.",
    ),
]


def section_has_content(text, header_pattern):
    """True if a section header matches AND has >CONTENT_THRESHOLD chars before the next ##."""
    match = re.search(header_pattern, text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return False
    start = match.end()
    next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
    end = start + next_header.start() if next_header else len(text)
    body = text[start:end].strip()
    return len(body) > CONTENT_THRESHOLD


def main():
    if not BRAND_MD.exists():
        print(f"✗ BRAND.md not found at {BRAND_MD}")
        return 2

    text = BRAND_MD.read_text()

    present = []
    missing = []
    for pattern, name, persona, guidance in CANONICAL_SECTIONS:
        if section_has_content(text, pattern):
            present.append(name)
        else:
            missing.append((name, persona, guidance))

    print(f"# Brand Doc Audit — {date.today().isoformat()}")
    print()
    print(f"Source: {BRAND_MD}  ({BRAND_MD.stat().st_size:,} bytes)")
    print()
    print(f"## ✓ Present ({len(present)} of {len(CANONICAL_SECTIONS)})")
    for name in present:
        print(f"  - {name}")
    print()
    if missing:
        print(f"## ⚠ Missing or thin ({len(missing)})")
        for name, persona, guidance in missing:
            print(f"  - **{name}** → load `{persona}` — {guidance}")
        print()
        print("## Recommended next step")
        first_name, first_persona, first_guidance = missing[0]
        print(f'  Operator: "Load {first_persona}. Draft a {first_name} for <VENTURE>. {first_guidance}"')
        return 1
    else:
        print("## All canonical sections present and have content. ✓")
        return 0


if __name__ == "__main__":
    sys.exit(main())
