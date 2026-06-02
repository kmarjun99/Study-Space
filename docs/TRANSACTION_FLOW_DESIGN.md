# StudySpace — Complete Transaction Flow Design

> Indian GST + TCS / TDS-compliant, ledger-first, additive design.
> Goal: introduce a CA-auditable money-movement system **without breaking** the existing app.
> Existing models that stay untouched: `User`, `ReadingRoom`, `Cabin`, `Accommodation`, `Booking`, `PaymentTransaction`, `Invoice`, `Refund`, `SubscriptionPlan`, `BoostPlan/Request`, `Reminder`, `Notification`, `AuditLog`.
> All new behavior is layered on top via new tables, additive columns, and new services.

---

## 1. Roles, responsibilities and money flow at a glance

| Party | Role in transaction | Responsibilities |
|---|---|---|
| **StudySpace (platform)** | E-commerce operator (ECO) u/s 52 CGST + Sec 9(5) deemed supplier in defined cases | (a) Collect listing fee + monthly maintenance fee as **its own revenue**; (b) Collect student booking amount as **agent on behalf of owner**; (c) Apply Sec 9(5) GST where applicable; (d) Deduct TCS (Sec 52 CGST) and TDS (Sec 194-O IT Act) where applicable; (e) File GSTR-8 + 26Q; (f) Settle owner net of deductions; (g) Issue tax invoices for platform-fees and Sec 9(5) supplies; (h) Issue facilitation receipt for owner-billed supplies |
| **Property owner** (`UserRole.ADMIN`) | Supplier of accommodation/seat service to student | (a) Pay one-time listing fee; (b) Pay recurring maintenance fee; (c) Provide GSTIN/PAN/bank/KYC; (d) Issue own GST invoice to student if **GST-registered** (platform generates it on owner's behalf using owner's GSTIN); (e) Honour booking; (f) Accept settlement net of platform fees and statutory deductions |
| **Student / user** | Recipient of service | (a) Pay booking amount; (b) Receive a tax invoice (from owner if registered, from StudySpace if Sec 9(5) applies) or a non-tax receipt; (c) Claim refund per policy |

### Revenue classification (critical for accounting)

| Money flow | Whose revenue | GST liability |
|---|---|---|
| Listing fee (one-time) | StudySpace | StudySpace charges 18% GST (SAC 998599 — other support services) |
| Monthly maintenance fee | StudySpace | StudySpace charges 18% GST |
| Student booking amount | **Owner's revenue** (StudySpace is collecting agent) | See §6 — depends on owner GST status + service type |
| Convenience / facilitation fee (optional, future) | StudySpace | 18% GST |
| TCS collected | Liability — pay to government via GSTR-8 | Not revenue |
| TDS u/s 194-O | Liability — pay to government via 26Q | Not revenue |

> **Hard rule**: booking gross collected from the student must **never** be credited to StudySpace's P&L. It is held in a liability/`owner_payable` ledger until settled.

---

## 2. End-to-end transaction flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                      OWNER ONBOARDING                            │
└─────────────────────────────────────────────────────────────────┘
  Signup (role=ADMIN)
     │
     ▼
  KYC form (PAN, GSTIN-optional, Bank A/c, IFSC, state of business,
            GST registration type: REGULAR / COMPOSITION / UNREGISTERED)
     │
     ▼
  KYC review (super admin) ──── BLOCKING REMINDER if missing
     │
     ▼
  Create draft listing (ReadingRoom / Accommodation)  [status=DRAFT]
     │
     ▼
  Owner picks Listing Plan (SubscriptionPlan, one-time)
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│        ONE-TIME LISTING FEE  (StudySpace revenue)                │
└─────────────────────────────────────────────────────────────────┘
  Create OwnerCharge[type=LISTING_FEE]
     │
     ▼
  Razorpay order → pay → webhook verifies
     │
     ▼
  Create Invoice[doc_type=PLATFORM_TAX_INVOICE]  with 18% GST split
  (CGST+SGST if same state as StudySpace; else IGST)
     │
     ▼
  Post double-entry ledger lines:
    Dr Bank      ₹X (incl. GST)
    Cr Platform Revenue (Listing Fee)   ₹X / 1.18
    Cr GST Output (CGST/SGST or IGST)   ₹X * 0.18 / 1.18
     │
     ▼
  Listing status: DRAFT → VERIFICATION_PENDING
     │
     ▼
  Super admin approval → status=LIVE
     │
     ▼
  Trigger first MaintenanceBillingCycle (next month)

