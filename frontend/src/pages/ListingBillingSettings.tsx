/**
 * Owner-facing page to configure accounting fields on a single listing:
 *   - GST category (HOTEL_LIKE / SHORT_STAY / HOSTEL_PG / READING_ROOM / OTHER)
 *   - Per-listing GST rate override
 *   - SAC code
 *   - Price display mode (GST_INCLUDED / GST_EXTRA)
 *   - Maintenance billing anchor day (1-28)
 *
 * Surfaces clearly that price_display_mode is INFORMATIONAL until the
 * platform flag `feature.per_listing_price_mode` is enabled by super-admin.
 * Pairs the form with a live PriceBreakdownPreview so the owner sees exactly
 * what the student will see at checkout.
 *
 * URL: /admin/listings/:listingType/:listingId/billing
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, AlertTriangle, Save, RotateCcw } from 'lucide-react';
import {
    listingBillingService,
    BillingConfig,
    BillingConfigUpdate,
    GstCategory,
    PriceDisplayMode,
    ListingTypeSlug,
} from '../services/listingBillingService';
import { PriceBreakdownPreview } from '../components/PriceBreakdownPreview';

const CATEGORIES: GstCategory[] = ['HOTEL_LIKE', 'SHORT_STAY', 'HOSTEL_PG', 'READING_ROOM', 'OTHER'];

export const ListingBillingSettings: React.FC = () => {
    const navigate = useNavigate();
    const params = useParams<{ listingType: string; listingId: string }>();
    const listingType = (params.listingType ?? 'reading-room') as ListingTypeSlug;
    const listingId = params.listingId ?? '';

    const [config, setConfig] = useState<BillingConfig | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Draft form state — null fields use the original value as default
    const [gstCategory, setGstCategory] = useState<GstCategory | ''>('');
    const [gstRateOverride, setGstRateOverride] = useState<string>('');
    const [gstSac, setGstSac] = useState<string>('');
    const [priceMode, setPriceMode] = useState<PriceDisplayMode | ''>('');
    const [anchorDay, setAnchorDay] = useState<string>('');
    const [previewPrice, setPreviewPrice] = useState<number>(2500);

    useEffect(() => {
        if (!listingId) return;
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const c = await listingBillingService.get(listingType, listingId);
                if (cancelled) return;
                setConfig(c);
                setGstCategory(c.gst_category ?? '');
                setGstRateOverride(c.gst_rate_override !== null ? String(c.gst_rate_override) : '');
                setGstSac(c.gst_sac ?? '');
                setPriceMode((c.price_display_mode as PriceDisplayMode) ?? '');
                setAnchorDay(c.billing_anchor_day !== null ? String(c.billing_anchor_day) : '');
            } catch (e: any) {
                if (!cancelled) {
                    setError(e?.response?.data?.detail || 'Could not load billing config.');
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [listingType, listingId]);

    const dirty = useMemo(() => {
        if (!config) return false;
        const rateOrig = config.gst_rate_override !== null ? String(config.gst_rate_override) : '';
        const anchorOrig = config.billing_anchor_day !== null ? String(config.billing_anchor_day) : '';
        return (
            (config.gst_category ?? '') !== gstCategory ||
            rateOrig !== gstRateOverride ||
            (config.gst_sac ?? '') !== gstSac ||
            ((config.price_display_mode as PriceDisplayMode) ?? '') !== priceMode ||
            anchorOrig !== anchorDay
        );
    }, [config, gstCategory, gstRateOverride, gstSac, priceMode, anchorDay]);

    const handleReset = () => {
        if (!config) return;
        setGstCategory(config.gst_category ?? '');
        setGstRateOverride(config.gst_rate_override !== null ? String(config.gst_rate_override) : '');
        setGstSac(config.gst_sac ?? '');
        setPriceMode((config.price_display_mode as PriceDisplayMode) ?? '');
        setAnchorDay(config.billing_anchor_day !== null ? String(config.billing_anchor_day) : '');
    };

    const handleSave = async () => {
        if (!config) return;
        const body: BillingConfigUpdate = {};
        if (gstCategory) body.gst_category = gstCategory as GstCategory;
        else body.clear_gst_category = !!config.gst_category;

        if (gstRateOverride.trim()) {
            const v = parseFloat(gstRateOverride);
            if (Number.isNaN(v) || v < 0 || v > 1) {
                alert('GST rate must be a number between 0 and 1 (e.g. 0.18 for 18%).');
                return;
            }
            body.gst_rate_override = v;
        } else {
            body.clear_gst_rate_override = config.gst_rate_override !== null;
        }

        body.gst_sac = gstSac.trim() || null;

        if (priceMode) body.price_display_mode = priceMode as PriceDisplayMode;
        else body.clear_price_display_mode = !!config.price_display_mode;

        if (anchorDay.trim()) {
            const v = parseInt(anchorDay, 10);
            if (Number.isNaN(v) || v < 1 || v > 28) {
                alert('Billing anchor day must be between 1 and 28.');
                return;
            }
            body.billing_anchor_day = v;
        }

        setSaving(true);
        try {
            const next = await listingBillingService.update(listingType, listingId, body);
            setConfig(next);
            // Re-sync draft to canonical
            setGstCategory(next.gst_category ?? '');
            setGstRateOverride(next.gst_rate_override !== null ? String(next.gst_rate_override) : '');
            setGstSac(next.gst_sac ?? '');
            setPriceMode((next.price_display_mode as PriceDisplayMode) ?? '');
            setAnchorDay(next.billing_anchor_day !== null ? String(next.billing_anchor_day) : '');
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not save billing config.');
        } finally {
            setSaving(false);
        }
    };

    if (!listingId) {
        return <div className="p-6 text-gray-500">Missing listing id.</div>;
    }

    return (
        <div className="max-w-4xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <h1 className="text-2xl font-bold text-gray-900 mb-1">Listing billing &amp; GST</h1>
            <p className="text-gray-500 text-sm mb-6">
                Per-listing accounting settings. These shape how invoices are issued and how
                the booking price is broken down at checkout.
            </p>

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : !config ? (
                <Card className="p-6 text-gray-400">No billing config found.</Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Card className="p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4">Settings</h2>

                        <label className="block text-sm font-medium text-gray-700 mb-1">GST category</label>
                        <select
                            value={gstCategory}
                            onChange={e => setGstCategory(e.target.value as GstCategory | '')}
                            className="w-full mb-3 border rounded px-3 py-2 text-sm"
                        >
                            <option value="">— Use platform default —</option>
                            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>

                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            GST rate override (0–1, e.g. <code>0.18</code> for 18%)
                        </label>
                        <input
                            type="text"
                            value={gstRateOverride}
                            onChange={e => setGstRateOverride(e.target.value)}
                            placeholder="leave blank to use config default"
                            className="w-full mb-3 border rounded px-3 py-2 text-sm"
                        />

                        <label className="block text-sm font-medium text-gray-700 mb-1">SAC code</label>
                        <input
                            type="text"
                            value={gstSac}
                            onChange={e => setGstSac(e.target.value)}
                            placeholder="e.g. 996311"
                            className="w-full mb-3 border rounded px-3 py-2 text-sm"
                        />

                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Price display mode
                        </label>
                        <select
                            value={priceMode}
                            onChange={e => setPriceMode(e.target.value as PriceDisplayMode | '')}
                            className="w-full mb-1 border rounded px-3 py-2 text-sm"
                        >
                            <option value="">— Use platform default —</option>
                            <option value="GST_INCLUDED">GST_INCLUDED — student sees final price</option>
                            <option value="GST_EXTRA">GST_EXTRA — show base + GST separately</option>
                        </select>
                        <p className="text-xs text-amber-700 mb-3 flex items-start gap-1">
                            <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                            <span>
                                Currently informational. Live booking math will switch only after
                                super-admin enables <code>feature.per_listing_price_mode</code>.
                            </span>
                        </p>

                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Maintenance billing anchor day (1–28)
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={28}
                            value={anchorDay}
                            onChange={e => setAnchorDay(e.target.value)}
                            placeholder="1"
                            className="w-full mb-4 border rounded px-3 py-2 text-sm"
                        />

                        <div className="flex items-center justify-between mt-4">
                            <div className="text-xs text-gray-400">
                                Maintenance status:&nbsp;
                                <Badge variant={config.maintenance_status === 'CURRENT' ? 'success' : 'warning'}>
                                    {config.maintenance_status ?? '—'}
                                </Badge>
                            </div>
                            <div className="flex gap-2">
                                <Button variant="outline" size="sm" onClick={handleReset} disabled={!dirty}>
                                    <RotateCcw className="w-3 h-3 mr-1" /> Reset
                                </Button>
                                <Button size="sm" onClick={handleSave} isLoading={saving} disabled={!dirty}>
                                    <Save className="w-3 h-3 mr-1" /> Save
                                </Button>
                            </div>
                        </div>
                    </Card>

                    <div className="space-y-4">
                        <Card className="p-6">
                            <h2 className="text-lg font-semibold text-gray-900 mb-3">Live preview</h2>
                            <p className="text-xs text-gray-500 mb-3">
                                Shows the exact breakdown a student would see at checkout, computed by the
                                same backend engine.
                            </p>
                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                Sample displayed price
                            </label>
                            <input
                                type="number"
                                value={previewPrice}
                                onChange={e => setPreviewPrice(parseFloat(e.target.value) || 0)}
                                className="w-full mb-3 border rounded px-3 py-2 text-sm"
                            />
                            <PriceBreakdownPreview
                                listingType={listingType}
                                listingId={listingId}
                                displayedPrice={previewPrice}
                            />
                        </Card>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ListingBillingSettings;
