/**
 * Super-admin tax & accounting configuration.
 *
 * Each key in tax_config is editable in-place. Values are stored as JSON so
 * the editor accepts free JSON text — strings, numbers, booleans, arrays.
 * Every save audits via the backend; this page just renders + persists.
 *
 * Now also supports CREATING keys from the UI (Add Key form + Quick Add
 * panel for common defaults), so operators don't need the backend seed
 * script to have run before they can configure anything. Earlier version
 * only edited pre-existing rows — if `/api/admin/tax-config` returned [],
 * the page rendered nothing actionable and operators were stuck.
 *
 * Warning banner at the top is intentional: rates are not law-default; the
 * platform's CA must confirm them before go-live.
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, AlertTriangle, Save, RotateCcw, Plus, Sparkles, Power, CheckCircle2 } from 'lucide-react';
import { taxConfigService, TaxConfigItem } from '../services/taxConfigService';

type Draft = Record<string, { raw: string; dirty: boolean; error: string | null }>;

// Quick-Add preset categories. Every entry mirrors a row in
// backend/scripts/seed_tax_config.py — these are the operationally-
// important keys an admin will need before going live. Categories let
// the UI group them so the operator sees a curated list instead of a
// flat wall of 30+ buttons.
//
// Adding a new key here lets the operator one-click create it with a
// safe default. They can edit afterward via the inline editor on the
// same page. Defaults are intentionally CONSERVATIVE (booleans default
// false / accounting & insights start gated) so creating a key never
// flips behaviour on by itself — the operator has to explicitly edit
// the value after creation.
type Preset = { key: string; value: unknown; description: string };
const QUICK_ADD_CATEGORIES: { title: string; intro: string; items: Preset[] }[] = [
    {
        title: 'Accounting & GST',
        intro: 'Core GST + ledger. Flip accounting.enabled to true to start freezing GST splits on every new paid booking.',
        items: [
            {
                key: 'accounting.enabled',
                value: false,
                description: 'Master switch — when true, the accounting layer freezes a GST split on every paid booking.',
            },
            {
                key: 'gst.booking.default_rate',
                value: 0.18,
                description: 'Default GST rate on bookings when the listing has no rate override (0.18 = 18%).',
            },
            {
                key: 'gst.booking.pricing_is_inclusive',
                value: true,
                description: 'When true, displayed booking prices already include GST; engine reverse-calculates the split.',
            },
            {
                key: 'gst.platform_fee_rate',
                value: 0.18,
                description: 'GST rate applied on platform listing-fee / maintenance-fee invoices (typically 18%).',
            },
            {
                key: 'feature.gst_invoices',
                value: false,
                description: 'Render new GST-aware invoice formats (PLATFORM_TAX_INVOICE etc.) when true.',
            },
            {
                key: 'feature.recurring_maintenance',
                value: false,
                description: 'Enable monthly maintenance billing per listing when true.',
            },
        ],
    },
    {
        title: 'Platform identity (required for GST invoices)',
        intro: 'These appear on every tax invoice the platform issues. Confirm with your CA before flipping feature.gst_invoices on.',
        items: [
            {
                key: 'platform.legal_name',
                value: 'mySpace Technology Pvt Ltd',
                description: 'Registered legal name shown on tax invoices.',
            },
            {
                key: 'platform.gstin',
                value: '',
                description: 'Platform GSTIN. Required for GST invoices — get from your tax advisor.',
            },
            {
                key: 'platform.home_state',
                value: 'KA',
                description: '2-letter state code for platform registration (KA, MH, etc.). Decides CGST/SGST vs IGST.',
            },
            {
                key: 'platform.address',
                value: '',
                description: 'Registered office address shown on tax invoices.',
            },
        ],
    },
    {
        title: 'Settlements & maintenance dunning',
        intro: 'Controls when owners get paid out and how unpaid maintenance charges escalate.',
        items: [
            {
                key: 'settlement.hold_days',
                value: 3,
                description: 'T+N hold window — bookings become settlement-eligible this many days after paid_at.',
            },
            {
                key: 'maintenance.overdue.dim_days',
                value: 7,
                description: 'Days after a maintenance charge becomes overdue before halving the listing\'s visibility score.',
            },
            {
                key: 'maintenance.overdue.suspend_days',
                value: 10,
                description: 'Days overdue before the listing is suspended (no new bookings allowed).',
            },
            {
                key: 'maintenance.overdue.hide_days',
                value: 15,
                description: 'Days overdue before the listing is hidden from search entirely.',
            },
        ],
    },
    {
        title: 'TCS & TDS (Sec 9(5) / 194-O compliance)',
        intro: 'Turn on ONLY after your CA confirms applicability + turnover thresholds. Disabled by default.',
        items: [
            {
                key: 'tcs.enabled',
                value: false,
                description: 'Master switch for Tax Collected at Source on bookings. Flip on once your CA signs off.',
            },
            {
                key: 'tcs.rate_cgst',
                value: 0.0025,
                description: 'TCS rate on the CGST portion (default 0.25%).',
            },
            {
                key: 'tcs.rate_sgst',
                value: 0.0025,
                description: 'TCS rate on the SGST portion (default 0.25%).',
            },
            {
                key: 'tcs.rate_igst',
                value: 0.005,
                description: 'TCS rate on IGST for inter-state bookings (default 0.5%).',
            },
            {
                key: 'tds.section_194o_enabled',
                value: false,
                description: 'Master switch for Section 194-O TDS on owner payouts.',
            },
            {
                key: 'tds.section_194o_rate',
                value: 0.001,
                description: 'Section 194-O TDS rate (default 0.1%).',
            },
            {
                key: 'tds.section_194o_threshold_yearly',
                value: 500000,
                description: 'Per-owner yearly turnover threshold below which TDS does not apply (₹).',
            },
        ],
    },
    {
        title: 'Intelligence & insights',
        intro: 'Insights dashboards (owner + super-admin) and the underlying intent/profile scoring. The "Insights are not enabled" message you see on those pages is gated on insights.enabled — flip it true here.',
        items: [
            {
                key: 'insights.enabled',
                value: false,
                description: 'Powers the Owner Insights + Super-Admin Insights / Cohorts dashboards. The "Insights are not enabled" placeholder disappears once true.',
            },
            {
                key: 'insights.k_anonymity_floor',
                value: 5,
                description: 'Minimum cohort size before insights are shown (privacy floor — smaller cohorts are hidden).',
            },
            {
                key: 'events.enabled',
                value: false,
                description: 'Records user events (searches, views, bookings) into the events firehose. Required for intelligence + recommendations.',
            },
            {
                key: 'events.anonymous_allowed',
                value: true,
                description: 'When true, anonymous (logged-out) events are stored. Switch off for strict consent regimes.',
            },
            {
                key: 'intelligence.profile_aggregation_enabled',
                value: false,
                description: 'Aggregates per-user intent profiles from event history. Required for personalized recommendations.',
            },
            {
                key: 'consent.required_for_analytics',
                value: false,
                description: 'When true, analytics events are only recorded for users who opted in via privacy settings.',
            },
        ],
    },
    {
        title: 'Recommendations & attribution',
        intro: 'Rule-based recommendations on listing pages + tracking which recommendation led to each booking.',
        items: [
            {
                key: 'recommendations.enabled',
                value: false,
                description: 'When true, listing detail pages show FOR_YOU / SIMILAR recommendation rails.',
            },
            {
                key: 'recommendations.log_impressions',
                value: false,
                description: 'Logs every recommendation impression to recommendation_log for attribution analysis.',
            },
            {
                key: 'recommendations.attribution_enabled',
                value: false,
                description: 'On payment, stamps the booking with the recommendation_log row the user clicked through.',
            },
            {
                key: 'recommendations.attribution_window_days',
                value: 7,
                description: 'Maximum days between a recommendation click and a booking for attribution to count.',
            },
        ],
    },
    {
        title: 'Segments, campaigns & notification automation',
        intro: 'Rule-based audience segments + campaign delivery + push/email automation. Disable individually if you don\'t want owner notifications.',
        items: [
            {
                key: 'segments.enabled',
                value: false,
                description: 'When true, nightly cron computes audience segments from event history.',
            },
            {
                key: 'campaigns.enabled',
                value: false,
                description: 'When true, drafted campaigns can be dispatched to their target segments.',
            },
            {
                key: 'campaigns.attribution_window_days',
                value: 7,
                description: 'Days within which a campaign click → booking counts as attributed to the campaign.',
            },
            {
                key: 'notification_automation.enabled',
                value: false,
                description: 'Master switch for rule-based push / email notifications.',
            },
            {
                key: 'experiments.enabled',
                value: false,
                description: 'A/B testing infrastructure — turn on only when you have an experiment defined.',
            },
        ],
    },
];

const toRaw = (value: unknown): string => {
    if (typeof value === 'string') return JSON.stringify(value);
    try {
        return JSON.stringify(value, null, 0);
    } catch {
        return String(value);
    }
};

export const SuperAdminTaxConfig: React.FC = () => {
    const navigate = useNavigate();
    const [items, setItems] = useState<TaxConfigItem[]>([]);
    const [drafts, setDrafts] = useState<Draft>({});
    const [loading, setLoading] = useState(false);
    const [savingKey, setSavingKey] = useState<string | null>(null);
    const [topError, setTopError] = useState<string | null>(null);

    // Add Key form state
    const [newKey, setNewKey] = useState('');
    const [newValue, setNewValue] = useState('');
    const [newDesc, setNewDesc] = useState('');
    const [adding, setAdding] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);

    // One-click "Enable Accounting" state — bulk-seeds every missing default
    // AND flips accounting.enabled=true in a single confirm.
    const [bulkBusy, setBulkBusy] = useState(false);
    const [bulkError, setBulkError] = useState<string | null>(null);
    const [bulkConfirm, setBulkConfirm] = useState(false);

    const refresh = async () => {
        setLoading(true);
        setTopError(null);
        try {
            const rows = await taxConfigService.list();
            setItems(rows);
            const d: Draft = {};
            for (const r of rows) {
                d[r.key] = { raw: toRaw(r.value), dirty: false, error: null };
            }
            setDrafts(d);
        } catch (e: any) {
            setTopError(e?.response?.data?.detail || 'Failed to load tax config.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { void refresh(); }, []);

    const setRaw = (key: string, raw: string) => {
        let error: string | null = null;
        try { JSON.parse(raw); } catch (e: any) { error = e.message; }
        setDrafts(prev => ({ ...prev, [key]: { raw, dirty: true, error } }));
    };

    const reset = (key: string) => {
        const item = items.find(i => i.key === key);
        if (!item) return;
        setDrafts(prev => ({ ...prev, [key]: { raw: toRaw(item.value), dirty: false, error: null } }));
    };

    const save = async (key: string) => {
        const draft = drafts[key];
        if (!draft || draft.error) return;
        setSavingKey(key);
        try {
            const parsed = JSON.parse(draft.raw);
            const updated = await taxConfigService.upsert(key, parsed);
            setItems(prev => prev.map(i => (i.key === key ? updated : i)));
            setDrafts(prev => ({ ...prev, [key]: { raw: toRaw(updated.value), dirty: false, error: null } }));
        } catch (e: any) {
            setDrafts(prev => ({
                ...prev,
                [key]: { ...prev[key], error: e?.response?.data?.detail || 'Save failed.' },
            }));
        } finally {
            setSavingKey(null);
        }
    };

    // Create a brand-new key. The backend's PUT endpoint is an upsert so the
    // same call doubles as "set initial value for a key that doesn't exist yet".
    const addKey = async (key: string, rawValue: string, description: string) => {
        setAddError(null);
        const trimmedKey = key.trim();
        if (!trimmedKey) {
            setAddError('Key is required.');
            return;
        }
        let parsed: unknown;
        try {
            parsed = JSON.parse(rawValue);
        } catch (e: any) {
            setAddError(`Value must be valid JSON. ${e.message}`);
            return;
        }
        setAdding(true);
        try {
            const created = await taxConfigService.upsert(trimmedKey, parsed, description || undefined);
            setItems(prev => {
                // De-dupe by key in case it already existed (upsert replaces).
                const without = prev.filter(i => i.key !== created.key);
                return [...without, created];
            });
            setDrafts(prev => ({
                ...prev,
                [created.key]: { raw: toRaw(created.value), dirty: false, error: null },
            }));
            // Clear manual-form fields on success so the operator can add another.
            // Quick-add presets call addKey() directly so this is harmless for them.
            setNewKey('');
            setNewValue('');
            setNewDesc('');
        } catch (e: any) {
            setAddError(e?.response?.data?.detail || 'Could not create key.');
        } finally {
            setAdding(false);
        }
    };

    // One-click bootstrap: create every missing Quick Add preset AND set
    // accounting.enabled=true. Idempotent — re-running after partial success
    // just upserts the rest. Used by operators who don't want to remember
    // which six keys to add; instead they confirm once and the system is
    // configured + live.
    const bulkEnable = async () => {
        setBulkBusy(true);
        setBulkError(null);
        try {
            // Bulk-enable seeds the "Accounting & GST" + "Platform identity"
            // categories — the minimum needed to flip accounting.enabled
            // to true and start writing GST splits. Everything else
            // (insights, recommendations, campaigns, TCS/TDS) stays opt-in
            // via the individual Quick Add buttons because they have
            // operational implications that need explicit consent.
            const BULK_CATEGORIES = new Set([
                'Accounting & GST',
                'Platform identity (required for GST invoices)',
                'Settlements & maintenance dunning',
            ]);
            const presetsToSeed = QUICK_ADD_CATEGORIES
                .filter(cat => BULK_CATEGORIES.has(cat.title))
                .flatMap(cat => cat.items);
            // Iterate sequentially so the audit log is readable and we
            // don't hammer the backend with parallel writes.
            for (const preset of presetsToSeed) {
                if (existingKeys.has(preset.key)) continue;
                await taxConfigService.upsert(preset.key, preset.value, preset.description);
            }
            // Master switch flip happens last so any seed failure above
            // surfaces before the system goes live.
            await taxConfigService.upsert(
                'accounting.enabled',
                true,
                'Master kill switch — when true, the new accounting layer freezes GST split on every paid booking.',
            );
            await refresh();
            setBulkConfirm(false);
        } catch (e: any) {
            setBulkError(e?.response?.data?.detail || 'Bulk enable failed. Some keys may have been created — refresh to see.');
        } finally {
            setBulkBusy(false);
        }
    };

    // Group by key prefix so related settings sit together
    const grouped = items.reduce<Record<string, TaxConfigItem[]>>((acc, item) => {
        const group = item.key.split('.')[0] || 'misc';
        (acc[group] ||= []).push(item);
        return acc;
    }, {});

    const existingKeys = new Set(items.map(i => i.key));
    // Filter each category to only the presets the user hasn't created yet.
    // Categories whose presets are all present collapse to empty arrays —
    // the render below skips empty categories.
    const missingByCategory = QUICK_ADD_CATEGORIES.map(cat => ({
        ...cat,
        items: cat.items.filter(p => !existingKeys.has(p.key)),
    })).filter(cat => cat.items.length > 0);
    const missingPresetCount = missingByCategory.reduce((n, c) => n + c.items.length, 0);

    // Compute the live-status badge from the accounting.enabled row (if any).
    const accountingRow = items.find(i => i.key === 'accounting.enabled');
    const accountingOn = accountingRow?.value === true;
    const accountingMissing = accountingRow === undefined;

    return (
        <div className="max-w-5xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Tax &amp; Accounting Config</h1>
            <p className="text-gray-500 mb-6">
                Configurable GST / TCS / TDS rates, platform identity, and recurring-billing
                policy. Values are stored as JSON.
            </p>

            <Card className="p-4 mb-6 border-amber-200 bg-amber-50">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div className="text-sm text-amber-900">
                        <strong>Confirm final tax rates and applicability with your CA before go-live.</strong>
                        {' '}Defaults reflect current rules but Indian tax law evolves — this page is the
                        one place to keep mySpace compliant without a redeploy.
                    </div>
                </div>
            </Card>

            {topError && (
                <Card className="p-4 mb-6 border-red-200 bg-red-50 text-red-700 text-sm">{topError}</Card>
            )}

            {/* Live-status banner + one-click enable. The fastest path to a
                working system: confirm once, and every missing default key
                gets created + accounting.enabled flips to true. */}
            {!loading && (
                <Card className={`p-5 mb-6 ${accountingOn
                    ? 'border-emerald-200 bg-emerald-50'
                    : 'border-indigo-200 bg-indigo-50'}`}>
                    {accountingOn ? (
                        <div className="flex items-start gap-3">
                            <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5" />
                            <div className="text-sm text-emerald-900">
                                <strong>Accounting is LIVE.</strong> Every new paid booking from
                                now on freezes a GST split into the booking row. Old bookings
                                stay legacy (Tax ₹0). To turn this off, edit the
                                {' '}<code className="font-mono">accounting.enabled</code> row
                                below and set it to <code className="font-mono">false</code>.
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className="flex items-start gap-3 mb-3">
                                <Power className="w-5 h-5 text-indigo-600 mt-0.5" />
                                <div className="text-sm text-indigo-900">
                                    <strong>
                                        {accountingMissing
                                            ? 'Accounting is not configured yet.'
                                            : 'Accounting is OFF.'}
                                    </strong>{' '}
                                    Click below to create every required default key
                                    (GST rates, inclusive-pricing flag, platform fee rate,
                                    invoice format flag) AND flip accounting.enabled to
                                    true in one step. Old bookings are NOT touched — only
                                    new paid bookings get the GST split.
                                </div>
                            </div>
                            {bulkError && (
                                <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2 mb-3">
                                    {bulkError}
                                </div>
                            )}
                            {!bulkConfirm ? (
                                <Button
                                    onClick={() => { setBulkConfirm(true); setBulkError(null); }}
                                    disabled={bulkBusy}
                                >
                                    <Power className="w-4 h-4 mr-1" /> Enable Accounting (one-click)
                                </Button>
                            ) : (
                                <div className="bg-white border border-indigo-300 rounded-lg p-3">
                                    <div className="text-sm text-gray-700 mb-3">
                                        This will create the Accounting + Platform Identity
                                        + Settlement defaults (if missing) and set{' '}
                                        <code className="font-mono">accounting.enabled = true</code>.
                                        Other categories (insights, recommendations, TCS/TDS)
                                        stay opt-in via the Quick Add panels below — flip
                                        them on only when your CA / product team has
                                        explicitly approved. Confirm only if you've reviewed
                                        the defaults with your CA.
                                    </div>
                                    <div className="flex gap-2">
                                        <Button onClick={bulkEnable} isLoading={bulkBusy}>
                                            Yes, enable now
                                        </Button>
                                        <Button
                                            variant="outline"
                                            onClick={() => setBulkConfirm(false)}
                                            disabled={bulkBusy}
                                        >
                                            Cancel
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </Card>
            )}

            {/* Empty-state hint — visible only when there are zero keys. */}
            {!loading && items.length === 0 && (
                <Card className="p-6 mb-6 border-indigo-200 bg-indigo-50">
                    <div className="text-sm text-indigo-900">
                        <strong>No tax_config rows yet.</strong> Use the green button above
                        to enable accounting in one click, or use the Quick Add / Add Key
                        controls below for granular control.
                    </div>
                </Card>
            )}

            {/* Quick Add — grouped by category so the operator sees a curated
                list per concern (Accounting / Platform identity / Settlements /
                TCS+TDS / Intelligence / Recommendations / Segments+Campaigns)
                instead of a flat wall of 30+ buttons. Each category renders
                only the presets that aren't already configured. */}
            {missingPresetCount > 0 && (
                <>
                    <div className="mb-2 flex items-center gap-2 text-xs text-gray-500">
                        <Sparkles className="w-4 h-4 text-indigo-600" />
                        <span>
                            <strong>Quick Add</strong> — {missingPresetCount} default
                            key{missingPresetCount === 1 ? '' : 's'} available across
                            {' '}{missingByCategory.length} categor{missingByCategory.length === 1 ? 'y' : 'ies'}.
                            One click to create with a safe default; edit after.
                        </span>
                    </div>
                    {missingByCategory.map(cat => (
                        <Card key={cat.title} className="p-6 mb-4">
                            <h2 className="text-base font-bold text-gray-900 mb-1">
                                {cat.title}
                            </h2>
                            <p className="text-xs text-gray-500 mb-4">{cat.intro}</p>
                            <div className="space-y-2">
                                {cat.items.map(p => (
                                    <div key={p.key} className="flex items-start justify-between gap-4 border rounded-lg p-3">
                                        <div className="flex-1 min-w-0">
                                            <div className="font-mono text-sm font-semibold text-gray-900">{p.key}</div>
                                            <div className="text-xs text-gray-500 mt-0.5">{p.description}</div>
                                            <div className="text-xs text-gray-400 mt-1">
                                                suggested value: <code className="font-mono bg-gray-100 px-1 rounded">{JSON.stringify(p.value)}</code>
                                            </div>
                                        </div>
                                        <Button
                                            size="sm"
                                            onClick={() => addKey(p.key, JSON.stringify(p.value), p.description)}
                                            isLoading={adding}
                                        >
                                            <Plus className="w-3 h-3 mr-1" /> Add
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </Card>
                    ))}
                </>
            )}

            {/* Manual Add Key — arbitrary key + JSON value. */}
            <Card className="p-6 mb-6">
                <h2 className="text-lg font-bold text-gray-900 mb-1 flex items-center gap-2">
                    <Plus className="w-5 h-5 text-indigo-600" /> Add Key
                </h2>
                <p className="text-xs text-gray-500 mb-4">
                    Create a new config row. Value must be valid JSON
                    (<code className="font-mono">true</code>, <code className="font-mono">0.18</code>,
                    {' '}<code className="font-mono">"text"</code>, <code className="font-mono">{`{...}`}</code>).
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                    <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Key</label>
                        <input
                            value={newKey}
                            onChange={e => setNewKey(e.target.value)}
                            placeholder="e.g. accounting.enabled"
                            className="w-full font-mono text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Value (JSON)</label>
                        <input
                            value={newValue}
                            onChange={e => setNewValue(e.target.value)}
                            placeholder='e.g. true   or   0.18   or   "in"'
                            className="w-full font-mono text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                </div>
                <div className="mb-3">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Description (optional)</label>
                    <input
                        value={newDesc}
                        onChange={e => setNewDesc(e.target.value)}
                        placeholder="Short note shown next to the key"
                        className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                </div>
                {addError && (
                    <div className="text-xs text-red-600 mb-3">{addError}</div>
                )}
                <Button
                    size="sm"
                    onClick={() => addKey(newKey, newValue, newDesc)}
                    isLoading={adding}
                    disabled={!newKey.trim() || !newValue.trim()}
                >
                    <Plus className="w-3 h-3 mr-1" /> Create
                </Button>
            </Card>

            {loading && <div className="text-gray-500">Loading…</div>}

            {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([group, rows]) => (
                <Card key={group} className="p-6 mb-4">
                    <h2 className="text-lg font-bold text-gray-900 mb-4 capitalize">{group}</h2>
                    <div className="space-y-4">
                        {rows.sort((a, b) => a.key.localeCompare(b.key)).map(item => {
                            const draft = drafts[item.key];
                            if (!draft) return null;
                            return (
                                <div key={item.key} className="border rounded-lg p-4">
                                    <div className="flex items-start justify-between gap-4 mb-2">
                                        <div>
                                            <div className="font-mono text-sm font-semibold text-gray-900">{item.key}</div>
                                            {item.description && (
                                                <div className="text-xs text-gray-500 mt-1">{item.description}</div>
                                            )}
                                        </div>
                                        {draft.dirty && <Badge variant="warning">unsaved</Badge>}
                                    </div>
                                    <textarea
                                        value={draft.raw}
                                        onChange={e => setRaw(item.key, e.target.value)}
                                        rows={Math.min(6, Math.max(1, (draft.raw.match(/\n/g) || []).length + 1))}
                                        className="w-full font-mono text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                    />
                                    {draft.error && (
                                        <div className="text-xs text-red-600 mt-1">{draft.error}</div>
                                    )}
                                    <div className="flex items-center justify-between mt-3">
                                        <div className="text-xs text-gray-400">
                                            {item.updated_at ? `Updated ${new Date(item.updated_at).toLocaleString()}` : 'Never updated'}
                                        </div>
                                        <div className="flex gap-2">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => reset(item.key)}
                                                disabled={!draft.dirty}
                                            >
                                                <RotateCcw className="w-3 h-3 mr-1" /> Reset
                                            </Button>
                                            <Button
                                                size="sm"
                                                onClick={() => save(item.key)}
                                                isLoading={savingKey === item.key}
                                                disabled={!draft.dirty || !!draft.error}
                                            >
                                                <Save className="w-3 h-3 mr-1" /> Save
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </Card>
            ))}
        </div>
    );
};

export default SuperAdminTaxConfig;