┌─────────────────────────────────────────────────────────────────┐
│      MONTHLY MAINTENANCE FEE  (StudySpace revenue, recurring)    │
└─────────────────────────────────────────────────────────────────┘
  Cron @ 02:00 IST 1st of every month
     │
     ▼
  For every LIVE listing whose billing_anchor_day matches today:
     │
     ▼
  Create OwnerCharge[type=MAINTENANCE_FEE, period=YYYY-MM]
  (idempotency key = listing_id + period)
     │
     ▼
  Generate Invoice[doc_type=PLATFORM_TAX_INVOICE]  (18% GST)
     │
     ▼
  Notify owner → email + in-app + (T-3, T+0, T+3, T+7, T+10)
     │
     ▼
  Payment received? ──No──► T+3:  in-app banner
                         ──► T+7:  visibility_score *= 0.5
                         ──► T+10: status=SUSPENDED_FOR_NONPAYMENT
                                     (existing active bookings honoured;
                                      no new bookings accepted)
                         ──► T+15: hidden from search
                  ──Yes──► Webhook → mark OwnerCharge=PAID
                           → ledger entries
                           → if previously suspended, re-activate

┌─────────────────────────────────────────────────────────────────┐
│              STUDENT BOOKING + PAYMENT                           │
└─────────────────────────────────────────────────────────────────┘
  Student selects cabin/seat/accommodation + duration
     │
     ▼
  POST /bookings/hold  (existing — keep working)
    - DB row lock on Cabin (SELECT ... FOR UPDATE)
    - Set cabin.held_by + hold_expires_at = now+10min
    - Create Booking[status=HELD]
     │
     ▼
  Tax computation (server-side, never trust client):
    base_amount        = duration_price
    owner_gst_amount   = base_amount * owner_gst_rate   (if owner registered or Sec 9(5))
    platform_fee       = base_amount * platform_fee_pct  (optional, configurable)
    platform_fee_gst   = platform_fee * 18%
    gross_payable      = base_amount + owner_gst_amount + platform_fee + platform_fee_gst
     │
     ▼
  POST /razorpay/create-order  (amount = gross_payable in paise)
     │
     ▼
  Student pays
     │
     ▼
  Razorpay webhook → /webhooks/razorpay  (signature verified)
     │
     ▼
  Idempotent handler:
    - Mark Booking PAID, status=ACTIVE
    - Mark Cabin OCCUPIED (cabin.held_by released)
    - Create PaymentTransaction (existing)
    - Create Invoice (see §6 for which doc_type)
    - Compute TCS_payable, TDS_payable (configurable, see §4)
    - Post double-entry ledger lines (see §3)
    - Mark Booking.settlement_status = NOT_SETTLED
     │
     ▼
  Notifications: student receipt, owner booking-alert
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  SETTLEMENT  (T+N days, configurable)            │
└─────────────────────────────────────────────────────────────────┘
  Cron daily @ 03:00 IST
     │
     ▼
  Pick bookings where: settlement_status=NOT_SETTLED
                     AND paid_at <= now - settlement_hold_days
                     AND no open dispute / refund
     │
     ▼
  Aggregate per owner → create SettlementRun
     │
     ▼
  net_payout = sum(owner_payable)
             - sum(platform_fees_due_from_owner)   [maintenance fee can offset]
             - TCS                                  [configurable]
             - TDS                                  [configurable]
     │
     ▼
  RazorpayX payout → webhook → mark Settlement PAID
     │
     ▼
  Owner notified + monthly statement PDF available
     │
     ▼
  Ledger entries posted (see §3)

┌─────────────────────────────────────────────────────────────────┐
│                  REFUNDS / CANCELLATIONS                         │
└─────────────────────────────────────────────────────────────────┘
  Student or Admin initiates → existing Refund flow (kept)
     │
     ▼
  If booking NOT yet settled:
    - Refund directly from collected pool
    - Reverse ledger entries
    - Issue Credit Note (new doc_type=CREDIT_NOTE)
  If booking ALREADY settled:
    - Create RefundDebit against owner_payable (next settlement)
    - If insufficient → flag for super admin recovery
     │
     ▼
  GSTR-1 amendment + credit-note number issued in invoice series
