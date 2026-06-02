/**
 * Super-admin weekly cohort retention (Phase 6).
 *
 * Renders a triangular retention matrix: cohort week × weeks-since-cohort.
 * Color-codes retention bands so retention shape is visible at a glance.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Calendar } from 'lucide-react';
import { Card, Button } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import { experimentService, CohortReport } from '../services/experimentService';

const KINDS: Array<'search_first' | 'booking_first'> = [
    'search_first', 'booking_first',
];

const fmtPct = (x: number): string => `${(x * 100).toFixed(0)}%`;

const bgFor = (r: number): string => {
    if (r >= 0.5) return 'bg-indigo-600 text-white';
    if (r >= 0.3) return 'bg-indigo-400 text-white';
    if (r >= 0.15) return 'bg-indigo-200 text-gray-900';
    if (r > 0) return 'bg-indigo-50 text-gray-700';
    return 'bg-gray-50 text-gray-400';
};

export const SuperAdminCohorts: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<CohortReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [kind, setKind] = useState<'search_first' | 'booking_first'>('search_first');

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            setData(await experimentService.cohorts(kind, 8, 8));
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load cohorts.');
        } finally {
            setLoading(false);
        }
    }, [kind]);

    useEffect(() => { void refresh(); }, [refresh]);

    return (
        <div className="max-w-6xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <FeatureFlagToggle
                flagKey="insights.enabled"
                label="Cohort analytics"
                description="Retention cohorts — shares the insights.enabled flag"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <Calendar className="w-6 h-6 text-indigo-600" /> Weekly cohorts
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Retention by cohort week. W0 = users joined that week, Wk = % still active k weeks later.
                    </p>
                </div>
                <div className="flex gap-2">
                    <div className="flex bg-gray-100 rounded p-0.5">
                        {KINDS.map(k => (
                            <button
                                key={k}
                                onClick={() => setKind(k)}
                                className={`px-3 py-1 text-xs rounded ${kind === k
                                    ? 'bg-white text-indigo-700 shadow-sm font-medium'
                                    : 'text-gray-600 hover:text-gray-900'}`}
                            >
                                {k.replace('_', ' ')}
                            </button>
                        ))}
                    </div>
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                </div>
            </div>

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading || !data ? (
                <div className="text-gray-500">Loading…</div>
            ) : !data.enabled ? (
                <Card className="p-8 text-center text-gray-500">
                    Cohorts are not enabled. Set <code className="bg-gray-100 px-1 rounded">insights.enabled</code>.
                </Card>
            ) : (data.rows ?? []).length === 0 ? (
                <Card className="p-8 text-center text-gray-400">
                    Not enough activity to form a cohort. Once user_events accumulate over the window, cohorts will appear here.
                </Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full text-xs">
                        <thead className="bg-gray-50 text-gray-500 uppercase">
                            <tr>
                                <th className="px-3 py-2 text-left">Cohort week</th>
                                <th className="px-3 py-2 text-right">Size</th>
                                {Array.from({ length: data.weeks ?? 8 }).map((_, i) => (
                                    <th key={i} className="px-3 py-2 text-center">W{i}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.rows!.map(r => (
                                <tr key={r.cohort_week} className="border-t">
                                    <td className="px-3 py-2 text-gray-900 font-mono">{r.cohort_week}</td>
                                    <td className="px-3 py-2 text-right text-gray-700">{r.size.toLocaleString()}</td>
                                    {Array.from({ length: data.weeks ?? 8 }).map((_, i) => {
                                        const val = r.retention[i];
                                        if (val === undefined) {
                                            return <td key={i} className="px-3 py-2 text-center text-gray-300">—</td>;
                                        }
                                        return (
                                            <td key={i} className="px-1 py-1 text-center">
                                                <div className={`rounded px-1 py-1 ${bgFor(val)}`}>
                                                    {fmtPct(val)}
                                                </div>
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}
        </div>
    );
};

export default SuperAdminCohorts;
