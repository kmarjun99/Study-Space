
import React from 'react';
import { Card, Button } from '../components/UI';
import { ExternalLink, TrendingUp, Users, Building2, Calendar } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { User, ReadingRoom, Booking } from '../types';

interface SuperAdminAnalyticsViewProps {
    users: User[];
    readingRooms: ReadingRoom[];
    bookings: Booking[];
}

export const SuperAdminAnalyticsView: React.FC<SuperAdminAnalyticsViewProps> = ({ users, readingRooms, bookings }) => {
    // Data Prep
    const totalUsers = users.length;
    const totalVenues = readingRooms.length;
    const totalBookings = bookings.length;

    // User Distribution
    const students = users.filter((u: any) => u.role === 'STUDENT').length;
    const admins = users.filter((u: any) => u.role === 'ADMIN').length;
    const superAdmins = users.filter((u: any) => u.role === 'SUPER_ADMIN').length;

    const userPieData = [
        { name: 'Students', value: students, color: '#4F46E5' }, // Indigo
        { name: 'Venue Owners', value: admins, color: '#10B981' }, // Emerald
        { name: 'Staff', value: superAdmins, color: '#F59E0B' }, // Amber
    ];

    // Capacity Utilization (Mock logic for demonstration until we have granular capacity data in state)
    const estCapacity = totalVenues * 50;
    const activeUtil = bookings.filter((b: any) => b.status === 'ACTIVE').length;
    const utilizationRate = estCapacity > 0 ? Math.round((activeUtil / estCapacity) * 100) : 0;

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Analytics Studio</h2>
                    <p className="text-gray-500">Deep dive into platform performance and user behavior.</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline">Last 30 Days</Button>
                    <Button><ExternalLink className="w-4 h-4 mr-2" /> Export Data</Button>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Total Users</h4>
                        <Users className="w-5 h-5 text-indigo-500" />
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{totalUsers}</p>
                    <p className="text-xs text-green-600 mt-1 flex items-center"><TrendingUp className="w-3 h-3 mr-1" /> +12% this month</p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Venues Active</h4>
                        <Building2 className="w-5 h-5 text-emerald-500" />
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{totalVenues}</p>
                    <p className="text-xs text-green-600 mt-1 flex items-center"><TrendingUp className="w-3 h-3 mr-1" /> +3 added recently</p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Total Bookings</h4>
                        <Calendar className="w-5 h-5 text-blue-500" />
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{totalBookings}</p>
                    <p className="text-xs text-gray-500 mt-1">Lifetime Volume</p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Utilization</h4>
                        <div className="w-5 h-5 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-bold">%</div>
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{utilizationRate}%</p>
                    <p className="text-xs text-gray-500 mt-1">Avg Occupancy</p>
                </Card>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6 min-h-[400px]">
                    <h3 className="text-lg font-bold text-gray-900 mb-6">User Distribution</h3>
                    <div className="h-80 w-full relative">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={userPieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={80}
                                    outerRadius={120}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {userPieData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                        {/* Legend Overlay */}
                        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none">
                            <p className="text-3xl font-bold text-gray-900">{totalUsers}</p>
                            <p className="text-xs text-gray-500 uppercase">Total Users</p>
                        </div>
                    </div>
                    <div className="flex justify-center gap-6 mt-4">
                        {userPieData.map((d) => (
                            <div key={d.name} className="flex items-center gap-2">
                                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: d.color }}></div>
                                <span className="text-sm text-gray-600">{d.name}</span>
                            </div>
                        ))}
                    </div>
                </Card>

                <Card className="p-6 min-h-[400px]">
                    <h3 className="text-lg font-bold text-gray-900 mb-6">Growth (New Venues)</h3>
                    <div className="h-80 w-full">
                        {/* Mock Bar Chart for Visual */}
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={[
                                { name: 'Jan', val: 2 },
                                { name: 'Feb', val: 5 },
                                { name: 'Mar', val: 3 },
                                { name: 'Apr', val: 8 },
                                { name: 'May', val: 12 },
                                { name: 'Jun', val: 7 }
                            ]}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#9CA3AF' }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9CA3AF' }} />
                                <Tooltip cursor={{ fill: '#F9FAFB' }} contentStyle={{ borderRadius: '8px', border: 'none' }} />
                                <Bar dataKey="val" fill="#10B981" radius={[4, 4, 0, 0]} barSize={30} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </Card>
            </div>
        </div>
    );
};
