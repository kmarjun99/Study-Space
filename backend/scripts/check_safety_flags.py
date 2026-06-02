"""Pre-deploy safety check.

Fails (exit code 1) if any of the production accounting flags are ON in the
current `tax_config`. Intended uses:

  - CI gate before merging to `main` or before a `cloudbuild` push
  - Manual `python -m scripts.check_safety_flags` from the dev machine
  - Cron heartbeat that posts to Slack if a flag flipped without sign-off

The list of "dangerous" flags is hardcoded here on purpose. The whole point
is that it MUST be edited in a separate, reviewed PR to allow each flag to
go live — that PR is the human gate.

Exit codes:
  0 — all dangerous flags OFF (safe to deploy)
  1 — at least one flag is ON (deploy blocked)
  2 — could not connect to the DB / something went wrong
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.tax_config import TaxConfig  # noqa: E402


# Flags that MUST remain OFF until the canary + CA sign-off + staging
# rehearsal gates have all passed. Each entry is (key, expected_value).
PROTECTED_FLAGS: list[tuple[str, object]] = [
    ("accounting.enabled",              False),
    ("feature.gst_invoices",            False),
    ("feature.credit_notes",            False),
    ("feature.recurring_maintenance",   False),
    ("feature.per_listing_price_mode",  False),
    ("settlement.offset_maintenance",   False),
    ("tcs.enabled",                     False),
    ("tds.section_194o_enabled",        False),
    # Phase 1 intelligence (event firehose stays OFF until Phase 1 reviewed)
    ("events.enabled",                  False),
    # Phase 2 intelligence (profile aggregation stays OFF until Phase 2 reviewed)
    ("intelligence.profile_aggregation_enabled", False),
    # Phase 3 intelligence (recommendations stay OFF until Phase 3 reviewed)
    ("recommendations.enabled",                  False),
    # Phase 4A intelligence (segments stay OFF until Phase 4A reviewed)
    ("segments.enabled",                         False),
    # Phase 4B intelligence (campaigns stay OFF until Phase 4B reviewed)
    ("campaigns.enabled",                        False),
    # Phase 4C intelligence (notification automation stays OFF until Phase 4C reviewed)
    ("notification_automation.enabled",          False),
    # Phase 4D intelligence (reco attribution stays OFF until Phase 4D reviewed)
    ("recommendations.attribution_enabled",      False),
    # Phase 5 intelligence (insight dashboards stay OFF until Phase 5 reviewed)
    ("insights.enabled",                         False),
    # Phase 6 intelligence (experiments + ML feature export stay OFF)
    ("experiments.enabled",                      False),
    ("ml.feature_export_enabled",                False),
]


# ---------- color helpers --------------------------------------------------

_USE_COLOR = sys.stdout.isatty()
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _USE_COLOR else text


# ---------- core check -----------------------------------------------------

async def check(allow: set[str] | None = None) -> int:
    """Return 0 if safe, 1 if any flag is on, 2 on infra error.

    `allow` is an opt-in set of flag keys that the caller has explicitly
    overridden (e.g., via `--allow accounting.enabled` after CA sign-off).
    """
    allow = allow or set()

    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(TaxConfig).where(
                    TaxConfig.key.in_([k for k, _ in PROTECTED_FLAGS])
                )
            )).scalars().all()
    except Exception as exc:
        print(_c(_RED, f"  ERROR: could not read tax_config: {exc}"))
        return 2

    by_key = {}
    for row in rows:
        try:
            by_key[row.key] = json.loads(row.value)
        except json.JSONDecodeError:
            by_key[row.key] = row.value

    print()
    print("  Production safety flag check")
    print("  " + "─" * 50)
    bad: list[str] = []
    for key, expected in PROTECTED_FLAGS:
        actual = by_key.get(key, "<unset>")
        if key in allow:
            print(f"  {_c(_YELLOW, '[ALLOW]'):>15}  {key}={actual!r} (explicit --allow)")
            continue
        if actual == expected or actual == "<unset>":
            print(f"  {_c(_GREEN, '[OK]'):>15}  {key}={actual!r}")
        else:
            bad.append(key)
            print(f"  {_c(_RED, '[BLOCKED]'):>15}  {key}={actual!r} (expected {expected!r})")

    print()
    if bad:
        print(_c(_RED, f"  Deploy BLOCKED — {len(bad)} flag(s) are on: {bad}"))
        print( "  If this is intentional (CA-signed canary), re-run with:")
        print( "    python -m scripts.check_safety_flags " +
               " ".join(f"--allow {k}" for k in bad))
        return 1
    print(_c(_GREEN, "  All protected flags OFF — safe to deploy."))
    return 0


# ---------- entrypoint -----------------------------------------------------

def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Block deploy if any production accounting flag is on.",
    )
    p.add_argument("--allow", action="append", default=[],
                   help="Explicitly allow a specific flag to be on. Repeatable. "
                        "Required for every flag the operator wants to bypass "
                        "after CA sign-off.")
    return p.parse_args()


def _main() -> int:
    args = _args()
    return asyncio.run(check(allow=set(args.allow)))


if __name__ == "__main__":
    raise SystemExit(_main())
