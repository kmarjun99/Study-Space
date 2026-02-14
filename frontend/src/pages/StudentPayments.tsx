import React, { useMemo, useState } from 'react';
import { AppState, User } from '../types';
import { Card, Badge, Button } from '../components/UI';
import { Download, CreditCard, TrendingUp, Calendar, Search, Loader2 } from 'lucide-react';
import { paymentService } from '../services/paymentService';

interface StudentPaymentsProps {
  state: AppState;
  user: User;
}

export const StudentPayments: React.FC<StudentPaymentsProps> = ({ state, user }) => {
  // Loading state for invoice download
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  // Derive payments from bookings
  const payments = useMemo(() => {
    return state.bookings
      .filter(b => b.userId === user.id)
      .sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime());
  }, [state.bookings, user.id]);

  const totalSpent = payments
    .filter(p => p.paymentStatus === 'PAID')
    .reduce((acc, curr) => acc + curr.amount, 0);

  const lastPayment = payments.find(p => p.paymentStatus === 'PAID');

  // Real invoice download function
  const handleDownloadInvoice = async (bookingId: string) => {
    setDownloadingId(bookingId);
    try {
      await paymentService.downloadInvoice(bookingId);
    } catch (error: any) {
      alert(error.message || 'Failed to download invoice. Please try again.');
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Payment History</h1>
          <p className="text-gray-500">View and download your subscription invoices.</p>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6 flex items-center space-x-4 bg-gradient-to-br from-indigo-500 to-indigo-600 text-white border-none shadow-md">
          <div className="p-3 bg-white/20 rounded-full backdrop-blur-sm">
            <CreditCard className="h-6 w-6 text-white" />
          </div>
          <div>
            <p className="text-indigo-100 text-sm font-medium">Total Spent</p>
            <p className="text-2xl font-bold">₹{totalSpent.toLocaleString()}</p>
          </div>
        </Card>

        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-green-100 text-green-600 rounded-full">
            <TrendingUp className="h-6 w-6" />
          </div>
          <div>
            <p className="text-gray-500 text-sm font-medium">Last Payment</p>
            <p className="text-2xl font-bold text-gray-900">
              {lastPayment ? `₹${lastPayment.amount.toLocaleString()}` : '₹0'}
            </p>
            {lastPayment && (
              <p className="text-xs text-gray-400">{lastPayment.startDate}</p>
            )}
          </div>
        </Card>

        <Card className="p-6 flex items-center space-x-4">
          <div className="p-3 bg-blue-100 text-blue-600 rounded-full">
            <Calendar className="h-6 w-6" />
          </div>
          <div>
            <p className="text-gray-500 text-sm font-medium">Total Transactions</p>
            <p className="text-2xl font-bold text-gray-900">{payments.length}</p>
          </div>
        </Card>
      </div>

      {/* Transactions Table */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b border-gray-100 bg-gray-50/50 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h3 className="font-semibold text-gray-900">Recent Transactions</h3>
          <div className="relative">
            <Search className="h-4 w-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search transaction ID..."
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-full sm:w-64"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Transaction ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Invoice</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {payments.length > 0 ? (
                payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {payment.startDate}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">Monthly Subscription</div>
                      <div className="text-xs text-gray-500">Cabin {payment.cabinNumber}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
                      {payment.transactionId}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      ₹{payment.amount.toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={payment.paymentStatus === 'PAID' ? 'success' : payment.paymentStatus === 'REFUNDED' ? 'warning' : 'error'}>
                        {payment.paymentStatus}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      {payment.paymentStatus === 'PAID' ? (
                        <button
                          onClick={() => handleDownloadInvoice(payment.id)}
                          disabled={downloadingId === payment.id}
                          className="text-indigo-600 hover:text-indigo-900 inline-flex items-center disabled:opacity-50 disabled:cursor-wait"
                        >
                          {downloadingId === payment.id ? (
                            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                          ) : (
                            <Download className="h-4 w-4 mr-1" />
                          )}
                          {downloadingId === payment.id ? 'Generating...' : 'PDF'}
                        </button>
                      ) : (
                        <span className="text-gray-400 text-xs">N/A</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-6 py-10 text-center text-sm text-gray-500">
                    <div className="flex flex-col items-center justify-center">
                      <CreditCard className="h-8 w-8 text-gray-300 mb-2" />
                      <p>No payment history available.</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};