```

---

## 3. The ledger (heart of the system)

Use a **double-entry, append-only** ledger. Every money event creates ≥2 balanced rows. No update / no delete after posting. Corrections are made via reversing entries.

### Account chart (configurable, stored in `chart_of_accounts`)

| Code | Name | Type | Normal balance |
|---|---|---|---|
| 1010 | Razorpay Receivable | Asset | Dr |
| 1011 | Razorpay Settlement A/c | Asset | Dr |
| 1020 | Bank — current | Asset | Dr |
| 2010 | Owner Payable — `{owner_id}` | Liability | Cr |
| 2020 | GST Output — CGST | Liability | Cr |
| 2021 | GST Output — SGST | Liability | Cr |
| 2022 | GST Output — IGST | Liability | Cr |
| 2030 | TCS Payable — CGST | Liability | Cr |
| 2031 | TCS Payable — SGST | Liability | Cr |
| 2032 | TCS Payable — IGST | Liability | Cr |
| 2040 | TDS Payable — 194-O | Liability | Cr |
| 2050 | Refund Provision | Liability | Cr |
| 4010 | Revenue — Listing Fee | Income | Cr |
| 4011 | Revenue — Maintenance Fee | Income | Cr |
| 4012 | Revenue — Facilitation Fee | Income | Cr |
| 5010 | Payment Gateway Charges | Expense | Dr |

> A single `ledger_entries` table with `(txn_group_id, account_code, party_type, party_id, debit, credit, currency, posted_at, source_type, source_id, narration)` is enough. Every business event has one `txn_group_id`; the sum of debits = sum of credits per group is enforced at the service layer and verified by a nightly job.

### Worked ledger postings (referenced by §5 numerical examples)

**Listing fee ₹999 + 18% GST = ₹1,178.82 paid by Owner in Karnataka** (StudySpace also in KA):
```
Dr  Razorpay Receivable          1,178.82
Cr  Revenue — Listing Fee          999.00
Cr  GST Output — CGST                89.91
Cr  GST Output — SGST                89.91
```

**Student pays ₹3,000 (taxable) + ₹360 GST (12%) for a 1-month cabin to a GST-registered owner in same state**:
```
Dr  Razorpay Receivable          3,360.00
Cr  Owner Payable (X)            3,360.00
```
(StudySpace is not a party to the supply; GST flows through to owner. Owner-issued tax invoice via platform UI uses owner's GSTIN.)

**Same payment, but Sec 9(5) applies (unregistered owner, services covered under 9(5))**:
```
Dr  Razorpay Receivable          3,360.00
Cr  Owner Payable                3,000.00
Cr  GST Output — CGST              180.00
Cr  GST Output — SGST              180.00
```
(Here StudySpace is the deemed supplier and owes the GST.)

**TCS @ 0.5% on ₹3,000 net taxable (registered owner case)** posted at settlement:
```
Dr  Owner Payable                   15.00
Cr  TCS Payable — CGST                7.50
Cr  TCS Payable — SGST                7.50
```

**Settlement payout to owner of remaining ₹2,985**:
```
Dr  Owner Payable                2,985.00
Cr  Razorpay Settlement A/c      2,985.00
```

---

## 4. Configurable tax engine

Hardcoding tax rates is the surest way to break compliance. Introduce a `tax_config` table:

| key | example value | meaning |
|---|---|---|
| `platform.home_state` | `"KA"` | Used to decide CGST+SGST vs IGST |
| `platform.gstin` | `"29XXXXX..."` | On every platform tax invoice |
| `gst.platform_fee_rate` | `0.18` | Listing + maintenance + facilitation |
| `gst.platform_fee_sac` | `"998599"` | SAC for online platform support |
| `gst.booking.default_rate` | `0.12` | Default for owner-billed booking when registered |
| `gst.booking.exempt_threshold_monthly` | `20000` | Per-person-per-month residential hostel/PG exemption ceiling (current rule; configurable for future amendments) |
| `gst.booking.sec_9_5_eligible_categories` | `["HOTEL_LIKE","SHORT_STAY"]` | Categories where ECO is deemed supplier when owner is unregistered |
| `tcs.rate_cgst` | `0.0025` | 0.25% (current) |
| `tcs.rate_sgst` | `0.0025` | 0.25% (current) |
| `tcs.rate_igst` | `0.005` | 0.5% (current) |
| `tcs.applies_to_unregistered_owner` | `false` | Per Sec 52 (registered suppliers only) |
| `tds.section_194o_rate` | `0.001` | 0.1% (from Oct 2024) |
| `tds.section_194o_threshold_yearly` | `500000` | Per-owner per-FY exemption ceiling |
| `settlement.hold_days` | `3` | T+N for owner payout |
| `maintenance.overdue.dim_days` | `7` | Reduce visibility |
| `maintenance.overdue.suspend_days` | `10` | Pause new bookings |
| `maintenance.overdue.hide_days` | `15` | Hide from search |

A `TaxEngine` service owns **all** computation. Routers/UI never compute tax. Every computation is also persisted (no recomputation later — frozen at invoice generation) to keep invoices immutable.

---

## 5. Numerical example (end-to-end)

Assumptions: StudySpace GSTIN in Karnataka. Owner GST-registered in Karnataka. Standard rates above.

| Step | Description | Amount (₹) |
|---|---|---|
| O1 | Owner pays one-time listing fee (configured at ₹999 pre-tax) | base 999.00, CGST 89.91, SGST 89.91, **Total 1,178.82** |
| O2 | Owner pays monthly maintenance fee (₹499 pre-tax) | base 499.00, CGST 44.91, SGST 44.91, **Total 588.82** |
| S1 | Student books cabin for 1 month, owner price ₹3,000 | base 3,000.00, CGST @6% 180.00, SGST @6% 180.00, **Total 3,360.00** |
| S2 | TCS @ 0.5% on ₹3,000 (Sec 52 CGST) | CGST-TCS 7.50, SGST-TCS 7.50, **Total 15.00** |
| S3 | TDS u/s 194-O @ 0.1% on ₹3,000 (assume yearly threshold crossed) | **3.00** |
| S4 | PG gateway fee absorbed by StudySpace (assume 2%) | (67.20) — platform expense |
| S5 | Settlement to owner = 3,360 − 15 (TCS) − 3 (TDS) − any deductible maintenance owed | **3,342.00** if maintenance fee separately collected |
| S6 | Platform revenue **recognized** this period | Listing 999 + Maint 499 = **1,498.00** (NOT 3,360!) |
| S7 | Platform GST output liability | 89.91 + 89.91 + 44.91 + 44.91 = **269.64** + (180 + 180 if Sec 9(5)) |
| S8 | TCS + TDS to deposit | TCS 15.00 (GSTR-8), TDS 3.00 (26Q) |

If the **owner were unregistered** and the category is Sec 9(5) eligible: StudySpace becomes the deemed supplier — issues its own invoice to student, owes 12% GST. Owner gets net of GST. TCS does **not** apply (only registered suppliers).

If the **owner were unregistered** and Sec 9(5) does **not** cover the category: no GST on the supply. Receipt reads "Supplier is not registered under GST; no tax invoice issued."

---

## 6. Invoice / receipt logic and structure

Use a single `documents` table (renamed conceptually from `invoices` — add columns, don't break) with a `doc_type` enum so all artefacts share one numbering authority:

```
PLATFORM_TAX_INVOICE        (StudySpace → Owner: listing/maint/facilitation fees)
OWNER_TAX_INVOICE           (Owner → Student, generated by platform using owner GSTIN)
ECO_TAX_INVOICE             (StudySpace → Student, Sec 9(5) deemed supplier)
NON_GST_RECEIPT             (Owner unregistered + Sec 9(5) not applicable)
CREDIT_NOTE                 (Refunds / cancellations)
SETTLEMENT_STATEMENT        (Monthly per owner)
```

Each doc_type has its **own** fiscal-year sequential series (mandatory under GST):
- `SS/PLF/24-25/000001` — Platform listing/maintenance fee
- `SS/OBI/24-25/000001` — Owner booking invoice
- `SS/ECO/24-25/000001` — ECO booking invoice
- `SS/RCT/24-25/000001` — Non-GST receipt
- `SS/CN/24-25/000001`  — Credit note
- `SS/STM/24-25/000001` — Settlement statement

Numbers are issued by an atomic Postgres sequence (or `SELECT ... FOR UPDATE` row in SQLite) per series — never timestamp-based. Replaces the current `timestamp:06d` in `invoice.py:49` (which can collide).

### Required fields per document

**A) Platform tax invoice (Listing / Maintenance fee)**
- Supplier: StudySpace name, address, GSTIN, state code
- Recipient: Owner name, billing address, GSTIN (if any), state code, place of supply
- Line item: description ("Listing fee — {listing_name}" or "Platform maintenance fee — {YYYY-MM} — {listing_name}"), SAC 998599, qty, rate
- Taxable value, CGST/SGST/IGST split, total
- Words for total, signature block
- Reverse charge: "No"
- HSN/SAC mandatory; e-invoice IRN/QR placeholder for when AATO > ₹5cr

**B) Owner tax invoice (booking) — owner is GST registered**
- Supplier: Owner's legal name, address, GSTIN, state
- Recipient: Student name + (optional) student GSTIN
- Description: "Accommodation — {venue} — {seat} — {start_date} to {end_date}"
- SAC: 996311 (room/unit accommodation) or 9963 / 9985 / 9967 depending on category — set per listing
- Tax split per place-of-supply rules
- **Footer**: "Issued by StudySpace Technology Pvt Ltd on behalf of {Owner Legal Name}. StudySpace is a facilitating platform under Section 2(45) of CGST Act and is not the supplier of this service. Owner is solely responsible for the supply."

**C) ECO tax invoice (Sec 9(5)) — owner unregistered + category in 9(5) list**
- Supplier shown as: StudySpace Technology Pvt Ltd (with its own GSTIN)
- A note: "Tax invoice issued by the e-commerce operator under Section 9(5) of CGST Act, 2017. Underlying supplier of accommodation: {Owner Name}."
- Tax rate per the underlying supply
- Settlement to owner is **net of GST** (owner doesn't see this GST as receivable)

**D) Non-GST receipt — owner unregistered + Sec 9(5) not applicable**
- Title: "Booking Receipt (Not a Tax Invoice)"
- Supplier: Owner name (no GSTIN). Footer: "Supplier is not registered under GST. No tax is charged on this supply. StudySpace acts only as a facilitating platform between supplier and recipient."
- No CGST/SGST/IGST line items
- Still has unique series number for audit

**E) Owner monthly settlement statement** — see §7

---

## 7. Owner monthly settlement statement (recommended layout)

```
StudySpace — Settlement Statement
Statement #: SS/STM/25-26/000142          Period: 1–31 May 2026
Owner: Acme PG (GSTIN 29ABCDE1234F1Z5)    Bank A/c: HDFC ****4421
─────────────────────────────────────────────────────────────────
A. Gross bookings collected on your behalf      ₹  84,000.00
   (32 bookings — see appended ledger)
