
import React, { useMemo, useState, useEffect } from 'react';
import { AppState } from '../types';
import { Card, Button, Badge } from '../components/UI';
import {
   BarChart,
   Bar,
   XAxis,
   YAxis,
   CartesianGrid,
   Tooltip,
   ResponsiveContainer,
   AreaChart,
   Area
} from 'recharts';
import {
   Download,
   TrendingUp,
   DollarSign,
   CreditCard,
   Calendar,
   Search,
   Filter,
   FileText,
   MoreHorizontal,
   ArrowUp,
   RefreshCw
} from 'lucide-react';
import { paymentService } from '../services/paymentService';

interface AdminFinancialsProps {
   state: AppState;
}

interface PaymentTransaction {
   id: string;
   booking_id: string;
   user_id: string;
   user_name: string;
   type: 'INITIAL' | 'EXTENSION' | 'REFUND';
   amount: number;
   date: string;
   venue_name: string;
   cabin_number: string;
   transaction_id: string;
   description: string;
   method: string;
}

export const AdminFinancials: React.FC<AdminFinancialsProps> = ({ state }) => {
   const [searchTerm, setSearchTerm] = useState('');
   const [statusFilter, setStatusFilter] = useState<'ALL' | 'INITIAL' | 'EXTENSION'>('ALL');
   const [paymentHistory, setPaymentHistory] = useState<PaymentTransaction[]>([]);
   const [isLoading, setIsLoading] = useState(true);

   // --- Fetch Payment History from API ---
   useEffect(() => {
      const fetchPayments = async () => {
         try {
            setIsLoading(true);
            const data = await paymentService.getOwnerPaymentHistory();
            setPaymentHistory(data.payments || []);
         } catch (error) {
            console.error('Failed to fetch payment history:', error);
            // Fallback to booking-based transactions
            setPaymentHistory([]);
         } finally {
            setIsLoading(false);
         }
      };
      fetchPayments();
   }, []);

   // --- Data Processing ---

   // 1. Identify Admin's Scope
   const myRoom = (state.readingRooms || []).find(r => r.ownerId === state.currentUser?.id);
   const myCabins = myRoom ? (state.cabins || []).filter(c => c.readingRoomId === myRoom.id) : [];
   const myCabinIds = new Set(myCabins.map(c => c.id));


   // 2. Use API payment history if available, otherwise fallback to bookings
   const transactions = useMemo(() => {
      if (paymentHistory.length > 0) {
         return paymentHistory;
      }
      // Fallback to booking-based transactions
      const allBookings = state.bookings || [];
      const allUsers = state.users || [];
      const venueBookings = allBookings.filter(b => myCabinIds.has(b.cabinId));
      return venueBookings.map(b => {
         const student = allUsers.find(u => u.id === b.userId);
         return {
            id: b.id,
            booking_id: b.id,
            user_id: b.userId,
            user_name: student ? student.name : 'Unknown User',
            type: 'INITIAL' as const,
            amount: b.amount,
            date: b.startDate,
            venue_name: myRoom?.name || 'Unknown',
            cabin_number: b.cabinNumber || 'N/A',
            transaction_id: b.transactionId || '',
            description: 'Initial Booking',
            method: 'UPI',
            paymentStatus: b.paymentStatus || 'PAID',
            startDate: b.startDate
         };
      });
   }, [paymentHistory, state.bookings, state.users, myCabinIds, myRoom]);

   // 3. Apply UI Filters
   const filteredTransactions = transactions.filter(t => {
      const matchesSearch =
         t.transaction_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
         t.user_name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'ALL' || t.type === statusFilter;
      return matchesSearch && matchesStatus;
   }).sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

   // 5. Calculate Metrics
   const totalRevenue = transactions
      .filter(t => t.paymentStatus === 'PAID')
      .reduce((sum, t) => sum + t.amount, 0);

   const currentMonth = new Date().getMonth();
   const currentYear = new Date().getFullYear();

   const monthlyRevenue = transactions
      .filter(t => {
         const d = new Date(t.startDate);
         return t.paymentStatus === 'PAID' && d.getMonth() === currentMonth && d.getFullYear() === currentYear;
      })
      .reduce((sum, t) => sum + t.amount, 0);

   const pendingAmount = transactions
      .filter(t => t.paymentStatus === 'PENDING')
      .reduce((sum, t) => sum + t.amount, 0);

   // 6. Prepare Chart Data (Last 6 Months)
   const chartData = useMemo(() => {
      const months = [];
      for (let i = 5; i >= 0; i--) {
         const d = new Date();
         d.setMonth(d.getMonth() - i);
         const monthKey = d.toLocaleString('default', { month: 'short' });
         const year = d.getFullYear();
         const monthIdx = d.getMonth();

         const total = transactions
            .filter(t => {
               const tDate = new Date(t.startDate);
               return t.paymentStatus === 'PAID' && tDate.getMonth() === monthIdx && tDate.getFullYear() === year;
            })
            .reduce((sum, t) => sum + t.amount, 0);

         months.push({ name: monthKey, revenue: total });
      }
      return months;
   }, [transactions]);

   const handleExport = () => {
      try {
         // Prepare CSV data
         const csvHeaders = [
            'Date',
            'Transaction ID',
            'Student Name',
            'Type',
            'Cabin',
            'Amount',
            'Method',
            'Description'
         ];

         const csvRows = filteredTransactions.map(t => [
            t.date,
            t.transaction_id || t.id,
            t.user_name,
            t.type,
            t.cabin_number,
            `₹${t.amount}`,
            t.method || 'N/A',
            t.description || ''
         ]);

         // Create CSV content
         const csvContent = [
            csvHeaders.join(','),
            ...csvRows.map(row => row.map(cell => {
               // Escape commas and quotes in cell content
               const cellStr = String(cell || '');
               if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
                  return `"${cellStr.replace(/"/g, '""')}"`;
               }
               return cellStr;
            }).join(','))
         ].join('\n');

         // Create blob and download
         const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
         const link = document.createElement('a');
         const url = URL.createObjectURL(blob);
         
         const today = new Date().toISOString().split('T')[0];
         const filename = `${myRoom?.name || 'venue'}_financial_report_${today}.csv`;
         
         link.setAttribute('href', url);
         link.setAttribute('download', filename);
         link.style.visibility = 'hidden';
         document.body.appendChild(link);
         link.click();
         document.body.removeChild(link);
         URL.revokeObjectURL(url);
      } catch (error) {
         console.error('Failed to export CSV:', error);
         alert('Failed to export report. Please try again.');
      }
   };

   if (!myRoom) {
      return (
         <div className="flex flex-col items-center justify-center h-96 text-center px-4">
            <div className="bg-gray-100 p-4 rounded-full mb-4">
               <DollarSign className="h-8 w-8 text-gray-400" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">Setup Required</h2>
            <p className="text-gray-500 mt-2">Create a venue to start tracking financials.</p>
         </div>
      );
   }

   return (
      <div className="space-y-6 max-w-7xl mx-auto pb-20 md:pb-0">
         {/* Header */}
         <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
               <h1 className="text-2xl font-bold text-gray-900">Financial Reports</h1>
               <p className="text-gray-500 text-sm">Track revenue stream and manage invoices for <span className="font-semibold text-indigo-600">{myRoom.name}</span>.</p>
            </div>
            <Button variant="outline" onClick={handleExport} className="w-full sm:w-auto justify-center">
               <Download className="w-4 h-4 mr-2" /> Export CSV
            </Button>
         </div>

         {/* Metrics Grid */}
         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-5 border-l-4 border-indigo-500 shadow-sm hover:shadow-md transition-shadow">
               <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Total Revenue</p>
                  <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600">
                     <DollarSign className="w-5 h-5" />
                  </div>
               </div>
               <p className="text-2xl font-bold text-gray-900">₹{totalRevenue.toLocaleString()}</p>
               <p className="text-xs text-green-600 flex items-center mt-1">
                  <TrendingUp className="w-3 h-3 mr-1" /> +12.5% from last year
               </p>
            </Card>

            <Card className="p-5 border-l-4 border-green-500 shadow-sm hover:shadow-md transition-shadow">
               <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">This Month</p>
                  <div className="p-2 bg-green-50 rounded-lg text-green-600">
                     <Calendar className="w-5 h-5" />
                  </div>
               </div>
               <p className="text-2xl font-bold text-gray-900">₹{monthlyRevenue.toLocaleString()}</p>
               <p className="text-xs text-gray-400 mt-1">Current billing cycle</p>
            </Card>

            <Card className="p-5 border-l-4 border-orange-400 shadow-sm hover:shadow-md transition-shadow">
               <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Pending</p>
                  <div className="p-2 bg-orange-50 rounded-lg text-orange-500">
                     <CreditCard className="w-5 h-5" />
                  </div>
               </div>
               <p className="text-2xl font-bold text-gray-900">₹{pendingAmount.toLocaleString()}</p>
               <p className="text-xs text-orange-600 mt-1">Unsettled invoices</p>
            </Card>

            <Card className="p-5 border-l-4 border-blue-500 shadow-sm hover:shadow-md transition-shadow">
               <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-gray-500">Avg. Transaction</p>
                  <div className="p-2 bg-blue-50 rounded-lg text-blue-500">
                     <TrendingUp className="w-5 h-5" />
                  </div>
               </div>
               <p className="text-2xl font-bold text-gray-900">
                  ₹{transactions.length > 0 ? Math.round(totalRevenue / transactions.length).toLocaleString() : 0}
               </p>
               <p className="text-xs text-gray-400 mt-1">Per booking</p>
            </Card>
         </div>

         {/* Chart Section */}
         <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-3">
               <Card className="p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-6">Revenue Trend</h3>
                  <div className="h-72 w-full min-w-0">
                     <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                           <defs>
                              <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                                 <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.2} />
                                 <stop offset="95%" stopColor="#4F46E5" stopOpacity={0} />
                              </linearGradient>
                           </defs>
                           <XAxis
                              dataKey="name"
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: '#9CA3AF', fontSize: 12 }}
                              dy={10}
                           />
                           <YAxis
                              axisLine={false}
                              tickLine={false}
                              tick={{ fill: '#9CA3AF', fontSize: 12 }}
                              tickFormatter={(val) => `₹${val}`}
                           />
                           <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#F3F4F6" />
                           <Tooltip
                              contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                              formatter={(value: number) => [`₹${value}`, 'Revenue']}
                           />
                           <Area type="monotone" dataKey="revenue" stroke="#4F46E5" strokeWidth={2} fillOpacity={1} fill="url(#colorRevenue)" />
                        </AreaChart>
                     </ResponsiveContainer>
                  </div>
               </Card>
            </div>
         </div>

         {/* Transactions Section */}
         <Card className="overflow-hidden">
            {/* Filter Header */}
            <div className="p-4 border-b border-gray-100 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 bg-gray-50">
               <h3 className="font-bold text-gray-900 flex items-center">
                  <FileText className="w-4 h-4 mr-2 text-gray-500" /> Recent Transactions
               </h3>

               <div className="flex flex-col sm:flex-row gap-3 w-full lg:w-auto">
                  {/* Type Filter */}
                  <div className="flex bg-white rounded-md shadow-sm w-full sm:w-auto border border-gray-200 sm:border-none">
                     {(['ALL', 'INITIAL', 'EXTENSION'] as const).map((s) => (
                        <button
                           key={s}
                           onClick={() => setStatusFilter(s)}
                           className={`flex-1 sm:flex-none px-3 py-2 text-xs font-medium border-r last:border-r-0 border-gray-200 first:rounded-l-md last:rounded-r-md transition-colors whitespace-nowrap ${statusFilter === s
                              ? 'bg-indigo-50 text-indigo-700'
                              : 'text-gray-600 hover:bg-gray-50'
                              }`}
                        >
                           {s}
                        </button>
                     ))}
                  </div>

                  {/* Search */}
                  <div className="relative w-full sm:w-64">
                     <Search className="h-4 w-4 text-gray-400 absolute left-3 top-2.5" />
                     <input
                        type="text"
                        placeholder="Search ID or Student..."
                        className="pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500 focus:outline-none w-full"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                     />
                  </div>
               </div>
            </div>

            {/* Desktop View: Table */}
            <div className="hidden md:block overflow-x-auto">
               <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-white">
                     <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Student</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                     </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                     {filteredTransactions.length > 0 ? (
                        filteredTransactions.map((t) => (
                           <tr key={t.id} className="hover:bg-gray-50">
                              <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                 {new Date(t.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                 <div className="flex items-center">
                                    <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-xs mr-3">
                                       {t.user_name.charAt(0)}
                                    </div>
                                    <span className="text-sm font-medium text-gray-900">{t.user_name}</span>
                                 </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                 <div className="text-sm text-gray-900">Cabin {t.cabin_number}</div>
                                 <div className="text-xs text-gray-500">{t.description}</div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap">
                                 <Badge variant={t.type === 'EXTENSION' ? 'warning' : t.type === 'REFUND' ? 'error' : 'success'}>
                                    {t.type === 'EXTENSION' ? '↑ Extension' : t.type === 'REFUND' ? 'Refund' : 'Initial'}
                                 </Badge>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-900">
                                 ₹{t.amount.toLocaleString()}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                                 <button className="text-indigo-600 hover:text-indigo-900 font-medium">View Invoice</button>
                              </td>
                           </tr>
                        ))
                     ) : (
                        <tr>
                           <td colSpan={6} className="px-6 py-10 text-center text-gray-500">
                              No transactions found matching your filters.
                           </td>
                        </tr>
                     )}
                  </tbody>
               </table>
            </div>

            {/* Mobile View: Cards */}
            <div className="md:hidden divide-y divide-gray-100">
               {filteredTransactions.length > 0 ? (
                  filteredTransactions.map((t) => (
                     <div key={t.id} className="p-4 bg-white space-y-3">
                        <div className="flex justify-between items-start">
                           <div className="flex items-center">
                              <div className="h-9 w-9 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-700 font-bold text-xs mr-3">
                                 {(t.user_name || 'U').charAt(0)}
                              </div>
                              <div>
                                 <p className="text-sm font-bold text-gray-900">{t.user_name || 'Unknown'}</p>
                                 <p className="text-xs text-gray-500">{t.startDate || t.date}</p>
                              </div>
                           </div>
                           <Badge variant={t.paymentStatus === 'PAID' ? 'success' : t.paymentStatus === 'REFUNDED' ? 'warning' : 'error'}>
                              {t.paymentStatus || 'PAID'}
                           </Badge>
                        </div>

                        <div className="grid grid-cols-2 gap-4 pl-12 pt-1">
                           <div>
                              <span className="text-xs text-gray-500 block mb-0.5">Amount</span>
                              <span className="font-medium text-gray-900">₹{(t.amount || 0).toLocaleString()}</span>
                           </div>
                           <div>
                              <span className="text-xs text-gray-500 block mb-0.5">Cabin</span>
                              <span className="font-medium text-gray-900">{t.cabin_number || 'N/A'}</span>
                           </div>
                        </div>

                        <div className="pl-12 pt-2 flex items-center justify-between border-t border-gray-50 mt-2">
                           <span className="text-xs font-mono text-gray-400 truncate max-w-[120px]">{t.transaction_id || ''}</span>
                           <button className="text-indigo-600 text-sm font-medium hover:bg-indigo-50 px-2 py-1 rounded-md transition-colors flex items-center mt-1">
                              View Invoice
                           </button>
                        </div>
                     </div>
                  ))
               ) : (
                  <div className="p-8 text-center text-gray-500 text-sm">
                     No transactions found.
                  </div>
               )}
            </div>
         </Card>
      </div>
   );
};
