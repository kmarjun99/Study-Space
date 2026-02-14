
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../components/UI';
import { User as UserIcon, ExternalLink } from 'lucide-react';
import { bookingService } from '../services/bookingService';

export const SuperAdminBookingsView = () => {
    const [bookings, setBookings] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadBookings();
    }, []);

    const loadBookings = async () => {
        setLoading(true);
        try {
            const bData = await bookingService.getMyBookings();
            setBookings(bData);
        } catch (err) {
            console.error("Failed to load bookings", err);
        } finally {
            setLoading(false);
        }
    };

    const downloadCSV = () => {
        if (!bookings.length) {
            alert("No bookings to export.");
            return;
        }

        const headers = [
            "Booking ID", "Transaction ID", "Venue Name", "Owner Name",
            "Resource", "Start Date", "End Date",
            "Gross Amount", "Net Amount (90%)", "Commission (10%)",
            "Settlement Status", "Booking Status"
        ];

        const csvRows = [
            headers.join(','), // Header row
            ...bookings.map(b => {
                const row = [
                    b.id || '',
                    b.transactionId || '',
                    `"${(b.venueName || '').replace(/"/g, '""')}"`, // Escape quotes
                    `"${(b.ownerName || '').replace(/"/g, '""')}"`,
                    `"${(b.cabinId ? `Cabin ${b.cabinNumber}` : `Housing #${b.accommodationId}`).replace(/"/g, '""')}"`,
                    b.startDate ? new Date(b.startDate).toLocaleDateString() : '',
                    b.endDate ? new Date(b.endDate).toLocaleDateString() : '',
                    b.amount || 0,
                    Math.round((b.amount || 0) * 0.9),
                    Math.round((b.amount || 0) * 0.1),
                    b.settlementStatus || 'NOT_SETTLED',
                    b.status || ''
                ];
                return row.join(',');
            })
        ];

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', `bookings_report_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const totalRevenue = bookings.reduce((sum, b) => sum + (b.amount || 0), 0);
    const pendingSettlement = bookings.reduce((sum, b) => (!b.settlementStatus || b.settlementStatus === 'NOT_SETTLED') ? sum + (b.amount * 0.9) : sum, 0);

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Booking Console</h2>
                    <p className="text-gray-500">Monitor all reservation activities, venue attribution, and settlements.</p>
                </div>
                <Button variant="outline" onClick={downloadCSV}>
                    <ExternalLink className="w-4 h-4 mr-2" /> Export CSV
                </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Total Revenue (Gross)</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">₹{totalRevenue.toLocaleString()}</p>
                    <p className="text-xs text-indigo-600 mt-1">Lifetime Volume</p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Pending Payouts</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">₹{pendingSettlement.toLocaleString()}</p>
                    <p className="text-xs text-orange-600 mt-1">To Owners</p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Settled</h4>
                    {/* Placeholder for now */}
                    <p className="text-3xl font-bold text-gray-900 mt-2">₹0</p>
                    <p className="text-xs text-green-600 mt-1">Paid Out</p>
                </Card>
                <Card className="p-6">
                    <h4 className="text-sm font-medium text-gray-500 uppercase">Active Bookings</h4>
                    <p className="text-3xl font-bold text-gray-900 mt-2">
                        {bookings.filter(b => b.status === "ACTIVE").length}
                    </p>
                    <p className="text-xs text-blue-600 mt-1">Ongoing</p>
                </Card>
            </div>

            <Card className="p-0 overflow-hidden border border-gray-200">
                <div className="p-4 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
                    <h3 className="font-semibold text-gray-700">All Reservations</h3>
                    <div className="flex gap-2">
                        <input placeholder="Filter by Venue..." className="px-3 py-1 border rounded text-sm" />
                        <input placeholder="Filter by Owner..." className="px-3 py-1 border rounded text-sm" />
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-gray-500">
                        <thead className="bg-white text-xs uppercase text-gray-700 font-semibold border-b">
                            <tr>
                                <th className="px-6 py-4">Booking ID</th>
                                <th className="px-6 py-4">Venue & Owner</th>
                                <th className="px-6 py-4">Resource</th>
                                <th className="px-6 py-4">Date Range</th>
                                <th className="px-6 py-4">Financials</th>
                                <th className="px-6 py-4">Settlement</th>
                                <th className="px-6 py-4">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {loading ? (
                                <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-400">Loading bookings...</td></tr>
                            ) : bookings.length > 0 ? bookings.map(b => (
                                <tr key={b.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4">
                                        <div className="font-mono text-xs">{b.id.slice(0, 8)}...</div>
                                        <div className="text-xs text-gray-400 mt-1">{b.transactionId ? 'Txn: ' + b.transactionId.slice(0, 8) : 'No Txn'}</div>
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
                                        <div className="whitespace-nowrap">{b.startDate ? new Date(b.startDate).toLocaleDateString() : 'N/A'}</div>
                                        <div className="text-gray-400">to {b.endDate ? new Date(b.endDate).toLocaleDateString() : 'N/A'}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="font-bold text-gray-900">₹{b.amount}</div>
                                        <div className="text-xs text-gray-500 flex justify-between w-24 mt-1">
                                            <span>Net:</span>
                                            <span className="font-medium text-green-600">₹{Math.round(b.amount * 0.9)}</span>
                                        </div>
                                        <div className="text-[10px] text-gray-400">Comm: ₹{Math.round(b.amount * 0.1)}</div>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={b.settlementStatus === "SETTLED" ? "success" : b.settlementStatus === "ON_HOLD" ? "error" : "warning"}>
                                            {b.settlementStatus || 'NOT_SETTLED'}
                                        </Badge>
                                    </td>
                                    <td className="px-6 py-4">
                                        <Badge variant={b.status === "ACTIVE" ? "success" : b.status === "CANCELLED" ? "error" : "warning"}>
                                            {b.status}
                                        </Badge>
                                    </td>
                                </tr>
                            )) : (
                                <tr><td colSpan={7} className="px-6 py-8 text-center bg-gray-50/50">No bookings found.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </Card>
        </div>
    );
};
