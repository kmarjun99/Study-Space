"""Owner billing: one-time listing fee + recurring monthly maintenance fee.

The unique constraint on `(owner_id, charge_type, period_key, listing_id)`
plus `is_already_posted` in `LedgerService` together guarantee idempotency
across re-runs of the monthly cron and webhook replays.

Dunning matrix (read from tax_config):
  T+3   : OVERDUE banner (no listing change yet)
  T+7   : visibility_score halved
  T+10  : maintenance_status = SUSPENDED_FOR_NONPAYMENT (no new bookings)
  T+15  : hidden from search (handled in search filter, not here)

The state machine acts on whichever model the listing belongs to —
`ReadingRoom` and `Accommodation` share the same column shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.accommodation import Accommodation
from app.models.invoice import Invoice, InvoiceDocType
from app.models.owner_charge import (
    ListingType,
    ONETIME_PERIOD_KEY,
    OwnerCharge,
    OwnerChargeStatus,
    OwnerChargeType,
)
from app.models.party import Party
from app.models.reading_room import (
    ListingStatus,
    MaintenanceStatus,
    ReadingRoom,
)
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.services.invoice_series_service import (
    InvoiceSeriesService,
    current_fiscal_year,
)
from app.services.ledger_service import Entry, LedgerService
from app.services.tax_engine import (
    PlatformFeeTaxResult,
    cfg_get,
    compute_platform_fee_tax,
    freeze_snapshot,
    load_active_config,
    q2,
    to_decimal,
)


# Series codes
SERIES_PLATFORM_INVOICE = "PLF"

# Account codes (must match seed_chart_of_accounts.py)
ACC_RAZORPAY_RECEIVABLE = "1010"
ACC_REVENUE_LISTING = "4010"
ACC_REVENUE_MAINTENANCE = "4011"
ACC_GST_OUT_CGST = "2020"
ACC_GST_OUT_SGST = "2021"
ACC_GST_OUT_IGST = "2022"


@dataclass
class ChargeCreationResult:
    charge: OwnerCharge
    tax: PlatformFeeTaxResult
    was_existing: bool = False    # True when an idempotent re-run returned an existing row


# ---------- listing helpers -------------------------------------------------

async def _load_listing(
    db: AsyncSession, listing_id: str, listing_type: ListingType,
):
    model = ReadingRoom if listing_type == ListingType.READING_ROOM else Accommodation
    return (await db.execute(select(model).where(model.id == listing_id))).scalar_one_or_none()


async def _load_owner(db: AsyncSession, owner_id: str) -> Optional[User]:
    return (await db.execute(select(User).where(User.id == owner_id))).scalar_one_or_none()


async def _platform_party(db: AsyncSession, config: dict) -> Party:
    """Snapshot a Party row representing mySpace as supplier.

    Reuses an existing row when the snapshot fields are identical so we
    don't append a fresh row for every invoice (the legal-name + GSTIN
    rarely change for the platform, so the same row serves thousands of
    invoices). Snapshot semantics still hold: if the platform legal entity
    changes mid-FY, the next invoice gets a new Party row and historic
    invoices keep pointing at the old one.
    """
    legal_name = cfg_get(config, "platform.legal_name", "mySpace")
    address = cfg_get(config, "platform.address", "")
    gstin = cfg_get(config, "platform.gstin", "")
    state_code = cfg_get(config, "platform.home_state", "")
    existing = (await db.execute(
        select(Party).where(
            (Party.party_type == "PLATFORM")
            & (Party.legal_name == legal_name)
            & (Party.gstin == gstin)
            & (Party.state_code == state_code)
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    party = Party(
        party_type="PLATFORM",
        legal_name=legal_name,
        address=address,
        gstin=gstin,
        state_code=state_code,
    )
    db.add(party)
    await db.flush()
    return party


async def _owner_party(db: AsyncSession, owner: User) -> Party:
    """Snapshot a Party row for an owner — re-using the latest snapshot
    when the owner's identity fields haven't changed. The party_ref_id
    column already indexes on owner.id, so this lookup is cheap.
    """
    legal_name = owner.legal_name or owner.name
    existing = (await db.execute(
        select(Party).where(
            (Party.party_type == "OWNER")
            & (Party.party_ref_id == owner.id)
            & (Party.legal_name == legal_name)
            & (Party.gstin == (owner.gstin or None))
            & (Party.pan == (owner.pan or None))
            & (Party.state_code == (owner.business_state_code or None))
        ).order_by(Party.snapshot_at.desc()).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    party = Party(
        party_type="OWNER",
        party_ref_id=owner.id,
        legal_name=legal_name,
        gstin=owner.gstin,
        pan=owner.pan,
        state_code=owner.business_state_code,
        contact_email=owner.email,
        contact_phone=owner.phone,
    )
    db.add(party)
    await db.flush()
    return party


# ---------- charge creation -------------------------------------------------

async def _create_charge(
    db: AsyncSession,
    *,
    owner: User,
    listing_id: Optional[str],
    listing_type: Optional[ListingType],
    charge_type: OwnerChargeType,
    period_key: Optional[str],
    base_amount: Decimal,
    due_in_days: int = 7,
) -> ChargeCreationResult:
    """Idempotent INSERT of an OwnerCharge with tax computed and frozen."""
    config = await load_active_config(db)
    snap = await freeze_snapshot(db, config)
    tax = compute_platform_fee_tax(
        base_or_total=base_amount,
        recipient_state=owner.business_state_code,
        config=config,
        snapshot_id=snap.id,
    )

    # Capture identifiers before flush — after a potential rollback below the
    # ORM-loaded `owner` is expired and `.id` would trigger an async lazy load.
    owner_id_local = owner.id

    # Service-level idempotency: re-running the cron must be safe even if the
    # DB-level unique constraint is the only enforcement (SQLite-friendly).
    existing = (await db.execute(
        select(OwnerCharge).where(
            (OwnerCharge.owner_id == owner_id_local)
            & (OwnerCharge.charge_type == charge_type)
            & (OwnerCharge.period_key == period_key)
            & (OwnerCharge.listing_id == listing_id)
        )
    )).scalar_one_or_none()
    if existing is not None:
        return ChargeCreationResult(charge=existing, tax=tax, was_existing=True)

    charge = OwnerCharge(
        owner_id=owner_id_local,
        listing_id=listing_id,
        listing_type=listing_type,
        charge_type=charge_type,
        period_key=period_key,
        base_amount=tax.base,
        gst_amount=tax.gst.total,
        total_amount=tax.total,
        gst_rate_applied=tax.rate_applied,
        status=OwnerChargeStatus.DUE,
        due_date=datetime.utcnow() + timedelta(days=due_in_days),
        tax_snapshot_id=snap.id,
    )
    # SAVEPOINT instead of full rollback: the monthly cron iterates many
    # listings on a single session, and a duplicate-key crash on one listing
    # used to wipe every charge the cron had already flushed in the same
    # session. begin_nested() limits the rollback to just this INSERT.
    try:
        async with db.begin_nested():
            db.add(charge)
            await db.flush()
    except IntegrityError:
        existing = (await db.execute(
            select(OwnerCharge).where(
                (OwnerCharge.owner_id == owner_id_local)
                & (OwnerCharge.charge_type == charge_type)
                & (OwnerCharge.period_key == period_key)
                & (OwnerCharge.listing_id == listing_id)
            )
        )).scalar_one()
        return ChargeCreationResult(charge=existing, tax=tax, was_existing=True)

    return ChargeCreationResult(charge=charge, tax=tax, was_existing=False)


async def create_listing_fee_charge(
    db: AsyncSession,
    *,
    owner_id: str,
    listing_id: str,
    listing_type: ListingType,
    plan_id: str,
) -> ChargeCreationResult:
    """Create a one-time LISTING_FEE charge based on the chosen plan."""
    owner = await _load_owner(db, owner_id)
    if owner is None:
        raise ValueError(f"Owner {owner_id} not found")

    plan = (await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
    )).scalar_one_or_none()
    if plan is None:
        raise ValueError(f"SubscriptionPlan {plan_id} not found")

    return await _create_charge(
        db,
        owner=owner,
        listing_id=listing_id,
        listing_type=listing_type,
        charge_type=OwnerChargeType.LISTING_FEE,
        # Sentinel rather than NULL: Postgres treats two NULLs as distinct
        # so a NULL period_key would let duplicate listing-fee rows through.
        period_key=ONETIME_PERIOD_KEY,
        base_amount=to_decimal(plan.price),
    )


async def create_maintenance_charge_for_period(
    db: AsyncSession,
    *,
    listing_id: str,
    listing_type: ListingType,
    year_month: str,        # 'YYYY-MM'
    base_amount: Decimal,
) -> Optional[ChargeCreationResult]:
    """Idempotent monthly maintenance charge for one listing.

    Returns None if the listing or its owner cannot be loaded.
    """
    listing = await _load_listing(db, listing_id, listing_type)
    if listing is None:
        return None
    owner = await _load_owner(db, listing.owner_id)
    if owner is None:
        return None

    return await _create_charge(
        db,
        owner=owner,
        listing_id=listing_id,
        listing_type=listing_type,
        charge_type=OwnerChargeType.MAINTENANCE_FEE,
        period_key=year_month,
        base_amount=base_amount,
    )


# ---------- payment marking & invoice issuance ------------------------------

async def mark_charge_paid(
    db: AsyncSession,
    *,
    charge_id: str,
    payment_ref: str,
) -> Invoice:
    """Mark an OwnerCharge PAID, issue the PLATFORM_TAX_INVOICE,
    and post the ledger group. Idempotent.

    Concurrency: client /confirm and the asynchronous webhook can both
    arrive at this function before the first one commits. Without a row
    lock, both would allocate distinct invoice numbers from the series
    counter and both would write Invoice rows pointing at the same
    OwnerCharge — visible as non-sequential gaps in the GST series (a
    real compliance violation). SELECT FOR UPDATE on the charge serializes
    them; the second caller sees status=PAID and returns the existing invoice.
    """
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        charge = (await db.execute(
            select(OwnerCharge).where(OwnerCharge.id == charge_id).with_for_update()
        )).scalar_one_or_none()
    else:
        charge = await db.get(OwnerCharge, charge_id)
    if charge is None:
        raise ValueError(f"OwnerCharge {charge_id} not found")

    # Idempotency: short-circuit on status alone, not (status AND invoice_id).
    # A prior partial commit could land status=PAID without invoice_id; in
    # that case re-allocating a number would create a duplicate invoice
    # for the same series sequence, which is the exact compliance violation
    # we're guarding against. Trust the status; if invoice is missing it
    # surfaces as a 404 the operator must reconcile.
    if charge.status == OwnerChargeStatus.PAID:
        if charge.invoice_id:
            existing_invoice = await db.get(Invoice, charge.invoice_id)
            if existing_invoice is not None:
                return existing_invoice
        raise ValueError(
            f"OwnerCharge {charge_id} is PAID but invoice_id is missing — "
            f"reconcile manually before re-attempting payment."
        )

    config = await load_active_config(db)
    owner = await _load_owner(db, charge.owner_id)
    if owner is None:
        raise ValueError(f"Owner {charge.owner_id} missing for charge")

    # Allocate invoice series number atomically
    series_no_str, fy, seq_no = await InvoiceSeriesService.next_number(
        db, series_code=SERIES_PLATFORM_INVOICE,
    )

    supplier = await _platform_party(db, config)
    recipient = await _owner_party(db, owner)

    # Determine state split from the recipient owner state
    platform_state = (cfg_get(config, "platform.home_state", "") or "").upper()
    owner_state = (owner.business_state_code or "").upper()
    intra = bool(platform_state and owner_state and platform_state == owner_state)

    cgst = sgst = igst = to_decimal(0)
    if intra:
        half = q2(to_decimal(charge.gst_amount) / 2)
        cgst = half
        sgst = q2(to_decimal(charge.gst_amount) - half)
    else:
        igst = to_decimal(charge.gst_amount)

    invoice = Invoice(
        invoice_number=series_no_str,
        booking_id=None,
        user_id=owner.id,
        payment_id=None,
        owner_charge_id=charge.id,
        amount=float(charge.base_amount),
        tax_amount=float(charge.gst_amount),
        total_amount=float(charge.total_amount),
        venue_name=cfg_get(config, "platform.legal_name", "StudySpace"),
        venue_address=cfg_get(config, "platform.address", ""),
        seat_details=_charge_description(charge),
        plan_duration=charge.period_key or "One-time",
        doc_type=InvoiceDocType.PLATFORM_TAX_INVOICE,
        series_code=SERIES_PLATFORM_INVOICE,
        fiscal_year=fy,
        sequence_no=seq_no,
        supplier_party_id=supplier.id,
        recipient_party_id=recipient.id,
        place_of_supply_state=owner.business_state_code,
        cgst=cgst,
        sgst=sgst,
        igst=igst,
        cess=to_decimal(0),
        base_amount=charge.base_amount,
        hsn_sac=cfg_get(config, "gst.platform_fee_sac", "998599"),
        tax_snapshot_id=charge.tax_snapshot_id,
    )
    db.add(invoice)
    await db.flush()

    # Mark charge paid
    charge.status = OwnerChargeStatus.PAID
    charge.paid_at = datetime.utcnow()
    charge.razorpay_payment_id = payment_ref
    charge.invoice_id = invoice.id

    # Post ledger (Dr Razorpay Receivable, Cr Revenue + GST)
    revenue_acc = (
        ACC_REVENUE_LISTING
        if charge.charge_type == OwnerChargeType.LISTING_FEE
        else ACC_REVENUE_MAINTENANCE
    )
    entries: list[Entry] = [
        Entry(
            account_code=ACC_RAZORPAY_RECEIVABLE,
            debit=to_decimal(charge.total_amount),
            party_type="OWNER",
            party_id=owner.id,
            narration=f"Receipt of {charge.charge_type.value} for {charge.period_key or 'one-time'}",
        ),
        Entry(
            account_code=revenue_acc,
            credit=to_decimal(charge.base_amount),
            party_type="OWNER",
            party_id=owner.id,
            narration=f"{charge.charge_type.value} revenue",
        ),
    ]
    if cgst > 0:
        entries.append(Entry(
            account_code=ACC_GST_OUT_CGST, credit=cgst,
            party_type="OWNER", party_id=owner.id,
            narration="Output CGST on platform fee",
        ))
    if sgst > 0:
        entries.append(Entry(
            account_code=ACC_GST_OUT_SGST, credit=sgst,
            party_type="OWNER", party_id=owner.id,
            narration="Output SGST on platform fee",
        ))
    if igst > 0:
        entries.append(Entry(
            account_code=ACC_GST_OUT_IGST, credit=igst,
            party_type="OWNER", party_id=owner.id,
            narration="Output IGST on platform fee",
        ))

    await LedgerService.post_entries(
        db,
        txn_group_id=None,
        source_type="OWNER_CHARGE",
        source_id=charge.id,
        entries=entries,
        narration=f"Payment of {charge.charge_type.value} {charge.id}",
    )

    return invoice


def _charge_description(charge: OwnerCharge) -> str:
    if charge.charge_type == OwnerChargeType.LISTING_FEE:
        return f"One-time listing fee — listing {charge.listing_id}"
    if charge.charge_type == OwnerChargeType.MAINTENANCE_FEE:
        return (
            f"Platform maintenance fee — {charge.period_key} — "
            f"listing {charge.listing_id}"
        )
    return charge.charge_type.value


# ---------- dunning + listing state machine ---------------------------------

async def _apply_state_to_listing(
    db: AsyncSession,
    listing_id: str,
    listing_type: ListingType,
    *,
    visibility_score: Optional[float] = None,
    maintenance_status: Optional[MaintenanceStatus] = None,
) -> None:
    listing = await _load_listing(db, listing_id, listing_type)
    if listing is None:
        return
    if visibility_score is not None:
        listing.visibility_score = visibility_score
    if maintenance_status is not None:
        listing.maintenance_status = maintenance_status
    await db.flush()


async def dunning_step(db: AsyncSession, *, charge_id: str) -> str:
    """Apply the dunning state machine to a single OVERDUE/DUE charge.

    Returns a short status string for logging.
    """
    charge = await db.get(OwnerCharge, charge_id)
    if charge is None or charge.status not in (OwnerChargeStatus.DUE, OwnerChargeStatus.OVERDUE):
        return "skip"
    if charge.due_date is None:
        return "skip-no-due-date"

    days_overdue = (datetime.utcnow() - charge.due_date).days
    if days_overdue < 0:
        return "not-yet-due"

    config = await load_active_config(db)
    dim_days = int(cfg_get(config, "maintenance.overdue.dim_days", 7))
    suspend_days = int(cfg_get(config, "maintenance.overdue.suspend_days", 10))
    hide_days = int(cfg_get(config, "maintenance.overdue.hide_days", 15))

    listing_id = charge.listing_id
    ltype = charge.listing_type
    if listing_id is None or ltype is None:
        return "skip-no-listing"

    # Mark OVERDUE regardless of severity
    if charge.status == OwnerChargeStatus.DUE:
        charge.status = OwnerChargeStatus.OVERDUE
        await db.flush()

    if days_overdue >= hide_days:
        await _apply_state_to_listing(
            db, listing_id, ltype,
            visibility_score=0.0,
            maintenance_status=MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT,
        )
        return f"hidden (T+{days_overdue})"

    if days_overdue >= suspend_days:
        await _apply_state_to_listing(
            db, listing_id, ltype,
            visibility_score=0.25,
            maintenance_status=MaintenanceStatus.SUSPENDED_FOR_NONPAYMENT,
        )
        return f"suspended (T+{days_overdue})"

    if days_overdue >= dim_days:
        await _apply_state_to_listing(
            db, listing_id, ltype,
            visibility_score=0.5,
            maintenance_status=MaintenanceStatus.OVERDUE,
        )
        return f"dimmed (T+{days_overdue})"

    await _apply_state_to_listing(
        db, listing_id, ltype, maintenance_status=MaintenanceStatus.OVERDUE,
    )
    return f"overdue (T+{days_overdue})"


async def reactivate_listing_after_payment(
    db: AsyncSession, *, listing_id: str, listing_type: ListingType,
) -> None:
    """When the most recent overdue charge is paid, restore visibility."""
    # Only reset if no other unpaid charges remain.
    pending = (await db.execute(
        select(OwnerCharge.id).where(
            (OwnerCharge.listing_id == listing_id)
            & (OwnerCharge.listing_type == listing_type)
            & (OwnerCharge.status.in_([
                OwnerChargeStatus.DUE,
                OwnerChargeStatus.OVERDUE,
                OwnerChargeStatus.FAILED,
            ]))
        )
    )).first()
    if pending:
        return  # still have unpaid charges
    await _apply_state_to_listing(
        db, listing_id, listing_type,
        visibility_score=1.0,
        maintenance_status=MaintenanceStatus.CURRENT,
    )


async def generate_maintenance_charges_for_today(
    db: AsyncSession,
    *,
    today: Optional[datetime] = None,
) -> dict:
    """Cron entry-point. Iterates all LIVE listings whose anchor_day matches.

    Returns a summary dict for logs.
    """
    config = await load_active_config(db)
    if not bool(cfg_get(config, "feature.recurring_maintenance", False)):
        return {"skipped": "feature.recurring_maintenance is OFF"}

    today = today or datetime.utcnow()
    day = today.day
    period_key = today.strftime("%Y-%m")

    created = 0
    skipped = 0

    # Reading rooms
    rr_rows = (await db.execute(
        select(ReadingRoom).where(
            (ReadingRoom.status == ListingStatus.LIVE)
            & (ReadingRoom.billing_anchor_day == day)
        )
    )).scalars().all()
    for rr in rr_rows:
        base = _resolve_maintenance_base_amount(rr, config)
        if base is None or base <= 0:
            skipped += 1
            continue
        result = await create_maintenance_charge_for_period(
            db,
            listing_id=rr.id,
            listing_type=ListingType.READING_ROOM,
            year_month=period_key,
            base_amount=base,
        )
        if result is not None and not result.was_existing:
            created += 1

    # Accommodations
    acc_rows = (await db.execute(
        select(Accommodation).where(
            (Accommodation.status == ListingStatus.LIVE)
            & (Accommodation.billing_anchor_day == day)
        )
    )).scalars().all()
    for acc in acc_rows:
        base = _resolve_maintenance_base_amount(acc, config)
        if base is None or base <= 0:
            skipped += 1
            continue
        result = await create_maintenance_charge_for_period(
            db,
            listing_id=acc.id,
            listing_type=ListingType.ACCOMMODATION,
            year_month=period_key,
            base_amount=base,
        )
        if result is not None and not result.was_existing:
            created += 1

    await db.commit()
    return {"created": created, "skipped": skipped, "period": period_key}


def _resolve_maintenance_base_amount(listing, config) -> Optional[Decimal]:
    """Per-listing maintenance fee override or platform default.

    We keep this simple: a single config key `maintenance.default_base_amount`
    is the platform default. Per-listing override mechanism can be added
    later without touching this function's callers.
    """
    default = cfg_get(config, "maintenance.default_base_amount", None)
    if default is None:
        return None
    return to_decimal(default)
