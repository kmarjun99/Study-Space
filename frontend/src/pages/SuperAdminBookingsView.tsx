/**
 * Super-admin Bookings page.
 *
 * Replaces the old hardcoded 90/10 commission math with real GST-aware
 * financial data sourced from the accounting layer (base_amount,
 * gst_amount, gst_treatment, paid_at, settled_at). When a booking has
 * accounting data, we render the real split + the GST treatment chip.
 * When it doesn't (legacy bookings, or shadow failed silently), we
 * render a clear "no accounting data" badge so operators know the row
 * is incomplete instead of seeing made-up numbers.
 *
 * No per-booking "Settle" action exists by design — the settlement
 * engine aggregates eligible bookings per OWNER into one settlement
 * run (see backend/app/services/settlement_service.py). The per-row
 * action here deep-links to the Settlements page with the owner
 * pre-filtered so the operator can run / approve the aggregate.
 */
import React, { useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button, Badge } from '../components/UI';
import {
    User as UserIcon, ExternalLink, ArrowRight, AlertCircle,
} from 'lucide-react';
import { bookingService } from '../services/bookingService';
import type { Booking } from '../types';

// Render the GST treatment badge with treatment-specific colour. Helps
// operators eyeball the mix of OWNER_REGISTERED vs SEC_9_5 vs LEGACY
// at a glance — important because the owner-payable math differs by
// treatment (Sec 9(5) means platform keeps the GST; everything else
// passes the full gross through).
const treatmentBadgeVariant = (t: string | null | undefined) => {
    switch (t) {
        case 'OWNER_REGISTERED': return 'info';
        case 'SEC_9_5':          return 'success';
        case 'EXEMPT':           return 'warning';
        case 'NOT_REGISTERED':   return 'warning';
        case 'LEGACY':           return 'error';
        case 'NOT_COMPUTED':     return 'error';
        default:                 return 'info';
    }
};

// Compute the owner-payable amount per the GST treatment. This mirrors
// what the accounting_shadow posts to the ledger for each booking:
//   * SEC_9_5     — platform keeps GST, owner gets the taxable base
//   * everything else (registered, exempt, not_registered) — owner gets
//     the gross amount and handles their own GST liability
// Returns null when the booking has no accounting data; the UI shows
// a "—" placeholder in that case so we never display a fabricated
// number (the old page used `amount * 0.9` regardless of treatment).
const computeOwnerPayable = (b: Booking): number | null => {
    if (!b.gstTreatment) return null;
    if (b.gstTreatment === 'SEC_9_5') {
        return b.baseAmount ?? null;
    }
    return b.amount;
};

