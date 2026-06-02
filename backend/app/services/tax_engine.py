"""Pure tax computation service.

Hard rules:
  - Money math uses `Decimal`, never `float`.
  - Rates and policy come from `tax_config` — nothing here is hardcoded.
  - For each financial event we freeze a `TaxSnapshot` so a CA can reproduce
    the exact computation years later.
  - Booking prices are **GST-inclusive by default** (per business rule).
    The split is computed by reverse-calculation, not by adding on top.
  - No DB writes happen here except `freeze_snapshot`. Callers pass the
    snapshot id into ledger / invoice services.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_config import TaxConfig
from app.models.tax_snapshot import TaxSnapshot
from app.models.user import User, GSTRegistrationType
from app.models.booking import GSTTreatment


TWO_PLACES = Decimal("0.01")
ONE = Decimal("1")
ZERO = Decimal("0")


# ---------- Result types ----------------------------------------------------

@dataclass
class InclusiveSplit:
    """Reverse-calculated split of a GST-inclusive gross amount."""
    gross: Decimal
    base: Decimal
    gst: Decimal
    rate: Decimal


@dataclass
class TaxAmounts:
    """CGST / SGST / IGST breakdown for one supply."""
    cgst: Decimal = ZERO
    sgst: Decimal = ZERO
    igst: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return q2(self.cgst + self.sgst + self.igst)


@dataclass
class BookingTaxResult:
    """Computed tax for a single student booking."""
    treatment: GSTTreatment
    gross: Decimal                  # what student paid (unchanged)
    base: Decimal                   # taxable value
    gst: TaxAmounts
    rate_applied: Decimal
    place_of_supply_state: Optional[str]
    snapshot_id: str
    sac: Optional[str] = None


@dataclass
class PlatformFeeTaxResult:
    """Computed tax for a platform-side charge (listing or maintenance fee)."""
    base: Decimal                   # taxable value
    gst: TaxAmounts
    total: Decimal                  # base + gst (what owner pays)
    rate_applied: Decimal
    place_of_supply_state: str
    snapshot_id: str
    sac: str


# ---------- Helpers ---------------------------------------------------------

def q2(value: Decimal | int | float | str) -> Decimal:
    """Quantize to 2 decimal places, banker-safe half-up rounding."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_decimal(value: Any) -> Decimal:
    """Tolerant cast that handles str/int/float/Decimal."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def compute_inclusive_split(gross: Decimal | float | int | str,
                            rate: Decimal | float | int | str) -> InclusiveSplit:
    """Reverse-calculate base + GST from a GST-inclusive gross.

    Example: gross=2500, rate=0.18 -> base=2118.64, gst=381.36 (sum equals gross
    after 2-dp rounding, by construction of `base = round(gross - gst)`).
    """
    g = to_decimal(gross)
    r = to_decimal(rate)

    if g <= 0:
        return InclusiveSplit(gross=q2(g), base=ZERO, gst=ZERO, rate=r)
    if r <= 0:
        return InclusiveSplit(gross=q2(g), base=q2(g), gst=ZERO, rate=r)

    gst = q2(g * r / (ONE + r))
    base = q2(g - gst)            # guarantees base + gst == gross at 2 dp
    return InclusiveSplit(gross=q2(g), base=base, gst=gst, rate=r)


def split_gst_by_state(gst: Decimal,
                       supplier_state: Optional[str],
                       recipient_state: Optional[str]) -> TaxAmounts:
    """CGST+SGST when intra-state, IGST when inter-state.

    Either state being unknown -> default to IGST (safer, recoverable; better
    than silently splitting incorrectly).
    """
    gst = q2(gst)
    if gst <= 0:
        return TaxAmounts()
    if (supplier_state and recipient_state
            and supplier_state.upper() == recipient_state.upper()):
        half = q2(gst / Decimal(2))
        # Ensure CGST + SGST equals total exactly (handle odd-paise residue).
        return TaxAmounts(cgst=half, sgst=q2(gst - half))
    return TaxAmounts(igst=gst)


# ---------- Config loading + snapshots --------------------------------------

async def load_active_config(db: AsyncSession) -> dict[str, Any]:
    """Read all tax_config rows into a plain dict (parsed JSON values)."""
    rows = (await db.execute(select(TaxConfig))).scalars().all()
    out: dict[str, Any] = {}
    for row in rows:
        try:
            out[row.key] = json.loads(row.value)
        except json.JSONDecodeError:
            # Tolerate bad data — surface as string so caller can decide.
            out[row.key] = row.value
    return out


async def freeze_snapshot(db: AsyncSession,
                          config: dict[str, Any]) -> TaxSnapshot:
    """Persist a TaxSnapshot row. Caller MUST commit. Returns the snapshot."""
    snap = TaxSnapshot(payload=json.dumps(config, default=str, sort_keys=True))
    db.add(snap)
    await db.flush()    # populate snap.id without committing
    return snap


def cfg_get(config: dict[str, Any], key: str, default: Any = None) -> Any:
    return config.get(key, default)


def accounting_enabled(config: dict[str, Any]) -> bool:
    return bool(cfg_get(config, "accounting.enabled", False))


# ---------- Booking tax -----------------------------------------------------

def _resolve_booking_rate(config: dict[str, Any],
                          listing_rate_override: Optional[Decimal]) -> Decimal:
    if listing_rate_override is not None:
        return to_decimal(listing_rate_override)
    return to_decimal(cfg_get(config, "gst.booking.default_rate", 0))


def _resolve_treatment(owner: Optional[User],
                       listing_gst_category: Optional[str],
                       config: dict[str, Any]) -> GSTTreatment:
    """Decide which GST regime applies to this booking."""
    if owner is None or owner.gst_registration_type is None:
        return GSTTreatment.NOT_REGISTERED
    if owner.gst_registration_type == GSTRegistrationType.REGULAR:
        return GSTTreatment.OWNER_REGISTERED
    if owner.gst_registration_type == GSTRegistrationType.COMPOSITION:
        # Composition dealers cannot collect GST from recipient — settled out of band.
        return GSTTreatment.EXEMPT
    # Unregistered owner -> check Sec 9(5) eligibility
    eligible = cfg_get(config, "gst.booking.sec_9_5_eligible_categories", []) or []
    if listing_gst_category and listing_gst_category in eligible:
        return GSTTreatment.SEC_9_5
    return GSTTreatment.NOT_REGISTERED


def resolve_pricing_inclusive(
    *,
    listing_price_display_mode: Optional[str],
    config: dict[str, Any],
) -> bool:
    """Decide whether the booking gross is GST-inclusive for this listing.

    Honour the per-listing `price_display_mode` only when the rollout flag
    `feature.per_listing_price_mode` is on. Otherwise the global
    `gst.booking.pricing_is_inclusive` flag wins for every listing. This makes
    the column safe to populate before the booking router migration ships.
    """
    flag_on = bool(cfg_get(config, "feature.per_listing_price_mode", False))
    if flag_on and listing_price_display_mode in ("GST_INCLUDED", "GST_EXTRA"):
        return listing_price_display_mode == "GST_INCLUDED"
    return bool(cfg_get(config, "gst.booking.pricing_is_inclusive", True))


def compute_booking_tax(
    *,
    gross: Decimal | float | int | str,
    owner: Optional[User],
    listing_gst_category: Optional[str],
    listing_gst_rate_override: Optional[Decimal] = None,
    listing_price_display_mode: Optional[str] = None,
    place_of_supply_state: Optional[str] = None,
    sac: Optional[str] = None,
    config: dict[str, Any],
    snapshot_id: str,
    inclusive_override: Optional[bool] = None,
) -> BookingTaxResult:
    """Compute the booking tax breakdown.

    `gross` is GST-inclusive iff one of the following is true (first match wins):
      1. `inclusive_override` is explicitly passed
      2. The listing has `price_display_mode` set AND
         `feature.per_listing_price_mode` is enabled in config
      3. The global `gst.booking.pricing_is_inclusive` flag (default: True)
    """
    treatment = _resolve_treatment(owner, listing_gst_category, config)
    sac = sac or cfg_get(config, "gst.booking.default_sac", None)

    # Decide effective rate & supplier state for state split.
    if treatment in (GSTTreatment.OWNER_REGISTERED, GSTTreatment.SEC_9_5):
        rate = _resolve_booking_rate(config, listing_gst_rate_override)
    else:
        rate = ZERO

    # Supplier state: owner state when owner-registered, else platform state for Sec 9(5).
    if treatment == GSTTreatment.OWNER_REGISTERED and owner is not None:
        supplier_state = owner.business_state_code
    else:
        supplier_state = cfg_get(config, "platform.home_state", None)

    if inclusive_override is not None:
        inclusive = inclusive_override
    else:
        inclusive = resolve_pricing_inclusive(
            listing_price_display_mode=listing_price_display_mode,
            config=config,
        )

    if inclusive:
        split = compute_inclusive_split(gross, rate)
        base, gst_total = split.base, split.gst
    else:
        b = q2(gross)
        gst_total = q2(b * rate)
        base = b

    gst_amounts = split_gst_by_state(gst_total, supplier_state, place_of_supply_state)

    return BookingTaxResult(
        treatment=treatment,
        gross=q2(gross),
        base=base,
        gst=gst_amounts,
        rate_applied=rate,
        place_of_supply_state=place_of_supply_state,
        snapshot_id=snapshot_id,
        sac=sac,
    )


def compute_booking_gross(
    *,
    displayed_price: Decimal | float | int | str,
    listing_gst_rate_override: Optional[Decimal],
    listing_price_display_mode: Optional[str],
    config: dict[str, Any],
) -> Decimal:
    """Helper for the *future* booking-router migration.

    Given a price as the owner enters it, return what the student must actually
    be charged:
      - GST_INCLUDED  -> displayed_price unchanged
      - GST_EXTRA     -> displayed_price * (1 + rate)

    The booking router can use this to keep tax handling in one place, instead
    of replicating the math at every order-creation site. Until
    `feature.per_listing_price_mode` is on, this always returns the displayed
    price unchanged.
    """
    if not resolve_pricing_inclusive(
        listing_price_display_mode=listing_price_display_mode, config=config,
    ):
        rate = _resolve_booking_rate(config, listing_gst_rate_override)
        return q2(to_decimal(displayed_price) * (ONE + rate))
    return q2(displayed_price)


# ---------- Platform fee tax (listing / maintenance) ------------------------

def compute_platform_fee_tax(
    *,
    base_or_total: Decimal | float | int | str,
    recipient_state: Optional[str],
    config: dict[str, Any],
    snapshot_id: str,
) -> PlatformFeeTaxResult:
    """Compute GST for a platform-charged owner fee.

    If config['gst.platform_fee_inclusive'] is true, `base_or_total` is treated
    as gross (reverse-calc). Otherwise GST is added on top of the base.
    """
    rate = to_decimal(cfg_get(config, "gst.platform_fee_rate", 0))
    sac = cfg_get(config, "gst.platform_fee_sac", "998599")
    platform_state = cfg_get(config, "platform.home_state", "")
    inclusive = bool(cfg_get(config, "gst.platform_fee_inclusive", False))

    if inclusive:
        split = compute_inclusive_split(base_or_total, rate)
        base, gst_total, total = split.base, split.gst, q2(split.gross)
    else:
        base = q2(base_or_total)
        gst_total = q2(base * rate)
        total = q2(base + gst_total)

    gst = split_gst_by_state(gst_total, platform_state, recipient_state)

    return PlatformFeeTaxResult(
        base=base,
        gst=gst,
        total=total,
        rate_applied=rate,
        place_of_supply_state=recipient_state or platform_state,
        snapshot_id=snapshot_id,
        sac=sac,
    )


# ---------- TCS / TDS (computed at settlement time) -------------------------

@dataclass
class StatutoryDeductions:
    tcs_cgst: Decimal = ZERO
    tcs_sgst: Decimal = ZERO
    tcs_igst: Decimal = ZERO
    tds_194o: Decimal = ZERO

    @property
    def total(self) -> Decimal:
        return q2(self.tcs_cgst + self.tcs_sgst + self.tcs_igst + self.tds_194o)


def compute_statutory_deductions(
    *,
    net_taxable_value: Decimal,
    owner_registered: bool,
    intra_state: bool,
    yearly_owner_gross_so_far: Decimal,
    config: dict[str, Any],
) -> StatutoryDeductions:
    """TCS (Sec 52 CGST) and TDS (Sec 194-O) deductions, configurable & gated.

    Returns all zeros if the relevant flag is disabled in config.
    """
    out = StatutoryDeductions()
    net = q2(net_taxable_value)

    if bool(cfg_get(config, "tcs.enabled", False)):
        applies = owner_registered or bool(
            cfg_get(config, "tcs.applies_to_unregistered_owner", False)
        )
        if applies and net > 0:
            if intra_state:
                out.tcs_cgst = q2(net * to_decimal(cfg_get(config, "tcs.rate_cgst", 0)))
                out.tcs_sgst = q2(net * to_decimal(cfg_get(config, "tcs.rate_sgst", 0)))
            else:
                out.tcs_igst = q2(net * to_decimal(cfg_get(config, "tcs.rate_igst", 0)))

    if bool(cfg_get(config, "tds.section_194o_enabled", False)):
        threshold = to_decimal(cfg_get(config, "tds.section_194o_threshold_yearly", 0))
        if yearly_owner_gross_so_far + net > threshold and net > 0:
            rate = to_decimal(cfg_get(config, "tds.section_194o_rate", 0))
            out.tds_194o = q2(net * rate)

    return out


# Convenience: dataclass -> dict (handy for narration / debug)
def result_to_dict(obj: Any) -> dict[str, Any]:
    return asdict(obj)