B. GST included in (A) and owed by you            (12,600.00)
   to govt (declared in your GSTR-1)
C. Net taxable value (A − B)                      71,400.00
D. TCS u/s 52 CGST @ 0.5%                            (357.00)
E. TDS u/s 194-O IT Act @ 0.1%                       (71.40)
F. Refunds processed against you in period           (3,000.00)
G. Platform deductions
   - Maintenance fee May (incl. GST)                  (588.82)
   - Listing fee (already paid)                            -
H. Net payout                                     ₹ 80,382.78
   UTR: HDFC1234567890 on 03-Jun-2026
─────────────────────────────────────────────────────────────────
Appendix: booking-level ledger
Appendix: GSTR-8 TCS certificate reference
```

---

## 8. Database / table changes (additive only)

### 8.1 Alter existing tables (non-breaking)

- `users` — add nullable columns:
  - `legal_name VARCHAR`, `pan VARCHAR(10)`, `gstin VARCHAR(15)`, `gst_registration_type VARCHAR(20)` (REGULAR / COMPOSITION / UNREGISTERED), `business_state_code VARCHAR(2)`, `bank_account_holder`, `bank_account_number`, `bank_ifsc`, `bank_verified_at DATETIME`, `kyc_status VARCHAR(20)` (PENDING / VERIFIED / REJECTED), `kyc_reviewed_by`, `kyc_reviewed_at`

- `reading_rooms`, `accommodations` — add nullable columns:
  - `gst_category VARCHAR(30)` (HOTEL_LIKE / SHORT_STAY / HOSTEL_PG / READING_ROOM / OTHER)
  - `gst_sac VARCHAR(10)`
  - `gst_rate_override NUMERIC(5,4)` (nullable; null = use default)
  - `billing_anchor_day SMALLINT` (1–28)
  - `maintenance_status VARCHAR(20)` (CURRENT / OVERDUE / SUSPENDED_FOR_NONPAYMENT)
  - `visibility_score NUMERIC(4,3) DEFAULT 1.0`

- `bookings` — add nullable columns:
  - `base_amount NUMERIC(12,2)`, `gst_cgst NUMERIC(12,2)`, `gst_sgst NUMERIC(12,2)`, `gst_igst NUMERIC(12,2)`, `gst_rate_applied NUMERIC(5,4)`, `gst_treatment VARCHAR(20)` (OWNER_REGISTERED / SEC_9_5 / EXEMPT / NOT_REGISTERED), `place_of_supply_state VARCHAR(2)`, `frozen_tax_snapshot_id` (FK to a `tax_snapshots` row capturing the exact tax config used)

- `invoices` — add nullable columns:
  - `doc_type VARCHAR(30)` (default `OWNER_TAX_INVOICE` for new rows; legacy rows backfilled as `LEGACY` via a one-time script)
  - `series_code VARCHAR(10)` (PLF / OBI / ECO / RCT / CN / STM)
  - `fiscal_year VARCHAR(7)` (e.g., `25-26`)
  - `sequence_no INTEGER`
  - `supplier_party_id`, `recipient_party_id` (FK to a new `parties` snapshot table — frozen name/address/GSTIN at issue time)
  - `place_of_supply_state VARCHAR(2)`
  - `cgst NUMERIC(12,2)`, `sgst NUMERIC(12,2)`, `igst NUMERIC(12,2)`, `cess NUMERIC(12,2)`
  - `hsn_sac VARCHAR(10)`
  - `irn VARCHAR(64)` (for future e-invoicing), `qr_payload TEXT`
  - Unique index on `(series_code, fiscal_year, sequence_no)`

### 8.2 New tables

```sql
chart_of_accounts(code PK, name, type, normal_side, is_active)

