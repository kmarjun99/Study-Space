/**
 * Super-admin KYC review.
 *
 * Status filter chips on top, table of owners, click-through to a detail
 * drawer with Approve / Reject / Request-Reupload actions. Bank account is
 * always shown masked (server enforces).
 *
 * Every state change writes an AuditLog row server-side, so this UI doesn't
 * need to maintain its own audit trail — the super-admin /trust + /finance
 * views surface audit entries separately.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import { ArrowLeft, CheckCircle, XCircle, RotateCcw, AlertCircle } from 'lucide-react';
import { kycService, KYCStatus, OwnerKYCRow } from '../services/kycService';

const STATUS_FILTERS: (KYCStatus | 'ALL')[] = ['ALL', 'PENDING', 'VERIFIED', 'REJECTED', 'NOT_REQUIRED'];

const statusVariant = (s: KYCStatus | null): 'success' | 'warning' | 'error' | 'info' => {
    switch (s) {
        case 'VERIFIED': return 'success';
        case 'PENDING': return 'warning';
        case 'REJECTED': return 'error';
        default: return 'info';
    }
};

// Modal state shape: which action the operator chose, on which row, the
// note text they're typing, and whether the note is required. Native
// `prompt()` doesn't work in Safari iframes and on most mobile browsers,
// so this inline modal replaces it everywhere on the page.
type ActionKind = 'approve' | 'reject' | 'reupload';

interface ActionModalState {
    kind: ActionKind;
    row: OwnerKYCRow;
}

const ACTION_LABELS: Record<ActionKind, { title: string; placeholder: string; required: boolean; cta: string }> = {
    approve: {
        title: 'Approve KYC',
        placeholder: 'Approval notes (optional)',
        required: false,
        cta: 'Approve',
    },
    reject: {
        title: 'Reject KYC',
        placeholder: 'Rejection reason — shown to the owner',
        required: true,
        cta: 'Reject',
    },
    reupload: {
        title: 'Request re-upload',
        placeholder: 'What needs to change? — shown to the owner',
        required: true,
        cta: 'Send request',
    },
};

export const SuperAdminKYCReview: React.FC = () => {
    const navigate = useNavigate();
    const [filter, setFilter] = useState<(typeof STATUS_FILTERS)[number]>('PENDING');
    const [rows, setRows] = useState<OwnerKYCRow[]>([]);
    const [selected, setSelected] = useState<OwnerKYCRow | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState<string | null>(null);

    const [actionModal, setActionModal] = useState<ActionModalState | null>(null);
    const [actionNote, setActionNote] = useState('');
    const [actionError, setActionError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await kycService.list(filter === 'ALL' ? undefined : filter);
            setRows(data);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Could not load KYC list.');
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => { void refresh(); }, [refresh]);

    const openAction = (kind: ActionKind, row: OwnerKYCRow) => {
        setActionModal({ kind, row });
        setActionNote('');
        setActionError(null);
    };

    const closeAction = () => {
        setActionModal(null);
        setActionNote('');
        setActionError(null);
    };

    const submitAction = async () => {
        if (!actionModal) return;
        const { kind, row } = actionModal;
        const spec = ACTION_LABELS[kind];
        const note = actionNote.trim();
        if (spec.required && !note) {
            setActionError(`${spec.title} requires a note.`);
            return;
        }
        setBusy(row.id);
        setActionError(null);
        try {
            if (kind === 'approve') {
                await kycService.approve(row.id, note || undefined);
            } else if (kind === 'reject') {
                await kycService.reject(row.id, note);
            } else {
                await kycService.requestReupload(row.id, note);
            }
            await refresh();
            setSelected(null);
            closeAction();
        } catch (e: any) {
            setActionError(e?.response?.data?.detail || 'Action failed.');
        } finally {
            setBusy(null);
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
            <h1 className="text-2xl font-bold text-gray-900 mb-1">Owner KYC Review</h1>
            <p className="text-gray-500 text-sm mb-4">
                Approve or reject owner KYC submissions. Listings cannot go LIVE
                until the owner's KYC is VERIFIED.
            </p>

            <div className="flex flex-wrap gap-2 mb-4">
                {STATUS_FILTERS.map(s => (
                    <button
                        key={s}
                        onClick={() => setFilter(s)}
                        className={`text-sm px-3 py-1 rounded-full border ${filter === s
                            ? 'bg-indigo-600 text-white border-indigo-600'
                            : 'bg-white text-gray-600 border-gray-300'
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
            ) : rows.length === 0 ? (
                <Card className="p-8 text-center text-gray-400">No owners match this filter.</Card>
            ) : (
                <Card className="p-0 overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Legal Name</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">PAN</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">GSTIN</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Bank</th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                <th className="px-4 py-3" />
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {rows.map(r => (
                                <tr key={r.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setSelected(r)}>
                                    <td className="px-4 py-3 text-sm">
                                        <div className="font-medium text-gray-900">{r.name}</div>
                                        <div className="text-xs text-gray-500">{r.email}</div>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-700">{r.legal_name || '—'}</td>
                                    <td className="px-4 py-3 text-sm font-mono text-gray-700">{r.pan || '—'}</td>
                                    <td className="px-4 py-3 text-sm font-mono text-gray-700">{r.gstin || '—'}</td>
                                    <td className="px-4 py-3 text-xs text-gray-500">
                                        {r.bank_account_number_masked || '—'}
                                        {r.bank_ifsc && <div className="font-mono">{r.bank_ifsc}</div>}
                                    </td>
                                    <td className="px-4 py-3">
                                        <Badge variant={statusVariant(r.kyc_status)} className="text-xs">
                                            {r.kyc_status || 'unset'}
                                        </Badge>
                                    </td>
                                    <td className="px-4 py-3 text-right text-xs text-indigo-600">Review →</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {selected && (
                <Card className="p-6 mt-6">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-900">{selected.name}</h2>
                        <button className="text-sm text-gray-500" onClick={() => setSelected(null)}>Close</button>
                    </div>
                    <dl className="grid grid-cols-2 gap-y-2 text-sm mb-4">
                        <dt className="text-gray-500">Email</dt><dd>{selected.email}</dd>
                        <dt className="text-gray-500">Legal Name</dt><dd>{selected.legal_name || '—'}</dd>
                        <dt className="text-gray-500">PAN</dt><dd className="font-mono">{selected.pan || '—'}</dd>
                        <dt className="text-gray-500">GSTIN</dt><dd className="font-mono">{selected.gstin || '—'}</dd>
                        <dt className="text-gray-500">GST Registration</dt><dd>{selected.gst_registration_type || '—'}</dd>
                        <dt className="text-gray-500">Business State</dt><dd>{selected.business_state_code || '—'}</dd>
                        <dt className="text-gray-500">Bank Holder</dt><dd>{selected.bank_account_holder || '—'}</dd>
                        <dt className="text-gray-500">Bank A/c</dt><dd className="font-mono">{selected.bank_account_number_masked || '—'}</dd>
                        <dt className="text-gray-500">IFSC</dt><dd className="font-mono">{selected.bank_ifsc || '—'}</dd>
                        <dt className="text-gray-500">Current Status</dt>
                        <dd><Badge variant={statusVariant(selected.kyc_status)} className="text-xs">{selected.kyc_status || 'unset'}</Badge></dd>
                        {selected.kyc_notes && (
                            <>
                                <dt className="text-gray-500">Last Review Notes</dt>
                                <dd className="text-amber-700 flex items-start gap-1">
                                    <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                    <span>{selected.kyc_notes}</span>
                                </dd>
                            </>
                        )}
                    </dl>
                    <div className="flex gap-2">
                        <Button size="sm" onClick={() => openAction('approve', selected)} isLoading={busy === selected.id}>
                            <CheckCircle className="w-4 h-4 mr-1" /> Approve
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => openAction('reject', selected)} isLoading={busy === selected.id}>
                            <XCircle className="w-4 h-4 mr-1" /> Reject
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => openAction('reupload', selected)} isLoading={busy === selected.id}>
                            <RotateCcw className="w-4 h-4 mr-1" /> Request Re-upload
                        </Button>
                    </div>
                </Card>
            )}

            {actionModal && (() => {
                const spec = ACTION_LABELS[actionModal.kind];
                return (
                    <div
                        className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
                        onClick={closeAction}
                    >
                        <Card
                            className="p-6 max-w-md w-full"
                            onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        >
                            <h3 className="text-lg font-bold text-gray-900 mb-1">{spec.title}</h3>
                            <p className="text-xs text-gray-500 mb-4">
                                Owner: <span className="font-medium text-gray-700">{actionModal.row.name}</span>
                                {' · '}
                                {actionModal.row.email}
                            </p>
                            <textarea
                                value={actionNote}
                                onChange={e => { setActionNote(e.target.value); setActionError(null); }}
                                placeholder={spec.placeholder}
                                rows={4}
                                autoFocus
                                className="w-full text-sm border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                            {actionError && (
                                <div className="text-xs text-red-600 mt-2">{actionError}</div>
                            )}
                            <div className="flex justify-end gap-2 mt-4">
                                <Button size="sm" variant="outline" onClick={closeAction}>
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={submitAction}
                                    isLoading={busy === actionModal.row.id}
                                    disabled={spec.required && !actionNote.trim()}
                                >
                                    {spec.cta}
                                </Button>
                            </div>
                        </Card>
                    </div>
                );
            })()}
        </div>
    );
};

export default SuperAdminKYCReview;
