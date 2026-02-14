
import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../components/UI';
import { DollarSign, RotateCcw, ExternalLink, Activity } from 'lucide-react';
import { bookingService } from '../services/bookingService';
import { paymentService, RefundAdmin } from '../services/paymentService';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const SuperAdminFinanceView = () => {
    const [activeTab, setActiveTab] = useState<'overview' | 'refunds'>('overview');
    const [bookings, setBookings] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    // Refunds state
    const [refunds, setRefunds] = useState<RefundAdmin[]>([]);
    const [refundsLoading, setRefundsLoading] = useState(false);
    const [refundFilter, setRefundFilter] = useState<string>('');
    const [processingId, setProcessingId] = useState<string | null>(null);

    useEffect(() => {
        loadFinancials();
    }, []);

    useEffect(() => {
        if (activeTab === 'refunds') {
            loadRefunds();
        }
    }, [activeTab, refundFilter]);

    const loadFinancials = async () => {
        setLoading(true);
        try {
            const transactionData = await bookingService.getMyBookings();
            setBookings(transactionData);
        } catch (err) {
            console.error("Failed to load financials", err);
        } finally {
            setLoading(false);
        }
    };

    const loadRefunds = async () => {
        setRefundsLoading(true);
        try {
            const data = await paymentService.getAllRefunds(refundFilter || undefined);
            setRefunds(data);
        } catch (err) {
            console.error("Failed to load refunds", err);
        } finally {
            setRefundsLoading(false);
        }
    };

    const handleRefundAction = async (refundId: string, newStatus: string) => {
        const notes = newStatus === 'REJECTED' ? prompt('Enter rejection reason:') : undefined;
        setProcessingId(refundId);
        try {
            await paymentService.updateRefundStatus(refundId, newStatus, notes || undefined);
            alert(`Refund status updated to ${newStatus}`);
            loadRefunds();
        } catch (err) {
            console.error("Failed to update refund", err);
            alert("Failed to update refund status");
        } finally {
            setProcessingId(null);
        }
    };

    const handleExportReport = () => {
        // Prepare CSV data based on active tab
        let csvContent = '';
        let filename = '';

        if (activeTab === 'overview') {
            // Export financial overview
            filename = `financial_report_${new Date().toISOString().split('T')[0]}.csv`;
            csvContent = 'Date,Booking ID,User,Amount,Status\n';

            bookings.forEach(booking => {
                const date = booking.startDate || 'N/A';
                const id = booking.id || 'N/A';
                const user = booking.userId || 'N/A';
                const amount = booking.amount || 0;
                const status = booking.status || 'N/A';
                csvContent += `${date},${id},${user},${amount},${status}\n`;
            });
        } else {
            // Export refunds
            filename = `refunds_report_${new Date().toISOString().split('T')[0]}.csv`;
            csvContent = 'Refund ID,Booking ID,User,Amount,Status,Reason,Requested Date,Processed Date\n';

            refunds.forEach(refund => {
                const id = refund.id || 'N/A';
                const bookingId = refund.booking_id || 'N/A';
                const userId = refund.user_id || 'N/A';
                const amount = refund.amount || 0;
                const status = refund.status || 'N/A';
                const reason = (refund.reason || 'N/A').replace(/,/g, ';'); // Replace commas to avoid CSV issues
                const requestedDate = refund.requested_at || 'N/A';
                const processedDate = refund.processed_at || 'N/A';
                csvContent += `${id},${bookingId},${userId},${amount},${status},"${reason}",${requestedDate},${processedDate}\n`;
            });
        }

        // Create blob and download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // --- Metrics Calculation ---
    const totalVolume = bookings.reduce((sum, b) => sum + (b.amount || 0), 0);
    const platformRevenue = totalVolume * 0.10;
    // const payoutObligation = totalVolume * 0.90; // Unused variable

    // Refund stats
    const pendingRefunds = refunds.filter(r => ['REQUESTED', 'UNDER_REVIEW'].includes(r.status)).length;
    const processedRefunds = refunds.filter(r => r.status === 'PROCESSED').length;
    const totalRefundAmount = refunds.filter(r => r.status === 'PROCESSED').reduce((sum, r) => sum + r.amount, 0);

    // --- Chart Data ---
    const chartDataMap: { [key: string]: number } = {};
    bookings.forEach(b => {
        if (!b.startDate) return;
        const dateKey = b.startDate.substring(0, 10);
        chartDataMap[dateKey] = (chartDataMap[dateKey] || 0) + (b.amount || 0);
    });
    const data = Object.keys(chartDataMap).sort().map(date => ({
        name: date,
        revenue: chartDataMap[date]
    }));

    const statusColors: Record<string, string> = {
        REQUESTED: 'bg-yellow-100 text-yellow-700',
        UNDER_REVIEW: 'bg-blue-100 text-blue-700',
        APPROVED: 'bg-green-100 text-green-700',
        REJECTED: 'bg-red-100 text-red-700',
        PROCESSED: 'bg-emerald-100 text-emerald-700',
        FAILED: 'bg-red-100 text-red-700'
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Finance & Refunds</h2>
                    <p className="text-gray-500">Revenue capture, payouts, and refund management.</p>
                </div>
                <Button variant="outline" onClick={handleExportReport}><ExternalLink className="w-4 h-4 mr-2" /> Export Report</Button>
            </div>

            {/* Tabs */}
            <div className="flex gap-2 border-b border-gray-200 pb-4">
                <Button variant={activeTab === 'overview' ? 'primary' : 'outline'} onClick={() => setActiveTab('overview')}>
                    <DollarSign className="w-4 h-4 mr-2" /> Overview
                </Button>
                <Button variant={activeTab === 'refunds' ? 'primary' : 'outline'} onClick={() => setActiveTab('refunds')}>
                    <RotateCcw className="w-4 h-4 mr-2" /> Refunds
                    {pendingRefunds > 0 && <Badge variant="warning" className="ml-2">{pendingRefunds}</Badge>}
                </Button>
            </div>

            {activeTab === 'overview' && (
                <>
                    {/* Top Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <Card className="p-6 border-t-4 border-t-indigo-500 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Gross Volume (GMV)</p>
                                    <h3 className="text-3xl font-extrabold text-gray-900 mt-2">₹{totalVolume.toLocaleString()}</h3>
                                </div>
                                <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                                    <DollarSign className="w-6 h-6" />
                                </div>
                            </div>
                        </Card>
                        <Card className="p-6 border-t-4 border-t-green-500 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Net Revenue (Est.)</p>
                                    <h3 className="text-3xl font-extrabold text-gray-900 mt-2">₹{platformRevenue.toLocaleString()}</h3>
                                </div>
                                <div className="p-2 bg-green-50 rounded-lg text-green-600">
                                    <Activity className="w-6 h-6" />
                                </div>
                            </div>
                        </Card>
                        <Card className="p-6 border-t-4 border-t-orange-500 shadow-sm hover:shadow-md transition-shadow">
                            <div className="flex justify-between items-start">
                                <div>
                                    <p className="text-sm font-medium text-gray-500 uppercase tracking-wider">Refunds Processed</p>
                                    <h3 className="text-3xl font-extrabold text-gray-900 mt-2">₹{totalRefundAmount.toLocaleString()}</h3>
                                </div>
                                <div className="p-2 bg-orange-50 rounded-lg text-orange-600">
                                    <RotateCcw className="w-6 h-6" />
                                </div>
                            </div>
                            <div className="mt-4 text-sm text-gray-500">{processedRefunds} refunds completed</div>
                        </Card>
                    </div>

                    {/* Revenue Chart */}
                    <Card className="p-6">
                        <h3 className="text-lg font-bold text-gray-900 mb-6">Revenue Trend</h3>
                        <div className="h-80 w-full">
                            {data.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6B7280', fontSize: 12 }} />
                                        <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6B7280', fontSize: 12 }} tickFormatter={(value) => `₹${value}`} />
                                        <Tooltip cursor={{ fill: '#F3F4F6' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} />
                                        <Bar dataKey="revenue" fill="#4F46E5" radius={[4, 4, 0, 0]} barSize={40} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-lg">
                                    <Activity className="w-10 h-10 mb-2 opacity-20" />
                                    <p>No transaction data available yet</p>
                                </div>
                            )}
                        </div>
                    </Card>
                </>
            )}

            {activeTab === 'refunds' && (
                <div className="space-y-6">
                    {/* Refund Filters */}
                    <div className="flex gap-2 flex-wrap">
                        {['', 'REQUESTED', 'UNDER_REVIEW', 'APPROVED', 'PROCESSED', 'REJECTED'].map(status => (
                            <Button
                                key={status}
                                size="sm"
                                variant={refundFilter === status ? 'primary' : 'outline'}
                                onClick={() => setRefundFilter(status)}
                            >
                                {status || 'All'}
                            </Button>
                        ))}
                    </div>

                    {/* Refunds Table */}
                    <Card className="p-0 overflow-hidden">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-50 text-xs uppercase text-gray-700 font-semibold border-b">
                                <tr>
                                    <th className="px-6 py-4">User</th>
                                    <th className="px-6 py-4">Venue</th>
                                    <th className="px-6 py-4">Amount</th>
                                    <th className="px-6 py-4">Reason</th>
                                    <th className="px-6 py-4">Status</th>
                                    <th className="px-6 py-4">Requested</th>
                                    <th className="px-6 py-4 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {refundsLoading ? (
                                    <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-400">Loading refunds...</td></tr>
                                ) : refunds.length === 0 ? (
                                    <tr><td colSpan={7} className="px-6 py-8 text-center text-gray-400">No refund requests found.</td></tr>
                                ) : refunds.map(refund => (
                                    <tr key={refund.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4">
                                            <div className="font-medium text-gray-900">{refund.user_name}</div>
                                            <div className="text-xs text-gray-500">{refund.user_email}</div>
                                        </td>
                                        <td className="px-6 py-4 text-gray-900">{refund.venue_name}</td>
                                        <td className="px-6 py-4 font-bold text-indigo-600">₹{refund.amount.toLocaleString()}</td>
                                        <td className="px-6 py-4 text-gray-600 max-w-[150px] truncate" title={refund.reason_text || refund.reason}>
                                            {refund.reason_text || refund.reason.replace('_', ' ')}
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${statusColors[refund.status] || 'bg-gray-100 text-gray-700'}`}>
                                                {refund.status.replace('_', ' ')}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-gray-500">
                                            {new Date(refund.requested_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 text-right space-x-2">
                                            {refund.status === 'REQUESTED' && (
                                                <>
                                                    <Button size="sm" variant="outline" onClick={() => handleRefundAction(refund.id, 'UNDER_REVIEW')} disabled={processingId === refund.id}>
                                                        Review
                                                    </Button>
                                                </>
                                            )}
                                            {['REQUESTED', 'UNDER_REVIEW'].includes(refund.status) && (
                                                <>
                                                    <Button size="sm" variant="primary" onClick={() => handleRefundAction(refund.id, 'APPROVED')} disabled={processingId === refund.id}>
                                                        Approve
                                                    </Button>
                                                    <Button size="sm" variant="danger" onClick={() => handleRefundAction(refund.id, 'REJECTED')} disabled={processingId === refund.id}>
                                                        Reject
                                                    </Button>
                                                </>
                                            )}
                                            {refund.status === 'APPROVED' && (
                                                <Button size="sm" variant="primary" onClick={() => handleRefundAction(refund.id, 'PROCESSED')} disabled={processingId === refund.id}>
                                                    Mark Processed
                                                </Button>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Card>
                </div>
            )}
        </div>
    );
};
