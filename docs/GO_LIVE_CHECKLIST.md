# StudySpace Accounting — Go-Live Checklist

> Operational gate document. Do **not** enable any production accounting flag
> until every check below passes. The friend's directive (and now StudySpace
> policy): _"Freeze new feature development. Next step is operational
> validation, not more code."_

---

## Three gates (all required)

### Gate 1 — Synthetic canary pack reviewed by CA

- [ ] Run `python -m scripts.canary_walkthrough`
- [ ] Verify `backend/canary_output/` contains all 17 artifacts (3 CSVs + 12 PDFs + `summary.md` + `CA_REVIEW_NOTES.md`)
- [ ] Zip `backend/canary_output/` → `studyspace_ca_review_pack_<YYYYMMDD>.zip`
- [ ] Email pack to the firm's CA
- [ ] **Receive `CA_REVIEW_NOTES.md` back with all 7 questions answered + signed**
- [ ] Update `tax_config` keys to match CA's answers via super-admin UI (no redeploy):
  - `gst.booking.default_rate`
  - `gst.booking.default_sac`
  - `gst.booking.exempt_threshold_monthly`
  - `gst.booking.sec_9_5_eligible_categories`
  - `tcs.enabled` / `tds.section_194o_enabled` (whichever the CA confirmed)
- [ ] Re-run `canary_walkthrough` and confirm the new rates appear in the new artifacts

### Gate 2 — Real-listing canary validator passes on staging

- [ ] Create one CA-approved canary listing on staging (registered owner, KYC verified, real bank details, real Razorpay test key)
- [ ] Run:
      ```
      python -m scripts.canary_validate_listing \
        --listing-type accommodation \
        --listing-id <real-canary-listing-id> \
        --expected-price 2500 \
        --archive
      ```
- [ ] All 10 steps return PASS (Step 5 is allowed to SKIP if the legacy invoice path is used)
- [ ] Bonus integrity check returns PASS
- [ ] Archive bundle `staging_canary_<id>_<ts>.zip` is generated in `backend/canary_output/`
- [ ] Bundle contains all five required artifacts (per the operational directive):
  - `validation_<id>_<ts>.json`
  - `invoice_<SS_*>.pdf`
  - `settlement_<id>.pdf`
  - `credit_note_<SS_CN_*>.pdf`
  - `ledger.csv`
- [ ] Bundle is archived to whatever long-term store the team uses (GCS bucket, S3, internal drive)

### Gate 3 — Staging rehearsal without manual DB correction

- [ ] Repeat Gate 2 a second time with a different listing, owner, and tax category
- [ ] **No** rows were manually edited in the DB during the run
- [ ] **No** flags were toggled mid-run
- [ ] Both validation runs are archived

---

## Production flag enable order

After all three gates pass, enable flags one at a time in this exact order.
After each flip, wait a minimum of 48 hours and verify booking flow + ledger
integrity before flipping the next.

1. `accounting.enabled = true`  → shadow ledger now writes for real bookings
2. `feature.gst_invoices = true`  → new doc_types render in production
3. `feature.recurring_maintenance = true`  → monthly cron starts; verify the first cycle
4. `feature.credit_notes = true`  → refund approvals issue credit notes
5. `tcs.enabled = true` (only if CA-confirmed in CA_REVIEW_NOTES.md)
6. `tds.section_194o_enabled = true` (only if CA-confirmed in CA_REVIEW_NOTES.md)

**Stays off indefinitely** until a separate Phase 8 decision:
- `feature.per_listing_price_mode`  (GST_EXTRA per-listing override)
- `settlement.offset_maintenance`   (auto-deduct unpaid maintenance from payouts)
- GSTR-1 / GSTR-8 / 26Q export endpoints (not built; future Phase 8)

---

## Pre-deploy guardrails

Every PR / deploy must pass:
```
python -m scripts.check_safety_flags
```

This script reads `tax_config` and exits non-zero if any of the protected
flags above are on. Once a flag is intentionally enabled, the deploy
operator must opt in explicitly:

```
python -m scripts.check_safety_flags --allow accounting.enabled
```

That `--allow` is the human gate — anyone reading the deploy log can see
exactly which flag was bypassed and audit the corresponding CA sign-off.

---

## What "shadow / super-admin-reviewed only" means in practice

While all flags are OFF:

- The existing student booking flow runs **unchanged** — same Razorpay order,
  same amount, same invoice template (the legacy `Invoice` row).
- The shadow accounting code path is short-circuited at
  `AccountingShadow.shadow_post_booking_paid` (the first thing it checks is
  `accounting_enabled(config)`).
- The monthly maintenance cron is short-circuited at
  `generate_maintenance_charges_for_today` (first config check).
- The credit-note hook in `update_refund_status` is short-circuited at
  `credit_notes_enabled(db)`.
- Settlement cron still runs every night, but with no shadow-posted bookings
  it has nothing to aggregate.
- Super admin can manually flip any flag temporarily on staging via
  `/super-admin/tax-config` to test specific scenarios without redeploying.

---

## When to update this checklist

This document is the source of truth for the operational gates. Update it
when:

- The CA returns the form and any answer changes the config keys above
- An additional gate is required for a new feature (e.g., Phase 8 GSTR exports)
- A production incident reveals a missing pre-deploy check

PRs that touch this file must be reviewed by someone outside the engineering
team (CA, founder, or compliance lead).