export const SuperAdminBookingsView = () => {
    const [bookings, setBookings] = useState<Booking[]>([]);
    const [loading, setLoading] = useState(true);
    const [venueFilter, setVenueFilter] = useState('');
    const [ownerFilter, setOwnerFilter] = useState('');

    useEffect(() => {
        loadBookings();
    }, []);

    const loadBookings = async () => {
        setLoading(true);
        try {
            const bData = await bookingService.getMyBookings();
            setBookings(bData);
        } catch (err) {
            console.error('Failed to load bookings', err);
        } finally {
            setLoading(false);
        }
    };

    // Apply client-side filters AFTER the page loads. Backend doesn't yet
    // expose filter params; doing it here is fine for the volumes we
    // expect on this admin page (low hundreds of rows).
    const filtered = useMemo(() => bookings.filter(b => {
        const venueOk = !venueFilter
            || (b.venueName || '').toLowerCase().includes(venueFilter.toLowerCase());
        const ownerOk = !ownerFilter
            || (b.ownerName || '').toLowerCase().includes(ownerFilter.toLowerCase());
        return venueOk && ownerOk;
    }), [bookings, venueFilter, ownerFilter]);

    // KPI summaries — computed from REAL accounting fields when available.
    // Falls back to gross for legacy / pre-accounting bookings; the UI
    // shows a small note that the pending payout is approximate when
    // any rows lack accounting data.
    const summary = useMemo(() => {
        let totalGross = 0;
        let pendingOwnerPayable = 0;       // sum of owner-payable on PAID + unsettled
        let settledOwnerPayable = 0;       // sum of owner-payable on settled
        let rowsMissingAccounting = 0;
        for (const b of filtered) {
            totalGross += b.amount || 0;
            const payable = computeOwnerPayable(b);
            const isPaid = b.paymentStatus === 'PAID';
            const isSettled = !!b.settledAt || b.settlementStatus === 'SETTLED';
            if (isPaid && !b.gstTreatment) rowsMissingAccounting += 1;
            if (isPaid && !isSettled) {
                pendingOwnerPayable += payable ?? (b.amount || 0);
            }
            if (isPaid && isSettled) {
                settledOwnerPayable += payable ?? (b.amount || 0);
            }
        }
        return {
            totalGross,
            pendingOwnerPayable,
            settledOwnerPayable,
            activeCount: filtered.filter(b => b.status === 'ACTIVE').length,
            rowsMissingAccounting,
        };
    }, [filtered]);

    const downloadCSV = () => {
        if (!bookings.length) {
            alert('No bookings to export.');
            return;
        }
        const headers = [
            'Booking ID', 'Transaction ID', 'Venue Name', 'Owner Name',
            'Resource', 'Start Date', 'End Date',
            'Gross Amount', 'Base Amount', 'GST Amount', 'GST Rate', 'GST Treatment',
            'Owner Payable', 'Paid At', 'Settled At', 'Settlement Run',
            'Settlement Status', 'Booking Status',
        ];
        const escape = (s: any) => `"${String(s ?? '').replace(/"/g, '""')}"`;
        const csvRows = [
            headers.join(','),
            ...bookings.map(b => [
                b.id || '',
                b.transactionId || '',
                escape(b.venueName),
                escape(b.ownerName),
                escape(b.cabinId ? `Cabin ${b.cabinNumber}` : `Housing #${b.accommodationId}`),
                b.startDate ? new Date(b.startDate).toLocaleDateString() : '',
                b.endDate ? new Date(b.endDate).toLocaleDateString() : '',
                b.amount || 0,
                b.baseAmount ?? '',
                b.gstAmount ?? '',
                b.gstRateApplied ?? '',
                b.gstTreatment ?? '',
                computeOwnerPayable(b) ?? '',
                b.paidAt ?? '',
                b.settledAt ?? '',
                b.settlementRunId ?? '',
                b.settlementStatus || 'NOT_SETTLED',
                b.status || '',
            ].join(',')),
        ];
        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', `bookings_report_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Booking Console</h2>
                    <p className="text-gray-500">
                        Monitor reservations, GST-aware financials, and settlement state.
                    </p>
                </div>
                <Button variant="outline" onClick={downloadCSV}>
                    <ExternalLink className="w-4 h-4 mr-2" /> Export CSV
                </Button>
            </div>

            {summary.rowsMissingAccounting > 0 && (
                <Card className="p-4 border-amber-200 bg-amber-50">
                    <div className="flex items-start gap-3 text-sm text-amber-900">
                        <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div>
                            <strong>{summary.rowsMissingAccounting}</strong> PAID
                            booking{summary.rowsMissingAccounting === 1 ? '' : 's'}
                            {' '}have no GST accounting data. They were paid before
                            <code className="font-mono bg-amber-100 px-1 mx-0.5 rounded">accounting.enabled</code>
                            was switched on, OR the accounting shadow failed silently
                            (check Cloud Run logs for{' '}
                            <code className="font-mono bg-amber-100 px-1 rounded">studyspace.accounting</code>
                            ). Owner-payable totals below fall back to the gross
                            amount for those rows.
                        </div>
                    </div>
                </Card>
            )}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Total Revenue (Gross)</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                        ₹{summary.totalGross.toLocaleString()}
                    </p>
                    <p className="text-xs text-indigo-600 mt-1">Lifetime Volume</p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Pending Payouts</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                        ₹{summary.pendingOwnerPayable.toLocaleString()}
                    </p>
                    <p className="text-xs text-orange-600 mt-1">
                        Owner payable (PAID, unsettled)
                    </p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Settled</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                        ₹{summary.settledOwnerPayable.toLocaleString()}
                    </p>
                    <p className="text-xs text-green-600 mt-1">Paid out via settlement runs</p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Active Bookings</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{summary.activeCount}</p>
                    <p className="text-xs text-blue-600 mt-1">Ongoing</p>
                </Card>
            </div>

            <Card className="p-0 overflow-hidden border border-gray-200">
                <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                    <h3 className="font-semibold text-gray-700">
                        All Reservations
                        <span className="ml-2 text-xs text-gray-500 font-normal">
                            ({filtered.length} of {bookings.length})
                        </span>
                    </h3>
                    <div className="flex gap-2">
                        <input
                            placeholder="Filter by Venue..."
                            value={venueFilter}
                            onChange={(e) => setVenueFilter(e.target.value)}
                            className="px-3 py-1 border rounded text-sm"
                        />
                        <input
                            placeholder="Filter by Owner..."
                            value={ownerFilter}
                            onChange={(e) => setOwnerFilter(e.target.value)}
                            className="px-3 py-1 border rounded text-sm"
                        />
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-gray-500">
                        <thead className="bg-white text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-4">Booking ID</th>
                                <th className="px-6 py-4">Venue &amp; Owner</th>
                                <th className="px-6 py-4">Resource</th>
                                <th className="px-6 py-4">Date Range</th>
                                <th className="px-6 py-4">Financials</th>
                                <th className="px-6 py-4">Settlement</th>
                                <th className="px-6 py-4">Status</th>
                                <th className="px-6 py-4 text-right">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {loading ? (
                                <tr><td colSpan={8} className="px-6 py-8 text-center text-gray-400">Loading bookings...</td></tr>
                            ) : filtered.length > 0 ? filtered.map(b => {
                                const ownerPayable = computeOwnerPayable(b);
                                const hasAccounting = !!b.gstTreatment;
                                const isSettled = !!b.settledAt || b.settlementStatus === 'SETTLED';
                                const isPaid = b.paymentStatus === 'PAID';
                                // Build a deep link to the Settlements page so the
                                // operator can run / approve the aggregate for
                                // this owner. We can't settle one booking in
                                // isolation — the engine groups by owner.
                                const settlementsHref = b.ownerId
                                    ? `/super-admin/settlements?owner=${encodeURIComponent(b.ownerId)}`
                                    : '/super-admin/settlements';

                                return (
                                    <tr key={b.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4">
                                            <div className="font-mono text-xs">{b.id.slice(0, 8)}...</div>
                                            <div className="text-xs text-gray-400 mt-1">
                                                {b.transactionId ? `Txn: ${b.transactionId.slice(0, 12)}` : 'No Txn'}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="font-medium text-gray-900">{b.venueName || 'Unknown Venue'}</div>
                                            <div className="text-xs text-gray-500 flex items-center gap-1">
                                                <UserIcon className="w-3 h-3" /> {b.ownerName || 'Unknown Owner'}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 font-medium text-gray-900">
                                            {b.cabinId ? `Cabin ${b.cabinNumber}` : `Housing #${b.accommodationId?.slice(0, 6)}`}
                                        </td>
                                        <td className="px-6 py-4 text-xs">
                                            <div className="whitespace-nowrap">
                                                {b.startDate ? new Date(b.startDate).toLocaleDateString() : 'N/A'}
                                            </div>
                                            <div className="text-gray-400">
                                                to {b.endDate ? new Date(b.endDate).toLocaleDateString() : 'N/A'}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            {/* Gross is always shown — that's what the
                                                customer paid. Below it: the real GST
                                                breakdown when the accounting shadow
                                                ran, OR an explicit "no accounting" tag. */}
                                            <div className="font-bold text-gray-900">
                                                ₹{Number(b.amount || 0).toLocaleString()}
                                            </div>
                                            {hasAccounting ? (
                                                <div className="text-xs text-gray-500 mt-1 space-y-0.5">
                                                    <div className="flex justify-between gap-3">
                                                        <span>Base:</span>
                                                        <span className="font-medium text-gray-700">
                                                            ₹{Number(b.baseAmount ?? 0).toLocaleString()}
                                                        </span>
                                                    </div>
                                                    <div className="flex justify-between gap-3">
                                                        <span>GST{b.gstRateApplied != null && ` (${Math.round((b.gstRateApplied) * 1000) / 10}%)`}:</span>
                                                        <span className="font-medium text-gray-700">
                                                            ₹{Number(b.gstAmount ?? 0).toLocaleString()}
                                                        </span>
                                                    </div>
                                                    <div className="flex justify-between gap-3 pt-0.5 border-t border-gray-100 mt-1">
                                                        <span>Owner payable:</span>
                                                        <span className="font-semibold text-green-700">
                                                            ₹{Number(ownerPayable ?? 0).toLocaleString()}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <Badge
                                                            variant={treatmentBadgeVariant(b.gstTreatment)}
                                                            className="text-[10px] mt-1"
                                                        >
                                                            {b.gstTreatment}
                                                        </Badge>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="text-xs text-gray-400 mt-1">
                                                    <Badge variant="error" className="text-[10px]">
                                                        NO ACCOUNTING DATA
                                                    </Badge>
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            <Badge variant={isSettled ? 'success' : (b.settlementStatus === 'ON_HOLD' ? 'error' : 'warning')}>
                                                {isSettled ? 'SETTLED' : (b.settlementStatus || 'NOT_SETTLED')}
                                            </Badge>
                                            {b.settlementRunId && (
                                                <div className="text-[10px] text-gray-400 mt-1 font-mono">
                                                    run {b.settlementRunId.slice(0, 6)}
                                                </div>
                                            )}
                                            {b.paidAt && !isSettled && (
                                                <div className="text-[10px] text-gray-400 mt-1">
                                                    paid {new Date(b.paidAt).toLocaleDateString()}
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            <Badge variant={b.status === 'ACTIVE' ? 'success' : b.status === 'CANCELLED' ? 'error' : 'warning'}>
                                                {b.status}
                                            </Badge>
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            {/* No per-booking settle button by design —
                                                the engine aggregates by owner. Deep
                                                link to the Settlements page where the
                                                operator can run / approve the run that
                                                will include this booking. */}
                                            {isPaid && !isSettled ? (
                                                <Link
                                                    to={settlementsHref}
                                                    className="inline-flex items-center text-indigo-600 hover:text-indigo-800 text-xs font-medium"
                                                    title="Open Settlements console for this owner"
                                                >
                                                    Settle owner <ArrowRight className="w-3 h-3 ml-1" />
                                                </Link>
                                            ) : (
                                                <span className="text-xs text-gray-300">—</span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            }) : (
                                <tr><td colSpan={8} className="px-6 py-8 text-center bg-gray-50/50">No bookings match the current filters.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
};
