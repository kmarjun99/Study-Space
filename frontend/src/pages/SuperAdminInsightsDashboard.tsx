/**
 * Super-admin platform insights dashboard (Phase 5).
 *
 * Shows the search → book funnel, top demand cities, segment sizes,
 * campaign performance, and notification-automation health in one place.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ArrowLeft, RefreshCw, TrendingUp, MapPin, Users, Send, Zap,
} from 'lucide-react';
import { Card, Button } from '../components/UI';
import { FeatureFlagToggle } from '../components/FeatureFlagToggle';
import { insightsService, AdminDashboard as AD } from '../services/insightsService';

const WINDOWS = [7, 30, 90];

export const SuperAdminInsightsDashboard: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<AD | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [windowDays, setWindowDays] = useState(30);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const d = await insightsService.adminDashboard(windowDays);
            setData(d);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load dashboard.');
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
            <FeatureFlagToggle
                flagKey="insights.enabled"
                label="Platform insights"
                description="Owner + super-admin insights dashboards"
                onChange={() => void refresh()}
            />
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                        <TrendingUp className="w-6 h-6 text-indigo-600" /> Platform insights
                    </h1>
                    <p className="text-gray-500 text-sm">
                        Cross-cutting intelligence layer view.
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
                <Card className="p-8 text-center text-gray-500">
                    Insights are not enabled. Set <code className="bg-gray-100 px-1 rounded">insights.enabled</code> in tax_config.
                </Card>
            ) : (
                <>
                    {/* Funnel */}
                    <Card className="p-6 mb-4">
                        <h2 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide">
                            Search → Book funnel
                        </h2>
                        <div className="grid grid-cols-5 gap-3">
                            {(data.funnel ?? []).map(s => (
                                <div key={s.name} className="text-center">
                                    <div className="text-2xl font-bold text-gray-900">{s.count.toLocaleString()}</div>
                                    <div className="text-xs text-gray-500 uppercase">{s.name}</div>
                                </div>
                            ))}
                        </div>
                    </Card>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Top cities */}
                        <Card className="p-6">
                            <h2 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide flex items-center gap-1">
                                <MapPin className="w-4 h-4" /> Top demand cities
                            </h2>
                            {(data.top_cities ?? []).length === 0 ? (
                                <div className="text-gray-400 text-sm">No search activity in this window.</div>
                            ) : (
                                <table className="min-w-full text-sm">
                                    <thead>
                                        <tr className="text-xs text-gray-500 uppercase">
                                            <th className="text-left py-1">City</th>
                                            <th className="text-right py-1">Searches</th>
                                            <th className="text-right py-1">Users</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.top_cities!.map(c => (
                                            <tr key={c.city} className="border-t">
                                                <td className="py-1.5 text-gray-900">{c.city}</td>
                                                <td className="py-1.5 text-right text-gray-700">{c.searches.toLocaleString()}</td>
                                                <td className="py-1.5 text-right text-gray-500">{c.distinct_users.toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </Card>

                        {/* Segments */}
                        <Card className="p-6">
                            <h2 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide flex items-center gap-1">
                                <Users className="w-4 h-4" /> Active segments
                            </h2>
                            {(data.segments ?? []).length === 0 ? (
                                <div className="text-gray-400 text-sm">No active segments.</div>
                            ) : (
                                <table className="min-w-full text-sm">
                                    <thead>
                                        <tr className="text-xs text-gray-500 uppercase">
                                            <th className="text-left py-1">Segment</th>
                                            <th className="text-right py-1">Members</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.segments!.map(s => (
                                            <tr key={s.segment_id} className="border-t">
                                                <td className="py-1.5 text-gray-900">{s.name}</td>
                                                <td className="py-1.5 text-right text-gray-700">{s.active_members.toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </Card>

                        {/* Campaigns */}
                        <Card className="p-6">
                            <h2 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide flex items-center gap-1">
                                <Send className="w-4 h-4" /> Campaign activity
                            </h2>
                            {(data.campaigns ?? []).length === 0 ? (
                                <div className="text-gray-400 text-sm">No campaign activity in this window.</div>
                            ) : (
                                <table className="min-w-full text-sm">
                                    <thead>
                                        <tr className="text-xs text-gray-500 uppercase">
                                            <th className="text-left py-1">Campaign</th>
                                            <th className="text-right py-1">Sent</th>
                                            <th className="text-right py-1">Clicked</th>
                                            <th className="text-right py-1">Booked</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {data.campaigns!.map(c => (
                                            <tr key={c.campaign_id} className="border-t">
                                                <td className="py-1.5 text-gray-900 font-mono text-xs">{c.slug}</td>
                                                <td className="py-1.5 text-right text-gray-700">{c.delivered.toLocaleString()}</td>
                                                <td className="py-1.5 text-right text-gray-700">{c.clicked.toLocaleString()}</td>
                                                <td className="py-1.5 text-right text-gray-700">{c.converted.toLocaleString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </Card>

                        {/* Automation */}
                        <Card className="p-6">
                            <h2 className="text-sm font-semibold text-gray-900 mb-3 uppercase tracking-wide flex items-center gap-1">
                                <Zap className="w-4 h-4" /> Notification automation
                            </h2>
                            <div className="grid grid-cols-2 gap-3 text-sm">
                                <Stat label="Active rules" value={data.automation?.active_rules ?? 0} />
                                <Stat label="Queued" value={data.automation?.queued_total ?? 0} />
                                <Stat label="Delivered" value={data.automation?.delivered_total ?? 0} />
                                <Stat label="Failed" value={data.automation?.failed_total ?? 0} />
                            </div>
                        </Card>
                    </div>
                </>
            )}
        </div>
    );
};

const Stat: React.FC<{ label: string; value: number }> = ({ label, value }) => (
    <div>
        <div className="text-xs text-gray-500 uppercase">{label}</div>
        <div className="text-xl font-bold text-gray-900">{value.toLocaleString()}</div>
    </div>
);

export default SuperAdminInsightsDashboard;
