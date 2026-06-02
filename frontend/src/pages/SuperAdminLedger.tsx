/**
 * Super-admin ledger explorer.
 *
 * Filter form on top (date range, account code, party, source, side),
 * paginated rows below, with a "Check balance" link per txn_group_id and
 * a "Download CSV" button that respects the active filter.
 *
 * Read-only; nothing here can mutate the ledger.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, Download, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react';
import {
    ledgerService, LedgerFilters, LedgerPage, GroupBalance,
} from '../services/ledgerService';

const PAGE_SIZE = 50;

const formatINR = (n: number) =>
    n.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export const SuperAdminLedger: React.FC = () => {
    const navigate = useNavigate();
    const [filters, setFilters] = useState<LedgerFilters>({ limit: PAGE_SIZE, offset: 0 });
    const [page, setPage] = useState<LedgerPage | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [groupBalance, setGroupBalance] = useState<GroupBalance | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const result = await ledgerService.query(filters);
            setPage(result);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load ledger.');
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => { void refresh(); }, [refresh]);

    const handleDownload = async () => {
        try {
            const blob = await ledgerService.exportCsv(filters);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ledger_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not export CSV.');
        }
    };

    const checkGroup = async (txnGroupId: string) => {
        try {
            const res = await ledgerService.groupBalance(txnGroupId);
            setGroupBalance(res);
        } catch (e: any) {
            alert(e?.response?.data?.detail || 'Could not check group balance.');
        }
    };

    const setFilter = (key: keyof LedgerFilters, value: string | undefined) => {
        setFilters(prev => ({ ...prev, [key]: value || undefined, offset: 0 }));
    };

    const balanced = page && page.sum_debit === page.sum_credit;

    return (
        <div className="max-w-7xl mx-auto pb-10">
            <button
                onClick={() => navigate(-1)}
                className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
                <ArrowLeft className="w-4 h-4 mr-1" /> Back
            </button>
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Ledger Explorer</h1>
                    <p className="text-gray-500 text-sm">All double-entry rows. Read-only.</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={refresh}>
                        <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                    </Button>
                    <Button size="sm" onClick={handleDownload}>
                        <Download className="w-4 h-4 mr-1" /> Export CSV
                    </Button>
                </div>
            </div>

            <Card className="p-4 mb-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <input
                        type="date"
                        value={(filters.posted_from || '').slice(0, 10)}
                        onChange={e => setFilter('posted_from', e.target.value || undefined)}
                        placeholder="From"
                        className="border rounded px-3 py-2 text-sm"
                    />
                    <input
                        type="date"
                        value={(filters.posted_to || '').slice(0, 10)}
                        onChange={e => setFilter('posted_to', e.target.value || undefined)}
                        placeholder="To"
                        className="border rounded px-3 py-2 text-sm"
                    />
                    <input
                        value={filters.account_code || ''}
                        onChange={e => setFilter('account_code', e.target.value)}
                        placeholder="Account code (e.g. 2010)"
                        className="border rounded px-3 py-2 text-sm font-mono"
                    />
                    <input
                        value={filters.party_id || ''}
                        onChange={e => setFilter('party_id', e.target.value)}
                        placeholder="Party id"
                        className="border rounded px-3 py-2 text-sm font-mono"
                    />
                    <select
                        value={filters.party_type || ''}
                        onChange={e => setFilter('party_type', e.target.value || undefined)}
                        className="border rounded px-3 py-2 text-sm"
                    >
                        <option value="">— Any party type —</option>
                        <option value="STUDENT">STUDENT</option>
                        <option value="OWNER">OWNER</option>
                        <option value="PLATFORM">PLATFORM</option>
                    </select>
                    <input
                        value={filters.source_type || ''}
                        onChange={e => setFilter('source_type', e.target.value)}
                        placeholder="Source type (BOOKING, etc.)"
                        className="border rounded px-3 py-2 text-sm font-mono"
                    />
                    <input
                        value={filters.source_id || ''}
                        onChange={e => setFilter('source_id', e.target.value)}
                        placeholder="Source id"
                        className="border rounded px-3 py-2 text-sm font-mono"
                    />
                    <select
                        value={filters.side || ''}
                        onChange={e => setFilter('side', e.target.value as 'DEBIT' | 'CREDIT' | undefined)}
                        className="border rounded px-3 py-2 text-sm"
                    >
                        <option value="">— Both sides —</option>
                        <option value="DEBIT">Debit only</option>
                        <option value="CREDIT">Credit only</option>
                    </select>
                </div>
            </Card>

            {error && (
                <Card className="p-4 mb-4 border-red-200 bg-red-50 text-red-700 text-sm">{error}</Card>
            )}

            {page && (
                <Card className="p-4 mb-4 grid grid-cols-3 gap-4 text-sm">
                    <div><span className="text-gray-500">Rows:</span> <span className="font-semibold">{page.total.toLocaleString()}</span></div>
                    <div><span className="text-gray-500">Σ Debit:</span> <span className="font-semibold">{formatINR(page.sum_debit)}</span></div>
                    <div>
                        <span className="text-gray-500">Σ Credit:</span> <span className="font-semibold">{formatINR(page.sum_credit)}</span>
                        {' '}
                        {balanced ? (
                            <Badge variant="success" className="text-xs"><CheckCircle className="w-3 h-3 inline mr-1" />balanced</Badge>
                        ) : (
                            <Badge variant="warning" className="text-xs"><AlertCircle className="w-3 h-3 inline mr-1" />unbalanced</Badge>
                        )}
                    </div>
                </Card>
            )}

            {loading ? (
                <div className="text-gray-500">Loading…</div>
            ) : !page || page.rows.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">No ledger rows match the filter.</Card>
            ) : (
                <Card className="p-0 overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-xs">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Posted</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Group</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Source</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Account</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Party</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Debit</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-500 uppercase">Credit</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-500 uppercase">Narration</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {page.rows.map(r => (
                                <tr key={r.id}>
                                    <td className="px-3 py-2 text-gray-500 whitespace-nowrap">{new Date(r.posted_at).toLocaleString('en-IN')}</td>
                                    <td className="px-3 py-2 font-mono text-gray-500">
                                        <button className="text-indigo-600 hover:underline" onClick={() => checkGroup(r.txn_group_id)}>
                                            {r.txn_group_id.slice(0, 8)}
                                        </button>
                                    </td>
                                    <td className="px-3 py-2 text-gray-700">
                                        <div className="font-medium">{r.source_type}</div>
                                        <div className="font-mono text-gray-400">{r.source_id.slice(0, 8)}</div>
                                    </td>
                                    <td className="px-3 py-2 font-mono text-gray-700">{r.account_code}</td>
                                    <td className="px-3 py-2 text-gray-700">
                                        {r.party_type ? <div className="font-medium">{r.party_type}</div> : null}
                                        {r.party_id ? <div className="font-mono text-gray-400">{r.party_id.slice(0, 8)}</div> : null}
                                    </td>
                                    <td className="px-3 py-2 text-right text-gray-900">{r.debit > 0 ? formatINR(r.debit) : ''}</td>
                                    <td className="px-3 py-2 text-right text-gray-900">{r.credit > 0 ? formatINR(r.credit) : ''}</td>
                                    <td className="px-3 py-2 text-gray-500">{r.narration || ''}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {page && page.total > (filters.limit ?? PAGE_SIZE) && (
                <div className="mt-3 flex items-center justify-between text-sm">
                    <span className="text-gray-500">
                        Showing {filters.offset ?? 0} – {(filters.offset ?? 0) + page.rows.length} of {page.total.toLocaleString()}
                    </span>
                    <div className="flex gap-2">
                        <Button
                            size="sm" variant="outline"
                            onClick={() => setFilters(prev => ({ ...prev, offset: Math.max(0, (prev.offset ?? 0) - PAGE_SIZE) }))}
                            disabled={(filters.offset ?? 0) === 0}
                        >Prev</Button>
                        <Button
                            size="sm" variant="outline"
                            onClick={() => setFilters(prev => ({ ...prev, offset: (prev.offset ?? 0) + PAGE_SIZE }))}
                            disabled={(filters.offset ?? 0) + page.rows.length >= page.total}
                        >Next</Button>
                    </div>
                </div>
            )}

            {groupBalance && (
                <Card className="p-4 mt-4">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-gray-900">
                            Group {groupBalance.txn_group_id.slice(0, 8)} balance
                        </h3>
                        <button className="text-sm text-gray-500" onClick={() => setGroupBalance(null)}>Close</button>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                        <div><span className="text-gray-500">Σ Debit:</span> {formatINR(groupBalance.sum_debit)}</div>
                        <div><span className="text-gray-500">Σ Credit:</span> {formatINR(groupBalance.sum_credit)}</div>
                        <div>
                            {groupBalance.balanced ? (
                                <Badge variant="success"><CheckCircle className="w-3 h-3 inline mr-1" />balanced</Badge>
                            ) : (
                                <Badge variant="error"><AlertCircle className="w-3 h-3 inline mr-1" />IMBALANCED</Badge>
                            )}
                        </div>
                    </div>
                </Card>
            )}
        </div>
    );
};

export default SuperAdminLedger;
