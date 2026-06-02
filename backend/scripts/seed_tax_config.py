"""Seed default tax_config keys.

These defaults reflect the business rules confirmed for this rollout:
- Platform fees: 18% GST (added on top of the configured pre-tax price)
- Booking GST: 18% by default, but **prices in app are GST-inclusive** —
  the engine reverse-calculates GST out of the displayed amount.
- TCS / TDS: configurable, **disabled by default**.

Super admin can change any value via /admin/tax-config without redeploy.

Idempotent: existing keys are NOT overwritten.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.tax_config import TaxConfig


# Master kill switch + feature flags first — explicit so a CA can see them.
DEFAULTS: list[tuple[str, object, str]] = [
    # --- Master switches ---
    ("accounting.enabled",                  False,
     "Master kill switch — when false, the new accounting layer is a no-op."),
    ("feature.recurring_maintenance",       False,
     "Enable monthly maintenance billing per listing (set per-listing via billing_anchor_day)."),
    ("feature.gst_invoices",                False,
     "Render new GST-aware invoice formats (PLATFORM_TAX_INVOICE etc)."),
    ("feature.per_listing_price_mode",      False,
     "Honour the per-listing `price_display_mode` column. When OFF, the global "
     "`gst.booking.pricing_is_inclusive` flag wins for every listing. Turn ON "
     "only after the booking router has been updated to multiply by (1+rate) "
     "for GST_EXTRA listings."),
    ("feature.credit_notes",                False,
     "On refund approval, automatically issue a CREDIT_NOTE document and post "
     "the reversing ledger group. OFF by default so existing refund flow is "
     "unchanged during canary."),

    # --- Phase 1 intelligence layer (event firehose) ---
    ("events.enabled",                      False,
     "Master kill switch for the behavioral event firehose. When OFF, no row "
     "is ever inserted into user_events. Flip ON after Phase 1 review."),
    ("events.anonymous_allowed",            True,
     "Record events from pre-login sessions (anonymous_session_id only). "
     "Useful for funnel analysis. Set False to require login for tracking."),
    ("events.batch_size_limit",             100,
     "Max events accepted per POST /events/batch call. Larger batches are 400'd."),
    ("events.retention_days",               365,
     "Soft retention target (informational). Hard expiry job is Phase 2."),
    ("consent.required_for_analytics",      False,
     "If True, authenticated users must opt in via allow_analytics_tracking "
     "before any of their events are recorded. False = legitimate-interest "
     "default (most analytics platforms work this way; users still opt out)."),

    # --- Phase 2 intelligence layer (profile aggregation + intent scoring) ---
    ("intelligence.profile_aggregation_enabled", False,
     "Master switch for the derived user_intelligence_profiles table. When "
     "OFF, the rebuild service is a no-op and no rows are written. Flip ON "
     "after privacy review of the scoring rules."),
    ("intelligence.profile_window_days",         90,
     "How many days of events back the profile aggregator scans."),
    # Intent weights (Phase 2 scoring). Adjustable without redeploy.
    ("intent.weight.search",                     1,  "Weight for a SEARCH event."),
    ("intent.weight.view",                       2,  "Weight for a VIEW event."),
    ("intent.weight.filter",                     2,  "Weight for a FILTER event."),
    ("intent.weight.save",                       4,  "Weight for a SAVE event."),
    ("intent.weight.compare",                    3,  "Weight for a COMPARE event."),
    ("intent.weight.contact",                    5,  "Weight for a CONTACT event."),
    ("intent.weight.availability_check",         5,
     "Weight for an availability check (event_name contains 'availability')."),
    ("intent.weight.booking_start",              8,
     "Weight for a booking-start event (event_name starts with 'booking.start')."),
    ("intent.weight.payment_fail",              10,
     "Weight for a payment-failed or payment-abandoned event."),
    # Intent classification thresholds
    ("intent.threshold_medium",                  5,  "Raw score for MEDIUM_INTENT."),
    ("intent.threshold_high",                   15,  "Raw score for HIGH_INTENT."),
    ("intent.threshold_hot",                    30,
     "Raw score for HOT_LEAD (booking-start / payment-fail also force HOT_LEAD)."),

    # --- Phase 3 intelligence layer (rule-based recommendations) ---
    ("recommendations.enabled",                 False,
     "Master switch. When OFF every recommendation endpoint returns []. "
     "Flip ON after Phase 3 review."),
    ("recommendations.log_impressions",         False,
     "When ON every served recommendation writes a row to recommendation_logs "
     "for Phase 4 attribution. Off by default to save DB churn during testing."),
    # Ranking weights (additive — higher = appears earlier)
    ("recommendations.weight.city_match",        30.0,
     "Bonus when listing city matches profile.preferred_city."),
    ("recommendations.weight.location_match",    20.0,
     "Bonus when listing neighborhood matches profile.preferred_locations."),
    ("recommendations.weight.price_match",       15.0,
     "Bonus when listing price falls within the user's preferred band (30% slack)."),
    ("recommendations.weight.same_city",         20.0,
     "Item-based: bonus when 'similar' listing shares the source's city."),
    ("recommendations.weight.same_category",     15.0,
     "Item-based: bonus when 'similar' listing shares the source's gst_category."),
    ("recommendations.weight.trending_hit",       1.0,
     "Per-event multiplier for trending score."),
    ("recommendations.weight.admin_priority",   100.0,
     "Per-priority-level multiplier from listing.recommendation_priority."),
    ("recommendations.weight.sponsored",         20.0,
     "Bonus when listing.is_sponsored and sponsored_until is still active."),

    # --- Phase 4A intelligence layer (rule-based segments) ---
    ("segments.enabled",                        False,
     "Master switch for segment evaluation. When OFF, the nightly recompute "
     "skips and no memberships move. Flip ON after Phase 4A review."),
    ("segments.window_days",                       30,
     "Days back the predicates scan event history. Profile data is not "
     "windowed because the profile itself is already aggregated."),

    # --- Phase 4B intelligence layer (campaigns + attribution) ---
    ("campaigns.enabled",                       False,
     "Master switch for campaign delivery + attribution. When OFF the enqueue "
     "service is a no-op and the booking-attribution hook is a no-op. "
     "Flip ON after Phase 4B review."),
    ("campaigns.attribution_window_days",          7,
     "How many days back the booking attribution hook scans for the most "
     "recent CLICKED delivery. Last-click-wins inside this window."),

    # --- Phase 4C intelligence layer (trigger-based notification automation) ---
    ("notification_automation.enabled",         False,
     "Master switch for the trigger-based rule engine + dispatcher. When "
     "OFF, evaluate_rule is a no-op, dispatch_pending is a no-op, and the "
     "30-min scheduler job exits immediately. Flip ON after Phase 4C review."),
    ("notification_automation.dispatch_batch_size", 200,
     "Max QUEUED deliveries the cron job will dispatch per tick."),

    # --- Phase 4D intelligence layer (recommendation attribution) ---
    ("recommendations.attribution_enabled",     False,
     "Master switch for recommendation_log → booking attribution. When OFF "
     "the booking-attribution hook is a no-op and the click endpoint still "
     "stamps clicked_at but no conversion is recorded. Flip ON after Phase "
     "4D review."),
    ("recommendations.attribution_window_days", 7,
     "How many days back the booking attribution hook scans for the most "
     "recent matching recommendation_log row (click preferred, impression "
     "fallback)."),

    # --- Phase 5 intelligence layer (insights dashboards) ---
    ("insights.enabled",                        False,
     "Master switch for the aggregated owner + super-admin insight "
     "dashboards. When OFF the services return None and the API renders an "
     "empty state. Flip ON after Phase 5 review."),
    ("insights.k_anonymity_floor",              5,
     "Listing-level conversion rates are suppressed (returned as null) when "
     "the listing has fewer than this many distinct viewers in the window. "
     "Privacy floor — prevents inferring a single user's behaviour from "
     "owner-facing metrics."),

    # --- Phase 6 intelligence layer (experiments + ML) ---
    ("experiments.enabled",                     False,
     "Master switch for the A/B experiment framework. When OFF, get_variant "
     "always returns None (so all callers fall through to control) and "
     "record_exposure/conversion are no-ops."),
    ("ml.feature_export_enabled",               False,
     "When OFF, the feature-export CSV endpoint streams only the header row. "
     "Independent from experiments.enabled — exports may be useful before "
     "live A/B testing is on."),
    ("ml.hash_salt",                            "studyspace-v1",
     "Salt mixed into the SHA-256 of user_id for the exported CSV's "
     "user_hash column. Rotating the salt re-anonymises future exports."),

    # --- Platform identity ---
    ("platform.legal_name",                 "StudySpace Technology Pvt Ltd",
     "Legal name shown on platform tax invoices."),
    ("platform.gstin",                      "",
     "Platform GSTIN — must be set before issuing PLATFORM_TAX_INVOICE."),
    ("platform.home_state",                 "KA",
     "Two-letter state code (e.g. KA for Karnataka). Decides CGST+SGST vs IGST."),
    ("platform.address",                    "",
     "Registered office address shown on invoices."),

    # --- Platform fee GST (listing fee, maintenance fee) ---
    ("gst.platform_fee_rate",               0.18,
     "GST on platform fees. 18% by default."),
    ("gst.platform_fee_sac",                "998599",
     "SAC code for online platform support services."),
    ("gst.platform_fee_inclusive",          False,
     "If true, platform fee in plans is GST-inclusive; otherwise GST is added on top."),

    # --- Booking GST (student supply) ---
    ("gst.booking.default_rate",            0.18,
     "Default GST rate on student bookings (override per listing via gst_rate_override)."),
    ("gst.booking.pricing_is_inclusive",    True,
     "Cabin/seat/PG prices displayed in the app are GST-inclusive — reverse-calc."),
    ("gst.booking.default_sac",             "996311",
     "Default SAC for room/seat accommodation services."),
    ("gst.booking.exempt_threshold_monthly", 20000,
     "Per-person-per-month residential hostel/PG exemption ceiling (configurable)."),
    ("gst.booking.sec_9_5_eligible_categories",
     ["HOTEL_LIKE", "SHORT_STAY"],
     "GST categories where the platform is the deemed supplier under Sec 9(5) for unregistered owners."),

    # --- TCS (Sec 52 CGST) ---
    ("tcs.enabled",                         False,
     "Enable TCS deduction at settlement. Off until rates confirmed with CA."),
    ("tcs.rate_cgst",                       0.0025,
     "TCS CGST rate (0.25% as of 2024)."),
    ("tcs.rate_sgst",                       0.0025,
     "TCS SGST rate (0.25% as of 2024)."),
    ("tcs.rate_igst",                       0.005,
     "TCS IGST rate (0.5% as of 2024)."),
    ("tcs.applies_to_unregistered_owner",   False,
     "Sec 52 applies to registered suppliers only."),

    # --- TDS (Sec 194-O Income Tax) ---
    ("tds.section_194o_enabled",            False,
     "Enable 194-O TDS at settlement. Off until rates confirmed with CA."),
    ("tds.section_194o_rate",               0.001,
     "194-O TDS rate (0.1% from Oct 2024)."),
    ("tds.section_194o_threshold_yearly",   500000,
     "Per-owner per-FY threshold below which 194-O does not apply."),

    # --- Settlement timing ---
    ("settlement.hold_days",                3,
     "Hold student payment for N days before owner settlement (T+N)."),

    # --- Maintenance dunning matrix (days past due) ---
    ("maintenance.overdue.dim_days",        7,
     "After N overdue days, reduce listing visibility_score."),
    ("maintenance.overdue.suspend_days",    10,
     "After N overdue days, pause new bookings (existing bookings still resolve)."),
    ("maintenance.overdue.hide_days",       15,
     "After N overdue days, hide listing from search entirely."),
]


async def run() -> None:
    async with AsyncSessionLocal() as db:
        existing = {
            row.key for row in (await db.execute(select(TaxConfig))).scalars().all()
        }
        added = 0
        for key, value, desc in DEFAULTS:
            if key in existing:
                continue
            db.add(TaxConfig(
                key=key,
                value=json.dumps(value),
                description=desc,
            ))
            added += 1
        await db.commit()
        print(f"✅ tax_config seeded ({added} new, {len(existing)} pre-existing).")
        print("⚠️  Confirm final tax rates and applicability with your CA before go-live.")


if __name__ == "__main__":
    asyncio.run(run())
