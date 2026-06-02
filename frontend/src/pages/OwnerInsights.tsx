/**
 * Owner insights page (Phase 5). Aggregated counts only. Conversion rates
 * are suppressed below the k-anonymity floor to protect individual users.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, RefreshCw, BarChart3, Eye, Heart, MessageSquare,
    Calendar, ShieldCheck, AlertCircle,
} from 'lucide-react';
import { Card, Button } from '../components/UI';
import { insightsService, ListingInsight, OwnerInsights as OI } from '../services/insightsService';

const WINDOWS = [7, 30, 90];

const fmtPct = (x: number | null): string => x === null ? '—' : `${(x * 100).toFixed(2)}%`;

export const OwnerInsights: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<OI | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [windowDays, setWindowDays] = useState(30);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const d = await insightsService.ownerInsights(windowDays);
            setData(d);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load insights.');
        } finally {
            setLoading(false);
        }
    }, [windowDays]);

    useEffect(() => { void refresh(); }, [refresh]);

    return (
        <div className="max-w-6xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <BarChart3 className="w-6 h-6 text-indigo-600" /> Listing insights
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Aggregated performance for your listings.
                    </p>
                </div>
                <div className="flex gap-2">
                    <div className="flex bg-gray-100 rounded p-0.5">
                        {WINDOWS.map(w => (
                            <button
                                key={w}
                                onClick={() => setWindowDays(w)}
                                className={`px-3 py-1 text-xs rounded ${windowDays === w
                                    ? 'bg-white text-indigo-700 shadow-sm font-medium'
                                    : 'text-gray-600 hover:text-gray-900'}`}
                            >
                                {w}d
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
                <Card className="p-8 text-center">
                    <ShieldCheck className="w-10 h-10 mx-auto text-gray-400 mb-2" />
                    <h2 className="text-lg font-semibold text-gray-900 mb-1">Insights are not enabled</h2>
                    <p className="text-sm text-gray-500">{data.message || 'Contact your account manager to enable insights for your account.'}</p>
                </Card>
            ) : (
                <>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                        <KpiCard icon={<Eye className="w-4 h-4" />} label="Views" value={data.total_views ?? 0} />
                        <KpiCard icon={<BarChart3 className="w-4 h-4" />} label="Impressions" value={data.total_impressions ?? 0} />
                        <KpiCard icon={<Heart className="w-4 h-4" />} label="Saves" value={data.total_saves ?? 0} />
                        <KpiCard icon={<MessageSquare className="w-4 h-4" />} label="Inquiries" value={data.total_inquiries ?? 0} />
                        <KpiCard icon={<Calendar className="w-4 h-4" />} label="Bookings" value={data.total_bookings ?? 0} />
                    </div>

                    <Card className="p-0 overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Listing</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Views</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Distinct viewers</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Saves</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Inquiries</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Bookings</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">View → Inquiry</th>
                                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">View → Book</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {(data.listings ?? []).map((li: ListingInsight) => (
                                    <tr key={li.listing_id} className="hover:bg-gray-50">
                                        <td className="px-4 py-3 text-sm">
                                            <div className="font-medium text-gray-900">{li.name || '—'}</div>
                                            <div className="text-xs text-gray-500">{li.listing_type}</div>
                                        </td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{li.views.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{li.distinct_viewers.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{li.saves.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{li.inquiries.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-700">{li.bookings.toLocaleString()}</td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-500">
                                            {fmtPct(li.view_to_inquiry_rate)}
                                            {li.low_volume_suppressed && (
                                                <span className="text-[10px] text-amber-600 ml-1">low</span>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 text-sm text-right text-gray-500">
                                            {fmtPct(li.view_to_booking_rate)}
                                        </td>
                                    </tr>
                                ))}
                                {(data.listings ?? []).length === 0 && (
                                    <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                                        No listings yet.
                                    </td></tr>
                                )}
                            </tbody>
                        </table>
                    </Card>

                    <Card className="mt-4 p-4 bg-blue-50 border-blue-200 text-blue-800 text-xs flex items-start gap-2">
                        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            We never share who viewed your listing. Conversion rates marked{' '}
                            <span className="text-amber-700">low</span> mean too few distinct users to compute a reliable rate without risking re-identification.
                        </div>
                    </Card>
                </>
            )}
        </div>
    );
};

const KpiCard: React.FC<{ icon: React.ReactNode; label: string; value: number }> = ({
    icon, label, value,
}) => (
    <Card className="p-4">
        <div className="flex items-center gap-1 text-xs text-gray-500 uppercase">
            {icon} <span>{label}</span>
        </div>
        <div className="text-2xl font-bold text-gray-900 mt-1">{value.toLocaleString()}</div>
    </Card>
);

export default OwnerInsights;
