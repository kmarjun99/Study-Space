/**
 * Super-admin attribution funnel (Phase 4D).
 *
 * Shows impression → click → conversion for each recommendation surface.
 * Split by whether conversion came from a tracked click vs. fallback last
 * impression — the latter is the "low confidence" tier.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, BarChart3, AlertCircle } from 'lucide-react';
import { Card, Button } from '../components/UI';
import {
    recommendationAttributionService, AttributionFunnel,
} from '../services/recommendationAttributionService';

const fmtPct = (x: number): string => `${(x * 100).toFixed(2)}%`;

export const SuperAdminAttribution: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<AttributionFunnel | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const f = await recommendationAttributionService.funnel();
            setData(f);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load funnel.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void refresh(); }, [refresh]);

    return (
        <div className="max-w-6xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <BarChart3 className="w-6 h-6 text-indigo-600" /> Recommendation attribution
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Funnel by surface. Conversions split by click-attributed vs. impression-attributed (fallback).
                    </p>
                </div>
                <Button variant="outline" size="sm" onClick={refresh}>
                    <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                </Button>
            </div>

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading || !data ? (
                <div className="text-gray-500">Loading…</div>
            ) : (
                <>
                    <div className="grid grid-cols-3 gap-3 mb-4">
                        <Card className="p-4">
                            <div className="text-xs text-gray-500 uppercase">Total impressions</div>
                            <div className="text-2xl font-bold text-gray-900">
                                {data.total_impressions.toLocaleString()}
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="text-xs text-gray-500 uppercase">Total clicks</div>
                            <div className="text-2xl font-bold text-gray-900">
                                {data.total_clicks.toLocaleString()}
                            </div>
                        </Card>
                        <Card className="p-4">
                            <div className="text-xs text-gray-500 uppercase">Total conversions</div>
                            <div className="text-2xl font-bold text-gray-900">
                                {data.total_conversions.toLocaleString()}
                            </div>
                        </Card>
                    </div>

                    <Card className="p-0 overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Surface</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Impressions</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Clicks</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">CTR</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Conversions</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">CVR</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Click / Impression</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {data.surfaces.map(s => (
                                    <tr key={s.surface} className="hover:bg-gray-50">
                                        <td className="px-4 py-3 text-sm font-medium text-gray-900">{s.surface}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{s.impressions.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{s.clicks.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-500">{fmtPct(s.ctr)}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{s.conversions.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-500">{fmtPct(s.cvr)}</td>
                                        <td className="px-4 py-3 text-xs text-right text-gray-500">
                                            <span className="text-green-600">{s.click_attributed_conversions}</span>
                                            {' / '}
                                            <span className="text-amber-600">{s.impression_attributed_conversions}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Card>

                    <Card className="mt-4 p-4 bg-amber-50 border-amber-200 text-amber-800 text-xs flex items-start gap-2">
                        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            <strong>Click-attributed</strong> conversions are tracked from the public click endpoint{' '}
                            (<code className="bg-amber-100 px-1 rounded">/recommendation-logs/:id/clicked</code>) — wire up{' '}
                            recommendation cards to hit it. <strong>Impression-attributed</strong> fallback fires when no{' '}
                            click was recorded but the user booked the listing within the attribution window —{' '}
                            lower confidence but still useful for surfaces without click instrumentation.
                        </div>
                    </Card>
                </>
            )}
        </div>
    );
};

export default SuperAdminAttribution;
