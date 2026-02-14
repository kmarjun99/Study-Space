
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button } from '../components/UI';
import { Activity, MapPin, DollarSign } from 'lucide-react';
import { AppState, UserRole } from '../types';

interface SuperAdminDashboardHomeProps {
    state: AppState;
}

export const SuperAdminDashboardHome: React.FC<SuperAdminDashboardHomeProps> = ({ state }) => {
    const navigate = useNavigate();
    const globalRevenue = state.bookings.reduce((sum, b) => sum + b.amount, 0);

    const [activities] = useState([
        { id: 1, type: 'BOOKING', message: 'New booking at Central Library', time: 'Just now', status: 'success' },
        { id: 2, type: 'CHECKIN', message: 'Student verified at Study Nook', time: '2 mins ago', status: 'info' },
        { id: 3, type: 'ERROR', message: 'Payment failed for User #992', time: '5 mins ago', status: 'error' },
        { id: 4, type: 'REVIEW', message: 'New 5-star review for Sunrise PG', time: '12 mins ago', status: 'success' },
    ]);

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Mission Control</h1>
                    <p className="text-gray-500">Real-time platform health.</p>
                </div>
                <div className="text-sm text-gray-500">Last updated: Just now</div>
            </div>

            {/* Live Status Board */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* 1. Global Pulse */}
                <Card className="col-span-2 p-6">
                    <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                        <Activity className="w-5 h-5 mr-2 text-indigo-500" /> Platform Pulse
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-100">
                            <p className="text-xs text-indigo-600 uppercase font-bold tracking-wider">Live Users</p>
                            <p className="text-3xl font-extrabold text-indigo-900 mt-1">{state.users.length}</p>
                        </div>

                        <div className="p-4 bg-green-50 rounded-lg border border-green-100">
                            <p className="text-xs text-green-600 uppercase font-bold tracking-wider">Bookings / Hr</p>
                            <p className="text-3xl font-extrabold text-green-900 mt-1">
                                {/* Functional: Count Bookings in last 60 mins */}
                                {state.bookings.filter(b => {
                                    if (!b.createdAt) return false;
                                    const created = new Date(b.createdAt);
                                    const hourAgo = new Date(Date.now() - 60 * 60 * 1000);
                                    return created > hourAgo;
                                }).length}
                            </p>
                        </div>
                        <div className="p-4 bg-orange-50 rounded-lg border border-orange-100">
                            <p className="text-xs text-orange-600 uppercase font-bold tracking-wider">Pending KYC</p>
                            <p className="text-3xl font-extrabold text-orange-900 mt-1">
                                {/* Functional: Count ADMINs with PENDING status */}
                                {state.users.filter(u => u.role === UserRole.ADMIN && u.verificationStatus === 'PENDING').length}
                            </p>
                        </div>

                        <div className="p-4 bg-red-50 rounded-lg border border-red-100">
                            <p className="text-xs text-red-600 uppercase font-bold tracking-wider">Critical Issues</p>
                            <p className="text-3xl font-extrabold text-red-900 mt-1">
                                {state.notifications.filter(n => n.type === 'error').length}
                            </p>
                        </div>
                    </div>
                    <div className="h-64 border-2 border-dashed border-gray-200 rounded-xl bg-gray-50 flex flex-col items-center justify-center text-gray-400">
                        <MapPin className="w-12 h-12 mb-2 opacity-20" />
                        <p className="font-medium">Live City Heatmap Placeholder</p>
                        <p className="text-xs opacity-60">Visualizing demand hotspots in real-time</p>
                    </div>
                </Card>

                {/* 2. Live Activity Feed */}
                <Card className="p-0 overflow-hidden flex flex-col h-full bg-white border border-gray-200 shadow-sm">
                    <div className="p-4 border-b bg-gray-50/50 flex justify-between items-center">
                        <h3 className="font-bold text-gray-900 flex items-center gap-2">
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                            </span>
                            Live Feed
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto p-0">
                        {activities.map((act, i) => (
                            <div key={act.id} className={`p-4 border-b border-gray-50 hover:bg-gray-50 transition-colors flex gap-3 text-sm animate-in slide-in-from-right-2`} style={{ animationDelay: `${i * 100}ms` }}>
                                <div className={`w-2 h-2 mt-1.5 rounded-full flex-shrink-0 ${act.status === 'success' ? 'bg-green-500' :
                                    act.status === 'error' ? 'bg-red-500' : 'bg-blue-500'
                                    }`} />
                                <div>
                                    <p className="text-gray-900 font-medium leading-snug">{act.message}</p>
                                    <p className="text-xs text-gray-400 mt-1">{act.time}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            {/* Financial Reconciliation (Mini) */}
            <Card className="p-6 border-l-4 border-l-green-500 shadow-sm">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-gray-900 flex items-center gap-2">
                        <DollarSign className="w-5 h-5 text-green-600" />
                        Financial Overview
                    </h3>
                    <Button size="sm" variant="ghost" className="text-indigo-600 hover:bg-indigo-50" onClick={() => navigate('/super-admin/finance')}>View Full Report &rarr;</Button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 divide-y md:divide-y-0 md:divide-x divide-gray-100">
                    <div className="px-4">
                        <p className="text-sm text-gray-500 mb-1">Total Processed Vol.</p>
                        <p className="text-2xl font-bold tracking-tight text-gray-900">₹{globalRevenue.toLocaleString()}</p>
                        <p className="text-xs text-green-600 flex items-center mt-1">↑ 12% vs last month</p>
                    </div>
                    <div className="px-4 pt-4 md:pt-0">
                        <p className="text-sm text-gray-500 mb-1">Platform Revenue (Est)</p>
                        <p className="text-2xl font-bold tracking-tight text-indigo-600">₹{(globalRevenue * 0.1).toLocaleString()}</p>
                        <p className="text-xs text-gray-400 mt-1">Based on 10% commission</p>
                    </div>
                    <div className="px-4 pt-4 md:pt-0">
                        <p className="text-sm text-gray-500 mb-1">Pending Payouts</p>
                        <p className="text-2xl font-bold tracking-tight text-orange-600">₹45,200</p>
                        <p className="text-xs text-orange-600/80 mt-1">Due in 3 days</p>
                    </div>
                </div>
            </Card>
        </div>
    );
};
