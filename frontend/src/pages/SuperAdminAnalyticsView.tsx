
import React, { useEffect, useMemo, useState } from 'react';
import { Card, Button } from '../components/UI';
import { ExternalLink, Users, Building2, Calendar } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { User, ReadingRoom, Booking } from '../types';

interface SuperAdminAnalyticsViewProps {
    users: User[];
    readingRooms: ReadingRoom[];
    bookings: Booking[];
}

// Assumed seats per venue when granular capacity isn't available. Surfaced in
// the UI so the utilization figure is never mistaken for a measured value.
const ASSUMED_SEATS_PER_VENUE = 50;

const monthKey = (d: Date) => `${d.getFullYear()}-${d.getMonth()}`;

export const SuperAdminAnalyticsView: React.FC<SuperAdminAnalyticsViewProps> = ({ users, readingRooms, bookings }) => {
    // Defer chart mount until after first paint so Recharts sees a non-zero
    // parent height. Tailwind h-80 only resolves after layout; without this,
    // Recharts logs width(-1)/height(-1) warnings on every super-admin
    // navigation that lands here.
    const [chartMounted, setChartMounted] = useState(false);
    useEffect(() => {
        const t = setTimeout(() => setChartMounted(true), 50);
        return () => clearTimeout(t);
    }, []);
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

    // Estimated occupancy. Capacity is an estimate (no per-venue seat counts in
    // state yet), so this is labelled "Est." in the UI — never presented as a
    // measured occupancy rate.
    const estCapacity = totalVenues * ASSUMED_SEATS_PER_VENUE;
    const activeUtil = bookings.filter((b: any) => b.status === 'ACTIVE').length;
    const utilizationRate = estCapacity > 0 ? Math.round((activeUtil / estCapacity) * 100) : 0;

    // Real "this month" counts from the data we actually have. Users carry no
    // creation timestamp in the client model, so we don't fabricate a delta.
    const { newVenuesThisMonth, newBookingsThisMonth, venueGrowth, hasVenueGrowthData } = useMemo(() => {
        const now = new Date();
        const thisMonth = monthKey(now);

        const buckets: { name: string; key: string; val: number }[] = [];
        for (let i = 5; i >= 0; i--) {
            const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            buckets.push({ name: d.toLocaleString('default', { month: 'short' }), key: monthKey(d), val: 0 });
        }
        const idxByKey = new Map(buckets.map((b, i) => [b.key, i]));

        let venuesThisMonth = 0;
        let dataPoints = 0;
        for (const r of readingRooms as any[]) {
            if (!r.createdAt) continue;
            const d = new Date(r.createdAt);
            if (isNaN(d.getTime())) continue;
            dataPoints++;
            if (monthKey(d) === thisMonth) venuesThisMonth++;
            const idx = idxByKey.get(monthKey(d));
            if (idx !== undefined) buckets[idx].val++;
        }

        let bookingsThisMonth = 0;
        for (const b of bookings as any[]) {
            const raw = b.createdAt || b.date;
            if (!raw) continue;
            const d = new Date(raw);
            if (!isNaN(d.getTime()) && monthKey(d) === thisMonth) bookingsThisMonth++;
        }

        return {
            newVenuesThisMonth: venuesThisMonth,
            newBookingsThisMonth: bookingsThisMonth,
            venueGrowth: buckets.map(({ name, val }) => ({ name, val })),
            hasVenueGrowthData: dataPoints > 0,
        };
    }, [readingRooms, bookings]);

    const handleExport = () => {
        const rows: [string, string | number][] = [
            ['Metric', 'Value'],
            ['Total users', totalUsers],
            ['Students', students],
            ['Venue owners', admins],
            ['Staff', superAdmins],
            ['Venues', totalVenues],
            ['New venues this month', newVenuesThisMonth],
            ['Total bookings', totalBookings],
            ['New bookings this month', newBookingsThisMonth],
            ['Active bookings', activeUtil],
            [`Est. utilization (% of ${ASSUMED_SEATS_PER_VENUE}/venue)`, `${utilizationRate}%`],
        ];
        const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'platform-analytics.csv';
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="space-y-6 animate-in fade-in">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">Analytics Studio</h2>
                    <p className="text-gray-500">Platform performance from live data.</p>
                </div>
                <div className="flex gap-2">
                    <Button onClick={handleExport}><ExternalLink className="w-4 h-4 mr-2" /> Export Data</Button>
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
                    <p className="text-xs text-gray-500 mt-1">Across all roles</p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Venues Active</h4>
                        <Building2 className="w-5 h-5 text-emerald-500" />
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{totalVenues}</p>
                    <p className="text-xs text-gray-500 mt-1">
                        {newVenuesThisMonth > 0 ? `+${newVenuesThisMonth} this month` : 'Listed on platform'}
                    </p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Total Bookings</h4>
                        <Calendar className="w-5 h-5 text-blue-500" />
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{totalBookings}</p>
                    <p className="text-xs text-gray-500 mt-1">
                        {newBookingsThisMonth > 0 ? `+${newBookingsThisMonth} this month` : 'Lifetime volume'}
                    </p>
                </Card>
                <Card className="p-6">
                    <div className="flex items-center justify-between">
                        <h4 className="text-gray-500 font-medium text-sm uppercase">Utilization</h4>
                        <div className="w-5 h-5 rounded-full bg-orange-100 text-orange-600 flex items-center justify-center text-xs font-bold">%</div>
                    </div>
                    <p className="text-3xl font-bold text-gray-900 mt-2">{utilizationRate}%</p>
                    <p className="text-xs text-gray-500 mt-1">Est. — assumes {ASSUMED_SEATS_PER_VENUE} seats/venue</p>
                </Card>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="p-6 min-h-[400px]">
                    <h3 className="text-lg font-bold text-gray-900 mb-6">User Distribution</h3>
                    <div className="h-80 w-full relative" style={{ minHeight: 320, minWidth: 100 }}>
                        {chartMounted && (
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
                        )}
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
                    <h3 className="text-lg font-bold text-gray-900 mb-1">Growth (New Venues)</h3>
                    <p className="text-xs text-gray-400 mb-5">New venues added per month, last 6 months.</p>
                    <div className="h-80 w-full" style={{ minHeight: 320, minWidth: 100 }}>
                        {!hasVenueGrowthData ? (
                            <div className="h-full flex flex-col items-center justify-center text-center text-gray-400">
                                <Building2 className="w-8 h-8 mb-2 text-gray-300" />
                                <p className="text-sm">No venue creation dates available to chart growth yet.</p>
                            </div>
                        ) : chartMounted && (
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={venueGrowth}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#9CA3AF' }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#9CA3AF' }} allowDecimals={false} />
                                <Tooltip cursor={{ fill: '#F9FAFB' }} contentStyle={{ borderRadius: '8px', border: 'none' }} />
                                <Bar dataKey="val" fill="#10B981" radius={[4, 4, 0, 0]} barSize={30} />
                            </BarChart>
                        </ResponsiveContainer>
                        )}
                    </div>
                </Card>
            </div>
        </div>
    );
};
