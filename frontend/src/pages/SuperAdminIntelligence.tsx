/**
 * Super-admin intelligence dashboard (Phase 2).
 *
 * Lists derived user profiles ranked by raw intent score. Intent level chips
 * + filter, plus a manual "Rebuild profiles" button that calls the
 * aggregation cron on demand.
 *
 * NOTE: this surface is intentionally minimal in Phase 2 — segment + campaign
 * surfaces will land in Phase 4. For now, super-admin can see WHO is high-
 * intent and contact them out-of-band.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import {
    ArrowLeft, Play, RefreshCw, Sparkles, AlertCircle, MapPin,
} from 'lucide-react';
import {
    intelligenceService, IntelligenceProfile, IntentLevel,
} from '../services/intelligenceService';

const LEVELS: (IntentLevel | 'ALL')[] = [
    'ALL', 'HOT_LEAD', 'HIGH_INTENT', 'MEDIUM_INTENT', 'LOW_INTENT',
];

const variantFor = (level: IntentLevel): 'success' | 'warning' | 'error' | 'info' => {
    switch (level) {
        case 'HOT_LEAD': return 'error';        // visible & urgent
        case 'HIGH_INTENT': return 'warning';
        case 'MEDIUM_INTENT': return 'info';
        default: return 'info';
    }
};

const pct = (n: number) => `${Math.round(n * 100)}%`;
const formatINR = (n: number | null) =>
    n === null ? '—' : n.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export const SuperAdminIntelligence: React.FC = () => {
    const navigate = useNavigate();
    const [filter, setFilter] = useState<(typeof LEVELS)[number]>('HOT_LEAD');
    const [rows, setRows] = useState<IntelligenceProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [rebuilding, setRebuilding] = useState(false);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await intelligenceService.listProfiles(
                filter === 'ALL' ? undefined : filter,
            );
            setRows(data);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load profiles.');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleRebuildAll = async () => {
        if (!confirm(
            'Rebuild intelligence profiles for users active in the last 24 hours?\n\n' +
            'Run only if intelligence.profile_aggregation_enabled is ON.',
        )) return;
        setRebuilding(true);
        try {
            const res = await intelligenceService.rebuildAll(1) as Record<string, unknown>;
            alert(JSON.stringify(res, null, 2));
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Rebuild failed.');
        } finally {
            setRebuilding(false);
        }
    };

    return (
        <div className="max-w-7xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <FeatureFlagToggle
                flagKey="intelligence.profile_aggregation_enabled"
                label="Intelligence profiles"
                description="Nightly rebuild of derived user-intent profiles"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Sparkles className="w-6 h-6 text-indigo-600" /> Intelligence
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Derived user profiles ranked by intent. Updated nightly.
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" onClick={handleRebuildAll} isLoading={rebuilding}>
                        <Play className="w-4 h-4 mr-1" /> Rebuild Now
                    </Button>
                </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
                {LEVELS.map(l => (
                    <button
                        key={l}
                        onClick={() => setFilter(l)}
                        className={`text-sm px-3 py-1 rounded-full border ${filter === l
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white text-gray-600 border-gray-300'}`}
                    >
                        {l}
                    </button>
                ))}
            </div>

            {error && (
                <Card className="p-4 mb-4 border-amber-200 bg-amber-50">
                    <div className="flex items-start gap-2 text-sm text-amber-800">
                        <AlertCircle className="w-4 h-4 mt-0.5" /> {error}
                    </div>
                </Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : rows.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    No profiles match this filter. Profiles are built nightly from
                    user behavior — if no user has opted in to personalization or
                    triggered events recently, this list will be empty.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-xs">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">User</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Intent</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Raw</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Preferred</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Price band</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Conv P</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Urgency</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Confidence</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Last active</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {rows.map(r => (
                                <tr key={r.user_id} className="hover:bg-gray-50">
                                    <td className="px-3 py-2 font-mono text-gray-700">{r.user_id.slice(0, 8)}</td>
                                    <td className="px-3 py-2">
                                        <Badge variant={variantFor(r.intent_level)}>{r.intent_level}</Badge>
                                    </td>
                                    <td className="px-3 py-2 text-right font-semibold text-gray-900">{r.raw_intent_score}</td>
                                    <td className="px-3 py-2 text-gray-700">
                                        {r.preferred_city && (
                                            <div className="flex items-center gap-1">
                                                <MapPin className="w-3 h-3" /> {r.preferred_city}
                                            </div>
                                        )}
                                        {r.preferred_locations.length > 0 && (
                                            <div className="text-gray-400">{r.preferred_locations.join(', ')}</div>
                                        )}
                                        {r.preferred_amenities.length > 0 && (
                                            <div className="text-gray-400">amenity: {r.preferred_amenities.join(', ')}</div>
                                        )}
                                    </td>
                                    <td className="px-3 py-2 text-right text-gray-700">
                                        {formatINR(r.preferred_price_min)} – {formatINR(r.preferred_price_max)}
                                    </td>
                                    <td className="px-3 py-2 text-right text-gray-700">{pct(r.conversion_probability_score)}</td>
                                    <td className="px-3 py-2 text-right text-gray-700">{pct(r.booking_urgency_score)}</td>
                                    <td className="px-3 py-2 text-right text-gray-700">{pct(r.profile_confidence_score)}</td>
                                    <td className="px-3 py-2 text-gray-500">
                                        {r.last_active_at ? new Date(r.last_active_at).toLocaleString('en-IN') : '—'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}
        </div>
    );
};

export default SuperAdminIntelligence;
