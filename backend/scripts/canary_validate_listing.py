"""Interactive canary validator for ONE real listing.

Walks the operator through the 10-step checklist your CA / friend laid out:

  1. Listing is GST_INCLUDED-safe (flag OFF or mode unset)
  2. Tax preview's payable amount equals the displayed price
  3. Tax preview reverse-calcs into the expected base + GST split
  4. After test payment, a PAID booking exists with a shadow-posted treatment
  5. The booking invoice (if issued) uses the same base + GST split
  6. Ledger owner-payable for the booking matches the expected amount
  7. Settlement was created for the booking
  8. Settlement statement arithmetic matches the ledger
  9. Partial refund produces a CREDIT_NOTE with proportional GST reversed
 10. `feature.per_listing_price_mode` is still OFF (safety net)

Usage:
    python -m scripts.canary_validate_listing \\
        --listing-type accommodation \\
        --listing-id <uuid> \\
        --expected-price 2500 \\
        --expected-base 2118.64 \\
        --expected-gst 381.36

When a step needs operator action (e.g., "make a test payment now"), the
script prints what to do, then waits for ENTER and re-runs the check. Use
`--non-interactive` to skip the prompts and just run the checks that pass
without human action (useful in CI).

The full pass/fail report is written to
    canary_output/validation_<listing_id>_<ts>.json
so it can be archived in the audit log.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionLocal  # noqa: E402
from app.services.canary_archive import build_archive_bundle  # noqa: E402
from app.services.canary_checks import (  # noqa: E402
    CheckResult,
    Status,
    check_ledger_integrity,
    check_step_1_listing_safety,
    check_step_10_safety_flag_off,
    check_step_2_payable_matches_expected,
    check_step_3_split_matches,
    check_step_4_test_booking_exists,
    check_step_5_invoice_split_matches,
    check_step_6_ledger_owner_payable,
    check_step_7_settlement_was_created,
    check_step_8_statement_matches_ledger,
    check_step_9_partial_refund_credit_note,
    _find_recent_paid_booking,
)
from app.services.settlement_service import run_settlements  # noqa: E402


OUTPUT_DIR = Path(__file__).resolve().parent.parent / "canary_output"


# ---------- output ---------------------------------------------------------

_COLORS = {
    Status.PASS: "\033[32m",         # green
    Status.FAIL: "\033[31m",         # red
    Status.WARN: "\033[33m",         # yellow
    Status.SKIP: "\033[90m",         # grey
    Status.NEEDS_ACTION: "\033[36m", # cyan
}
_RESET = "\033[0m"
_USE_COLOR = sys.stdout.isatty()


def _color(status: Status, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{_COLORS.get(status, '')}{text}{_RESET}"


def _print_result(result: CheckResult) -> None:
    tag = _color(result.status, f"[{result.status.value:^13}]")
    print(f"  {tag}  Step {result.step:>2}: {result.name}")
    if result.detail:
        print(f"               {result.detail}")


def _prompt(message: str, interactive: bool) -> None:
    """Print an operator instruction and wait for ENTER unless --non-interactive."""
    print()
    print(_color(Status.NEEDS_ACTION, "  →  " + message))
    if interactive:
        try:
            input(_color(Status.NEEDS_ACTION, "     [press ENTER to re-check] "))
        except EOFError:
            pass


# ---------- driver --------------------------------------------------------

async def run(
    *,
    listing_type: str,
    listing_id: str,
    expected_price: Decimal,
    expected_base: Decimal,
    expected_gst: Decimal,
    interactive: bool,
    auto_settle: bool,
    archive: bool,
) -> tuple[list[CheckResult], Optional[str], Optional[str]]:
    """Drive the 10-step checklist.

    Returns (results, booking_id_or_None, settlement_run_id_or_None) — the IDs
    are used by the archive bundler so we don't have to re-query at the end.
    """
    results: list[CheckResult] = []
    booking_id_found: Optional[str] = None
    run_id_found: Optional[str] = None

    async with AsyncSessionLocal() as db:
        # Step 1
        r = await check_step_1_listing_safety(
            db, listing_type=listing_type, listing_id=listing_id,
        )
        _print_result(r)
        results.append(r)
        if r.status == Status.FAIL:
            print("\n  Aborting: listing-level safety check failed.")
            return results

        # Step 2
        r = await check_step_2_payable_matches_expected(
            db, listing_type=listing_type, listing_id=listing_id,
            expected_price=expected_price,
        )
        _print_result(r)
        results.append(r)

        # Step 3
        r = await check_step_3_split_matches(
            db, listing_type=listing_type, listing_id=listing_id,
            expected_price=expected_price,
            expected_base=expected_base,
            expected_gst=expected_gst,
        )
        _print_result(r)
        results.append(r)

        # Step 4 — needs operator to make a test payment
        attempts = 0
        while True:
            r = await check_step_4_test_booking_exists(
                db, listing_type=listing_type, listing_id=listing_id,
            )
            if r.status != Status.NEEDS_ACTION or not interactive or attempts >= 3:
                break
            _prompt(
                "Make a test booking + complete payment for this listing now, "
                "then press ENTER.",
                interactive,
            )
            attempts += 1
        _print_result(r)
        results.append(r)

        booking_id = r.data.get("booking_id") if r.ok else None
        if not booking_id:
            paid = await _find_recent_paid_booking(db, listing_type, listing_id)
            if paid is not None:
                booking_id = paid.id
        booking_id_found = booking_id

        # Step 5
        if booking_id:
            r = await check_step_5_invoice_split_matches(db, booking_id=booking_id)
        else:
            r = CheckResult(5, "Invoice PDF uses same split", Status.SKIP,
                            "no booking available — skipped")
        _print_result(r)
        results.append(r)

        # Step 6
        if booking_id:
            r = await check_step_6_ledger_owner_payable(db, booking_id=booking_id)
        else:
            r = CheckResult(6, "Ledger owner payable correct", Status.SKIP, "no booking")
        _print_result(r)
        results.append(r)

        # Step 7 — settlement
        if booking_id and auto_settle:
            print(_color(Status.NEEDS_ACTION,
                         "  →  Triggering settlement run (--auto-settle)…"))
            summary = await run_settlements(db)
            print(f"     {summary}")
        if booking_id:
            attempts = 0
            while True:
                r = await check_step_7_settlement_was_created(db, booking_id=booking_id)
                if r.status != Status.NEEDS_ACTION or not interactive or attempts >= 3:
                    break
                _prompt(
                    "Trigger the settlement cron (or call POST /admin/settlements/run), "
                    "then press ENTER.",
                    interactive,
                )
                attempts += 1
        else:
            r = CheckResult(7, "Settlement run created", Status.SKIP, "no booking")
        _print_result(r)
        results.append(r)

        run_id = r.data.get("run_id") if r.ok else None

        run_id_found = run_id

        # Step 8
        if run_id:
            r = await check_step_8_statement_matches_ledger(db, run_id=run_id)
        else:
            r = CheckResult(8, "Statement matches ledger", Status.SKIP, "no settlement run")
        _print_result(r)
        results.append(r)

        # Step 9 — partial refund + credit note
        if booking_id:
            attempts = 0
            while True:
                r = await check_step_9_partial_refund_credit_note(db, booking_id=booking_id)
                if r.status != Status.NEEDS_ACTION or not interactive or attempts >= 3:
                    break
                _prompt(
                    "Create a PARTIAL refund (e.g., Rs.500 of a Rs.2500 booking) and "
                    "approve it via the admin refund endpoint, then press ENTER.",
                    interactive,
                )
                attempts += 1
        else:
            r = CheckResult(9, "Partial refund + credit note", Status.SKIP, "no booking")
        _print_result(r)
        results.append(r)

        # Step 10 — safety net always runs
        r = await check_step_10_safety_flag_off(db)
        _print_result(r)
        results.append(r)

        # Bonus integrity check
        r = await check_ledger_integrity(db)
        _print_result(r)
        results.append(r)

        if archive:
            print()
            print(_color(Status.NEEDS_ACTION,
                         "  →  Building archive bundle (--archive)…"))

    return results, booking_id_found, run_id_found


def _summarize(results: list[CheckResult]) -> tuple[int, int, int, int]:
    p = sum(1 for r in results if r.status == Status.PASS)
    f = sum(1 for r in results if r.status == Status.FAIL)
    w = sum(1 for r in results if r.status in (Status.WARN, Status.NEEDS_ACTION))
    s = sum(1 for r in results if r.status == Status.SKIP)
    return p, f, w, s


def _write_audit_log(results: list[CheckResult], listing_id: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    path = OUTPUT_DIR / f"validation_{listing_id[:8]}_{ts}.json"
    path.write_text(json.dumps(
        {"timestamp": datetime.utcnow().isoformat() + "Z",
         "listing_id": listing_id,
         "results": [r.to_dict() for r in results]},
        indent=2,
    ))
    return path


# ---------- argparse ------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Validate one real listing end-to-end against the canary checklist.",
    )
    p.add_argument("--listing-type", required=True,
                   choices=["reading-room", "accommodation"])
    p.add_argument("--listing-id", required=True)
    p.add_argument("--expected-price", type=Decimal, required=True,
                   help="The price the student should see displayed (e.g., 2500).")
    p.add_argument("--expected-base", type=Decimal, default=None,
                   help="Expected reverse-calc base. Defaults to price / 1.18.")
    p.add_argument("--expected-gst", type=Decimal, default=None,
                   help="Expected GST component. Defaults to price - base.")
    p.add_argument("--non-interactive", action="store_true",
                   help="Skip operator prompts; only run checks that don't need action.")
    p.add_argument("--auto-settle", action="store_true",
                   help="Trigger settlement_service.run_settlements() between steps 6 and 7.")
    p.add_argument("--archive", action="store_true",
                   help="At the end, bundle validation JSON + invoice PDF + settlement "
                        "PDF + credit note PDF + ledger CSV into a single zip.")
    return p.parse_args()


async def _main() -> int:
    args = _parse_args()
    base = args.expected_base if args.expected_base is not None else None
    gst = args.expected_gst if args.expected_gst is not None else None
    if base is None or gst is None:
        # Default: assume 18% inclusive
        rate = Decimal("0.18")
        gst_default = (args.expected_price * rate / (Decimal("1") + rate)).quantize(Decimal("0.01"))
        base = base if base is not None else (args.expected_price - gst_default)
        gst = gst if gst is not None else gst_default

    print()
    print(f"  Canary validation for {args.listing_type} {args.listing_id}")
    print(f"  Expected price: Rs.{args.expected_price}  "
          f"→ base Rs.{base} + gst Rs.{gst}")
    print()

    try:
        results, booking_id, run_id = await run(
            listing_type=args.listing_type,
            listing_id=args.listing_id,
            expected_price=args.expected_price,
            expected_base=base,
            expected_gst=gst,
            interactive=not args.non_interactive,
            auto_settle=args.auto_settle,
            archive=args.archive,
        )
    except Exception as exc:
        print(f"\n  Fatal error: {exc}")
        return 2

    p, f, w, s = _summarize(results)
    print()
    print(f"  Result: PASS={p} FAIL={f} WARN/ACTION={w} SKIP={s}")
    path = _write_audit_log(results, args.listing_id)
    print(f"  Audit log: {path}")

    if args.archive:
        # Open a fresh session because the validator's session has rolled back
        # the freeze_snapshot writes from preview steps.
        async with AsyncSessionLocal() as db:
            zip_name, zip_bytes = await build_archive_bundle(
                db,
                listing_id=args.listing_id,
                booking_id=booking_id,
                settlement_run_id=run_id,
                validation_json_path=path,
            )
        zip_path = OUTPUT_DIR / zip_name
        zip_path.write_bytes(zip_bytes)
        print(f"  Archive:   {zip_path} ({len(zip_bytes):,} bytes)")

    return 0 if f == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