invoice_series_counter(series_code, fiscal_year, last_no)  -- atomic counter

parties(id PK, party_type, party_ref_id, legal_name, address, gstin, state_code, snapshot_at)

owner_charges(
  id PK, owner_id FK, listing_id, listing_type, charge_type ENUM(LISTING_FEE,MAINTENANCE_FEE,FACILITATION_FEE),
  period_key VARCHAR(7),  -- 'YYYY-MM' for recurring, NULL for one-time
  base_amount, gst_amount, total_amount, currency,
  status ENUM(DRAFT,DUE,PAID,WAIVED,FAILED), due_date,
  invoice_id FK,
  created_at, paid_at,
  UNIQUE(owner_id, charge_type, period_key, listing_id)   -- idempotency
)

tax_snapshots(id PK, snapshot_at, payload JSON)   -- frozen tax_config used by this txn

settlement_runs(
  id PK, owner_id FK, period_start, period_end, status,
  gross, refunds, platform_deductions, tcs_cgst, tcs_sgst, tcs_igst, tds_194o,
  net_payout, payout_ref, payout_at
)

settlement_lines(
  id PK, run_id FK, booking_id FK, base_amount, owner_gst, tcs, tds, net
)

ledger_entries(
  id PK, txn_group_id UUID, posted_at, account_code FK,
  party_type, party_id, debit NUMERIC(14,2), credit NUMERIC(14,2),
  currency, source_type, source_id, narration,
  CHECK ( (debit=0) <> (credit=0) )
)
-- nightly job asserts SUM(debit)=SUM(credit) per txn_group_id

