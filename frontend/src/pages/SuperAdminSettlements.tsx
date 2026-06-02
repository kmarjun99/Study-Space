/**
 * Super-admin settlements view.
 *
 * - Lists all settlement runs across all owners
 * - Manual trigger button (kicks the daily aggregator on demand)
 * - Mark-paid (record UTR) and Mark-failed (record reason) actions
 *
 * For NEGATIVE_HELD runs, no payout option is offered — these need an
 * out-of-band RECOVERY charge created against the owner first.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, Play, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import {
    settlementService, SettlementRun, SettlementStatus,
} from '../services/settlementService';

const STATUSES: (SettlementStatus | 'ALL')[] = ['ALL', 'READY', 'PAID', 'FAILED', 'NEGATIVE_HELD'];

const variantFor = (s: SettlementStatus): 'success' | 'warning' | 'error' | 'info' => {
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

export const SuperAdminSettlements: React.FC = () => {
    const navigate = useNavigate();
    const [runs, setRuns] = useState<SettlementRun[]>([]);
    const [filter, setFilter] = useState<(typeof STATUSES)[number]>('ALL');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [triggering, setTriggering] = useState(false);
    const [busyRunId, setBusyRunId] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const rows = await settlementService.listAllRuns(
                filter === 'ALL' ? undefined : filter,
            );
            setRuns(rows);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load settlements.');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleTrigger = async () => {
        if (!confirm('Run the settlement aggregator now? This processes all eligible bookings.')) return;
        setTriggering(true);
        try {
            const summary = await settlementService.triggerRun();
            if (summary.runs_created > 0) {
                alert(`Created ${summary.runs_created} run(s) for ${summary.owners} owner(s).`);
            } else {
                // Zero runs is not a code failure — it means no bookings met the
                // eligibility criteria right now. Explain what those are so the
                // operator knows what to check (and doesn't think the aggregator
                // is broken).
                alert(
                    'Created 0 settlement runs. No bookings are currently eligible.\n\n'
                    + 'A booking becomes eligible only when ALL of these are true:\n'
                    + '  • payment_status = PAID\n'
                    + '  • settled_at IS NULL (not already settled)\n'
                    + '  • gst_treatment IS NOT NULL and != LEGACY\n'
                    + '  • paid_at IS NOT NULL\n'
                    + '  • paid_at is older than the configured hold window (T+N days)\n\n'
                    + 'If you have recent PAID bookings but none qualify, the most '
                    + 'common reasons are: (a) accounting.enabled is false so the '
                    + 'shadow never set gst_treatment / paid_at, (b) bookings are still '
                    + 'inside the hold window, or (c) owner KYC is incomplete.',
                );
            }
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not trigger settlement run.');
        } finally {
            setTriggering(false);
        }
    };

    const handleMarkPaid = async (run: SettlementRun) => {
        const utr = prompt(`Enter RazorpayX payout UTR for ${formatINR(run.net_payout)}:`);
        if (!utr) return;
        setBusyRunId(run.id);
        try {
            await settlementService.markPaid(run.id, utr.trim());
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not mark as paid.');
        } finally {
            setBusyRunId(null);
        }
    };

    const handleMarkFailed = async (run: SettlementRun) => {
        const reason = prompt('Failure reason:');
        if (!reason) return;
        setBusyRunId(run.id);
        try {
            await settlementService.markFailed(run.id, reason.trim());
            await refresh();
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not mark as failed.');
        } finally {
            setBusyRunId(null);
        }
    };

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
                    <h1 className="text-2xl font-bold text-gray-900">Settlements</h1>
                    <p className="text-gray-500 text-sm">All owner payouts, statutory deductions and platform offsets.</p>
                </div>
                <Button onClick={handleTrigger} isLoading={triggering}>
                    <Play className="w-4 h-4 mr-1" /> Run Aggregator Now
                </Button>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
                {STATUSES.map(s => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`text-sm px-3 py-1 rounded-full border ${
                            filter === s ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-300'
                        }`}
                    >
                        {s}
                    </button>
                ))}
            </div>

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : runs.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">No settlement runs match this filter.</Card>
            ) : (
                <Card className="p-0 overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Period</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Gross</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Refunds</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">TCS</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">TDS</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Offsets</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Net</th>
                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {runs.map(r => (
                                <tr key={r.id}>
                                    <td className="px-3 py-3 text-xs text-gray-700 font-mono">{r.owner_id.slice(0, 8)}</td>
                                    <td className="px-3 py-3 text-xs text-gray-500">
                                        {new Date(r.period_start).toLocaleDateString('en-IN')}<br />
                                        – {new Date(r.period_end).toLocaleDateString('en-IN')}
                                    </td>
                                    <td className="px-3 py-3 text-sm text-right text-gray-700">{formatINR(r.gross)}</td>
                                    <td className="px-3 py-3 text-sm text-right text-gray-700">{formatINR(r.refunds)}</td>
                                    <td className="px-3 py-3 text-sm text-right text-gray-700">{formatINR(r.tcs_total)}</td>
                                    <td className="px-3 py-3 text-sm text-right text-gray-700">{formatINR(r.tds_total)}</td>
                                    <td className="px-3 py-3 text-sm text-right text-gray-700">{formatINR(r.platform_offset)}</td>
                                    <td className={`px-3 py-3 text-sm text-right font-semibold ${r.net_payout < 0 ? 'text-red-600' : 'text-gray-900'}`}>{formatINR(r.net_payout)}</td>
                                    <td className="px-3 py-3">
                                        <Badge variant={variantFor(r.status)} className="text-xs">{r.status}</Badge>
                                        {r.status === 'PAID' && r.payout_ref && (
                                            <div className="text-xs text-gray-400 font-mono mt-1">UTR: {r.payout_ref}</div>
                                        )}
                                        {r.status === 'NEGATIVE_HELD' && (
                                            <div className="flex items-center text-xs text-amber-700 mt-1">
                                                <AlertTriangle className="w-3 h-3 mr-1" /> Recovery needed
                                            </div>
                                        )}
                                    </td>
                                    <td className="px-3 py-3 text-right space-x-2">
                                        {r.status === 'READY' && (
                                            <>
                                                <Button size="sm" onClick={() => handleMarkPaid(r)} isLoading={busyRunId === r.id}>
                                                    <CheckCircle className="w-3 h-3 mr-1" /> Mark Paid
                                                </Button>
                                                <Button size="sm" variant="outline" onClick={() => handleMarkFailed(r)} isLoading={busyRunId === r.id}>
                                                    <XCircle className="w-3 h-3 mr-1" /> Fail
                                                </Button>
                                            </>
                                        )}
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

export default SuperAdminSettlements;
