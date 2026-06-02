/**
 * Owner-facing settlement statements.
 *
 * Lists every settlement run for the current owner with the full breakdown:
 * gross → refunds → TCS → TDS → maintenance offset → net payout, along with
 * the UTR if a RazorpayX payout has been recorded.
 *
 * Clicking a row opens line-level detail (one row per booking + each deduction).
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, ChevronRight, Receipt, AlertCircle } from 'lucide-react';
import {
    settlementService, SettlementRun, SettlementDetail, SettlementStatus,
} from '../services/settlementService';

const statusVariant = (s: SettlementStatus): 'success' | 'warning' | 'error' | 'info' => {
    switch (s) {
        case 'PAID': return 'success';
        case 'READY': return 'warning';
        case 'FAILED':
        case 'NEGATIVE_HELD': return 'error';
        default: return 'info';
    }
};

const formatINR = (n: number) =>
    n.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export const OwnerSettlements: React.FC = () => {
    const navigate = useNavigate();
    const [runs, setRuns] = useState<SettlementRun[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [detail, setDetail] = useState<SettlementDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const rows = await settlementService.listMyRuns();
                if (!cancelled) setRuns(rows);
            } catch (e: any) {
                if (!cancelled) {
                    setError(e?.response?.status === 404
                        ? 'Settlement engine is not yet enabled on the server.'
                        : (e?.response?.data?.detail || 'Could not load settlements.'));
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        void load();
        return () => { cancelled = true; };
    }, []);

    const openDetail = async (run: SettlementRun) => {
        setDetailLoading(true);
        setDetail(null);
        try {
            const d = await settlementService.getMyRun(run.id);
            setDetail(d);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not load settlement detail.');
        } finally {
            setDetailLoading(false);
        }
    };

    return (
        <div className="max-w-5xl mx-auto pb-10">
            <button
                onClick={() => navigate('/admin/profile')}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back to Profile
            </button>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Settlements</h1>
            <p className="text-gray-500 mb-6">
                Booking collections paid out to your bank account, net of TCS, TDS and platform deductions.
            </p>

            {error && (
                <Card className="p-4 mb-4 border-amber-200 bg-amber-50">
                    <div className="flex items-start gap-3 text-sm text-amber-800">
                        <AlertCircle className="w-5 h-5 mt-0.5" /> {error}
                    </div>
                </Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : runs.length === 0 && !error ? (
                <Card className="p-8 text-center text-gray-400">
                    <Receipt className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No settlement runs yet.</p>
                    <p className="text-xs mt-1">Settlements run nightly. Eligible bookings appear here after the T+N hold window.</p>
                </Card>
            ) : (
                <Card className="p-0 mb-6 overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Gross</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Refunds</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">TCS</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">TDS</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Offsets</th>
                                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Net Payout</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {runs.map(r => (
                                <tr key={r.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(r)}>
                                    <td className="px-4 py-3 text-sm text-gray-700">
                                        {new Date(r.period_start).toLocaleDateString('en-IN')} – {new Date(r.period_end).toLocaleDateString('en-IN')}
                                    </td>
                                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatINR(r.gross)}</td>
                                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatINR(r.refunds)}</td>
                                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatINR(r.tcs_total)}</td>
                                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatINR(r.tds_total)}</td>
                                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatINR(r.platform_offset)}</td>
                                    <td className="px-4 py-3 text-sm text-right font-semibold text-gray-900">{formatINR(r.net_payout)}</td>
                                    <td className="px-4 py-3"><Badge variant={statusVariant(r.status)} className="text-xs">{r.status}</Badge></td>
                                    <td className="px-4 py-3 text-right"><ChevronRight className="w-4 h-4 text-gray-400" /></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {detailLoading && <Card className="p-4 mb-4 text-sm text-gray-500">Loading detail…</Card>}
            {detail && (
                <Card className="p-6 mt-2">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-900">Run {detail.run.id.slice(0, 8)} — line items</h2>
                        <button className="text-sm text-indigo-600" onClick={() => setDetail(null)}>Close</button>
                    </div>
                    {detail.run.payout_ref && (
                        <div className="text-sm text-gray-600 mb-3">UTR: <span className="font-mono">{detail.run.payout_ref}</span> on {detail.run.payout_at && new Date(detail.run.payout_at).toLocaleString('en-IN')}</div>
                    )}
                    <div className="overflow-hidden rounded border">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Kind</th>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Reference</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Base</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Deduction</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Net</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {detail.lines.map(l => (
                                    <tr key={l.id}>
                                        <td className="px-4 py-2 text-sm font-medium text-gray-900">{l.kind.replace('_', ' ')}</td>
                                        <td className="px-4 py-2 text-sm text-gray-500 font-mono">{l.reference_id ? l.reference_id.slice(0, 8) : '—'}</td>
                                        <td className="px-4 py-2 text-sm text-right text-gray-700">{formatINR(l.base_amount)}</td>
                                        <td className="px-4 py-2 text-sm text-right text-gray-700">{formatINR(l.deduction)}</td>
                                        <td className={`px-4 py-2 text-sm text-right font-semibold ${l.net < 0 ? 'text-red-600' : 'text-gray-900'}`}>{formatINR(l.net)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </Card>
            )}
        </div>
    );
};

export default OwnerSettlements;