webhook_events(
  id PK, gateway, event_id UNIQUE, payload JSON, signature, status, received_at, processed_at
)   -- idempotent webhook handling

tax_config(key PK, value JSON, updated_by, updated_at)
```

### 8.3 Why not rename existing tables

`Invoice` already has rows in production. We extend it. Same for `SubscriptionPlan` — we keep it as the *catalog* of listing-fee plans and add `OwnerCharge` to represent the *actual* charge (one-time or recurring). Existing booking + cabin hold logic in [routers/bookings.py](../backend/app/routers/bookings.py) and [routers/razorpay.py](../backend/app/routers/razorpay.py) stays — we only **append** ledger postings + tax breakdown after the existing PAID write.

---

## 9. Backend service changes

### 9.1 New service modules (under `backend/app/services/`)

| Module | Purpose |
|---|---|
| `tax_engine.py` | Pure functions: compute GST + TCS + TDS given inputs; loads `tax_config` once per request; outputs frozen `TaxSnapshot` |
| `ledger_service.py` | `post_entries(txn_group_id, entries[])`; validates balance; one writer for all financial events |
| `invoice_service.py` | `issue(doc_type, party_data, lines, tax_snapshot)`; atomic series number allocation; PDF render; emits `INVOICE_ISSUED` event |
| `owner_billing_service.py` | Listing fee + recurring maintenance fee charge generation; idempotent monthly cron |
| `settlement_service.py` | Daily eligibility scan + payout aggregation + RazorpayX call + ledger post |
| `webhook_service.py` | Razorpay + RazorpayX webhook intake; signature verify; idempotent dispatch via `webhook_events` |
| `compliance_service.py` | KYC review, owner state machine, visibility/suspension transitions |
| `refund_service.py` | Extends existing `Refund` to issue credit notes + reverse ledger |
| `gst_export_service.py` | Build GSTR-1 / GSTR-8 / 26Q CSVs from ledger |

### 9.2 New routers

| Router | Endpoints |
|---|---|
| `routers/owner_billing.py` | `GET/POST /owner/charges`, `POST /owner/charges/{id}/pay`, `GET /owner/statements` |
| `routers/settlements.py` | `GET /admin/settlements`, `POST /admin/settlements/run`, `GET /owner/settlements`, `GET /owner/settlements/{id}/pdf` |
| `routers/ledger.py` | `GET /admin/ledger` (filter by account/party/period/source), CSV export |
| `routers/webhooks_razorpay.py` | `POST /webhooks/razorpay` (replaces inline verify logic — current `/razorpay/verify` continues to work for client-side flows, but webhook is now the source of truth) |
| `routers/owner_kyc.py` | KYC submit/review/reupload |
| `routers/tax_config.py` | super-admin CRUD for `tax_config` |
| `routers/gst_reports.py` | GSTR-1, GSTR-8, 26Q CSV downloads |

### 9.3 Background workers (APScheduler or RQ)

| Job | Schedule | What it does |
|---|---|---|
| `expire_held_bookings` | every 60s | Release `Cabin.held_by` where `hold_expires_at < now()` (currently not enforced) |
| `generate_maintenance_charges` | 02:00 1st of month IST | Create idempotent `OwnerCharge` for every LIVE listing |
| `maintenance_dunning` | 09:00 daily IST | Send reminders, dim visibility, suspend per matrix in §4 |
| `settlement_run` | 03:00 daily IST | Aggregate eligible bookings → payout |
| `ledger_integrity_check` | 04:00 daily IST | Assert per-`txn_group_id` debits=credits; alert on mismatch |
| `webhook_retry` | every 5 min | Re-process `webhook_events` stuck in PENDING |
| `gst_filing_reminder` | 11th, 20th monthly | Email finance team: pull GSTR-1, GSTR-8 |

### 9.4 Key invariants enforced in code

1. **Atomic booking confirmation**: `BEGIN; SELECT cabin FOR UPDATE; assert AVAILABLE; create booking; update cabin; insert ledger; commit;`
2. **Webhook idempotency**: `INSERT INTO webhook_events ... ON CONFLICT (event_id) DO NOTHING`. If insert affected 0 rows → already processed → return 200 OK without side effects.
3. **Invoice immutability**: invoice rows are insert-only. Corrections issue `CREDIT_NOTE`.
4. **Tax snapshot freezing**: every tax computation persists the rate set used (`tax_snapshots`) so an audit two years later can reproduce the math.
5. **Owner payable separation**: booking gross is **never** posted to a revenue account. Code-level lint via a unit test that asserts no ledger entry credits `4010-4012` from a `source_type='BOOKING'`.

---

## 10. Frontend / admin dashboard changes

### 10.1 Owner (`UserRole.ADMIN`) — additions

| Page | Purpose |
|---|---|
| `/admin/onboarding/kyc` | PAN / GSTIN / bank entry + status banner; blocking until VERIFIED |
| `/admin/billing` (extend existing) | Charges due, pay-now, payment history with `PLATFORM_TAX_INVOICE` downloads |
| `/admin/settlements` | List of settlement runs, statement PDF, line-level ledger |
| `/admin/financials` (extend existing) | Add **revenue split visualization**: my-revenue vs platform-fees vs taxes vs refunds |
| `/admin/listings/:id/billing` | Per-listing billing config: maintenance fee plan, gst_category, gst_rate_override (super-admin only) |

### 10.2 Student — minimal changes

- Invoice/receipt download page must now switch view based on `doc_type` (clearly label "Owner Tax Invoice", "Platform Tax Invoice under Sec 9(5)", or "Booking Receipt — No GST").
- Refund page: show credit-note number once issued.

### 10.3 Super admin — additions

| Page | Purpose |
|---|---|
| `/super-admin/tax-config` | CRUD on `tax_config` keys + audit log |
| `/super-admin/ledger` | Full ledger explorer (filter by account, party, period, source) + CSV export |
| `/super-admin/settlements` | All settlement runs, retry payout, override deductions (audited) |
| `/super-admin/gst-reports` | Download GSTR-1, GSTR-8, 26Q CSVs for any period |
| `/super-admin/owners/:id/compliance` | Owner KYC review + force-suspend with reason |
| `/super-admin/invoice-series` | Inspect series counters, manage future-FY series |

All amounts on every screen render via a shared `<Money>` component that uses a fixed-precision (`Decimal`-equivalent) string from the API — never JS floats — to prevent rounding drift visible to CAs.

---

## 11. Edge cases and how each is handled

| Case | Behavior |
|---|---|
| **Owner GST-registered vs unregistered** | `TaxEngine` branches on `owner.gst_registration_type`. Registered → owner-issued invoice + TCS applies. Unregistered + Sec 9(5) category → ECO invoice + GST owed by platform + no TCS. Unregistered + non-9(5) → non-GST receipt |
| **Failed student payment** | Razorpay webhook `payment.failed` → keep `Booking.status=HELD` and let `expire_held_bookings` job release the cabin at `hold_expires_at`. No ledger entry created. |
| **Successful payment but booking not confirmed** (race / crash mid-handler) | Webhook is idempotent. On retry: if `Booking` not yet ACTIVE but `PaymentTransaction` row exists → resume from "mark booking ACTIVE" step. Reconciliation job flags `PaymentTransaction` with no matching `Booking.PAID` within 10 min. |
| **Refund after settlement** | `RefundDebit` created against future settlement. If `owner_payable_running_balance < refund_amount` → state `RECOVERY_PENDING`, blocks new payouts, super-admin alert. Issue `CREDIT_NOTE`; report in next GSTR-1. |
| **Owner monthly fee unpaid** | Day matrix in §4. Existing active bookings always honoured. New booking attempts on suspended listings return `LISTING_PAUSED_BY_PLATFORM` and are not allowed even at API level. |
| **Property paused while student has active bookings** | Listing hidden from search; existing bookings still resolve, settlements continue, refunds still processed. Owner-billing screen shows "Cleared overdue → listing returns to LIVE in next cron." |
| **Wrong availability count** | `expire_held_bookings` + a reconciliation job that recomputes `cabin.status` from booking history nightly; mismatches logged and self-healed. Don't trust client state — always re-derive from DB. |
| **Duplicate invoice generation** | `owner_charges` unique key `(owner_id, charge_type, period_key, listing_id)`. Series numbers from atomic counter ensure no collisions (replaces timestamp-mod approach in `models/invoice.py:49`). PDF re-renders are idempotent — same invoice_id always renders identical bytes. |
| **Payment gateway webhook failure / out-of-order delivery** | `webhook_events` is the source of truth; retries are safe. Out-of-order events handled because each event uses Razorpay's `event.id` as idempotency key and side-effects are conditional on current state. |
| **Razorpay says success, server says failure** | Mismatch alert. Admin tool to manually confirm or refund. Never silently drop. |
| **Tax rate change mid-period** | New `tax_config` value, super admin "Effective from" date. New `tax_snapshots` row per transaction; already-issued invoices unaffected. |
| **Student GST registration** (B2B booking, future) | Optional GSTIN on booking; if present, owner's invoice includes student's GSTIN → student claims ITC. |
| **Owner across states** | `place_of_supply` derived from venue state. Different from owner's home state allowed; CGST+SGST vs IGST decided correctly. |
| **Negative settlement** (refunds + maintenance > collections) | Settlement run records `net_payout < 0`. No payout sent; balance carried; owner notified to top up via `OwnerCharge` of type `RECOVERY`. |
| **Cabin held but user closes browser** | 10-min hold expires; job releases. New entry, no ledger touched. |

---

## 12. Acceptance criteria

A reasonable PM/QA can verify the system by checking each item below.

### 12.1 Functional
1. An owner can complete KYC; until KYC is `VERIFIED`, no listing can move to `LIVE`.
2. Paying a listing fee yields a `PLATFORM_TAX_INVOICE` with the right CGST/SGST/IGST split based on owner state.
3. On the 1st of each month at 02:00 IST, every LIVE listing gets exactly one `MAINTENANCE_FEE` `OwnerCharge` for that month — and re-running the job creates zero new charges.
4. Maintenance overdue: at T+3 / T+7 / T+10 / T+15 days the side-effects in §4 are observable in DB + UI + emails.
5. A student booking generates correct invoice type (`OWNER_TAX_INVOICE` / `ECO_TAX_INVOICE` / `NON_GST_RECEIPT`) based on the matrix in §6.
6. A booking ledger group sums to zero (Σ debit = Σ credit).
7. Settlement run for an owner = Σ owner-payable − refunds − TCS − TDS − platform deductions; payout UTR recorded.
8. Refund before settlement reverses original ledger group and emits a `CREDIT_NOTE`.
9. Refund after settlement creates `RefundDebit`, deducted from next settlement, with credit note.
10. Suspended listing rejects new booking requests with `LISTING_PAUSED_BY_PLATFORM` HTTP 409; existing active bookings still resolve.
11. Cabin hold expires within 60s of `hold_expires_at`; cabin returns to `AVAILABLE`.

### 12.2 Compliance / audit
12. Every invoice series has strictly monotonic `sequence_no` per `fiscal_year` with no gaps.
13. Every monetary transaction has at least one corresponding `ledger_entries` group and the integrity job is green.
14. GSTR-1 export reconciles to ledger: Σ output GST in ledger = Σ tax on outward supplies in GSTR-1.
15. GSTR-8 export reconciles to ledger: Σ TCS payable in ledger = Σ TCS in GSTR-8.
16. 26Q export reconciles to ledger: Σ TDS payable = Σ in 26Q.
17. Changing any value in `tax_config` doesn't alter any already-issued invoice's amounts (proven via test that snapshots config and re-fetches old invoice).
18. Webhook replay test: same `event.id` posted 50× produces 1 booking, 1 invoice, 1 ledger group.

### 12.3 Non-functional
19. All money values stored as `NUMERIC(14,2)` (or paise-int) in DB; API exposes strings; UI uses fixed-precision rendering.
20. Existing student booking + payment flow (cabin map → hold → Razorpay → confirm) still works unchanged when no tax config is set (defaults: 0% GST, owner is unregistered, no TCS/TDS).
21. No existing tables renamed; no NOT NULL columns added without defaults; all new columns nullable or with defaults — production migrations are zero-downtime.
22. Admin can disable the entire new accounting layer via feature flag `accounting.enabled=false` — system falls back to existing behavior. (Useful for staged rollout.)

### 12.4 Rollout safety
23. New code path is opt-in per listing via `gst_category` being non-null. Null → legacy behavior (no GST line items, existing invoice format).
24. One-time backfill script tags all existing `invoices` rows with `doc_type='LEGACY'` and assigns a `LEGACY` series number — preserves historical data.
25. Feature flag matrix: `feature.owner_kyc`, `feature.recurring_maintenance`, `feature.settlement_engine`, `feature.gst_invoices`, `feature.tcs_tds` — each independently togglable for canary release.

---

## 13. Build sequence (recommended)

1. **Foundation, zero behavior change** — add `chart_of_accounts`, `ledger_entries`, `tax_config`, `tax_snapshots`, `webhook_events`, `parties`, `invoice_series_counter`. Migrate existing invoice rows to `LEGACY`.
2. **Ledger shadow** — start writing ledger entries for *existing* booking flow without changing the user-facing flow. Run integrity job daily. Verify books reconcile.
3. **Tax engine + invoice doc_types** — render new invoice formats behind `feature.gst_invoices`. A/B test on a single owner.
4. **Owner KYC + listing fee under new pipeline** — new owners onboard via new flow; old owners grandfathered.
5. **Monthly maintenance fee engine** — turn on the cron, dunning matrix, suspensions.
6. **Settlement engine** — turn on T+N payouts; until then, owners receive via existing manual route.
7. **TCS/TDS, GSTR-1/8/26Q exports** — last, once data quality is proven over ≥ 2 months.

---

## 14. Items deliberately out of scope (call out for sprint planning)

- E-invoicing (IRN + QR via NIC IRP) — required only when AATO > ₹5cr; schema includes the fields but generation is Phase 2.
- Multi-currency.
- Owner-side wallet / advances.
- Composition scheme owner billing peculiarities (1% turnover tax) — flag in `gst_registration_type` already, but no special invoice yet.
- Reverse-charge mechanism scenarios (legal / advocate inputs etc.).
- ITC reconciliation on platform-side input GST (separate finance project).

---

*Document author: design draft. Numbers above are illustrative; final rates must be confirmed by a practising CA before go-live and stored in `tax_config` — code reads them, code does not assume them.*
