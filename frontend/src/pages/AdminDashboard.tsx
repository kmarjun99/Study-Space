
import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { AppState, CabinStatus, Accommodation, ListingStatus, Ad } from '../types';
import { Card, Badge, Button } from '../components/UI';
import { supplyService } from '../services/supplyService';
import { AdBanner } from '../components/AdBanner';
import { adService, getTargetedAd } from '../services/adService';
import { trustService, TrustFlag } from '../services/trustService';
import { ResolveFlagModal } from '../components/ResolveFlagModal';
import { CreateSupportTicketModal } from '../components/CreateSupportTicketModal';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import { DollarSign, Home, Activity, Building2, Plus, MapPin, Users, BedDouble, CheckCircle, Clock, AlertTriangle, AlertOctagon, XCircle, ShieldAlert, FileWarning } from 'lucide-react';

interface AdminDashboardProps {
    state: AppState;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ state }) => {
    // --- Ads State ---
    const [ads, setAds] = useState<Ad[]>([]);
    // --- Trust/Flag State ---
    const [activeFlags, setActiveFlags] = useState<any[]>([]);
    const [selectedFlag, setSelectedFlag] = useState<TrustFlag | null>(null);
    const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);
    const [isSupportModalOpen, setIsSupportModalOpen] = useState(false);
    // --- Chart Mount State (prevents Recharts dimension warnings) ---
    const [isMounted, setIsMounted] = useState(false);

    // Set mounted after initial render for chart dimension fix
    useEffect(() => {
        const timer = setTimeout(() => setIsMounted(true), 50);
        return () => clearTimeout(timer);
    }, []);

    // Fetch ads on mount
    useEffect(() => {
        const fetchAds = async () => {
            try {
                const fetchedAds = await adService.getAllAds(false);
                setAds(fetchedAds);
            } catch (e) {
                console.error('Failed to load ads for owner', e);
            }
        };
        fetchAds();
    }, []);

    // Get targeted ad for ADMIN/OWNER audience
    const targetedAd = useMemo(() => {
        return getTargetedAd(ads, 'ADMIN', false, 'DASHBOARD');
    }, [ads]);

    // --- 1. Identification ---
    const myRoom = state.readingRooms.find(r => r.ownerId === state.currentUser?.id);
    // Fetch fresh accommodations to avoid stale status
    const [myAccommodations, setMyAccommodations] = useState<Accommodation[]>(state.accommodations.filter(a => a.ownerId === state.currentUser?.id));

    useEffect(() => {
        const fetchFreshAccommodations = async () => {
            try {
                // Determine if we need to fetch specific user's or just rely on global if already updated
                // But generally safe to fetch fresh
                const fresh = await supplyService.getMyAccommodations();
                if (fresh) setMyAccommodations(fresh);
            } catch (error) {
                console.error("Failed to fetch fresh accommodations", error);
            }
        };
        fetchFreshAccommodations();
    }, [state.currentUser?.id]);

    const hasVenue = !!myRoom;
    const hasHousing = myAccommodations.length > 0;

    // Fetch trust/flag status for owner's listings
    useEffect(() => {
        const fetchFlags = async () => {
            if (!state.currentUser?.id) return;
            try {
                const flags = await trustService.getOwnerFlags(state.currentUser.id);
                // Filter for active/unresolved flags only
                const active = flags.filter((f: any) => f.status !== 'resolved' && f.status !== 'approved');
                setActiveFlags(active);
            } catch (e) {
                console.error('Failed to fetch owner flags', e);
            }
        };
        fetchFlags();
    }, [state.currentUser?.id]);

    // --- 2. Venue Data Preparation ---
    const myCabins = myRoom ? state.cabins.filter(c => c.readingRoomId === myRoom.id) : [];
    const myCabinIds = new Set(myCabins.map(c => c.id));
    const myBookings = state.bookings.filter(b => myCabinIds.has(b.cabinId));

    const totalCabins = myCabins.length;
    const occupiedCabins = myCabins.filter(c => c.status === CabinStatus.OCCUPIED).length;
    const occupancyRate = totalCabins > 0 ? Math.round((occupiedCabins / totalCabins) * 100) : 0;
    const totalRevenue = myBookings.reduce((acc, curr) => acc + curr.amount, 0);

    // Mock Revenue Data
    const revenueData = [
        { name: 'Jan', amt: totalRevenue * 0.1 },
        { name: 'Feb', amt: totalRevenue * 0.2 },
        { name: 'Mar', amt: totalRevenue * 0.15 },
        { name: 'Apr', amt: totalRevenue * 0.25 },
        { name: 'May', amt: totalRevenue * 0.3 },
    ];

    const occupancyData = [
        { name: 'Available', value: totalCabins - occupiedCabins },
        { name: 'Occupied', value: occupiedCabins },
        { name: 'Maintenance', value: myCabins.filter(c => c.status === CabinStatus.MAINTENANCE).length },
    ];
    const COLORS = ['#10B981', '#EF4444', '#9CA3AF'];

    // --- 3. Housing Data Preparation ---
    const totalProperties = myAccommodations.length;
    const pgCount = myAccommodations.filter(a => a.type === 'PG').length;
    const hostelCount = myAccommodations.filter(a => a.type === 'HOSTEL').length;
    // Mock capacity calc based on sharing type for demo
    const estimatedCapacity = myAccommodations.reduce((acc, curr) => {
        const sharingMap: Record<string, number> = { 'Single': 1, 'Double': 2, 'Triple': 3, 'Four': 4 };
        const beds = sharingMap[curr.sharing] || 2;
        // Assuming each property has ~10 rooms for this mock stat
        return acc + (beds * 10);
    }, 0);

    // --- 4. Verification Status Helper ---
    const getVerificationBadge = (status: string, isVerified: boolean, trustStatus?: string, entityId?: string) => {
        // First check activeFlags array for real-time flag status
        if (entityId && activeFlags.length > 0) {
            const entityFlag = activeFlags.find(f => f.entity_id === entityId);
            if (entityFlag) {
                const isSevere = entityFlag.status === 'escalated' || entityFlag.status === 'rejected';
                return (
                    <Badge variant="error">
                        <AlertOctagon className="w-3 h-3 mr-1" />
                        {isSevere ? 'Suspended' : 'Flagged'}
                    </Badge>
                );
            }
        }

        // Trust status takes priority over listing status
        if (trustStatus === 'FLAGGED' || trustStatus === 'SUSPENDED') {
            return (
                <Badge variant="error">
                    <AlertOctagon className="w-3 h-3 mr-1" />
                    {trustStatus === 'SUSPENDED' ? 'Suspended' : 'Action Required'}
                </Badge>
            );
        }
        if (trustStatus === 'UNDER_REVIEW') {
            return (
                <Badge variant="warning">
                    <Clock className="w-3 h-3 mr-1" />
                    Under Review
                </Badge>
            );
        }

        // Listing status
        if (status === ListingStatus.LIVE) {
            return (
                <Badge variant="success">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Live
                </Badge>
            );
        }
        if (status === ListingStatus.VERIFICATION_PENDING || status === ListingStatus.PAYMENT_PENDING) {
            return (
                <Badge variant="warning">
                    <Clock className="w-3 h-3 mr-1" />
                    Pending
                </Badge>
            );
        }
        if (status === ListingStatus.REJECTED) {
            return (
                <Badge variant="error">
                    <AlertTriangle className="w-3 h-3 mr-1" />
                    Rejected
                </Badge>
            );
        }
        return (
            <Badge variant="info">
                <Clock className="w-3 h-3 mr-1" />
                Draft
            </Badge>
        );
    };

    // --- View: No Business Listed ---
    if (!hasVenue && !hasHousing) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
                <div className="bg-indigo-100 p-6 rounded-full mb-6">
                    <Building2 className="h-12 w-12 md:h-16 md:w-16 text-indigo-600" />
                </div>
                <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">Start Your Business</h1>
                <p className="text-gray-600 max-w-md mb-8 text-sm md:text-base">
                    Create a Reading Room or List a PG to get started.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                    <Link to="/admin/venue/new">
                        <Button size="lg" className="w-full sm:w-auto bg-purple-600 hover:bg-purple-700">
                            <Plus className="h-5 w-5 mr-2" /> Create Reading Room
                        </Button>
                    </Link>
                    <Link to="/admin/accommodation/new">
                        <Button size="lg" className="w-full sm:w-auto bg-purple-600 hover:bg-purple-700">
                            <Plus className="h-5 w-5 mr-2" /> List Accommodation
                        </Button>
                    </Link>
                </div>
            </div>
        );
    }

    // --- View: Dashboard ---
    return (
        <div className="space-y-8 pb-10">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                    <p className="text-gray-500 text-sm md:text-base">
                        Overview for <span className="font-semibold text-indigo-600">
                            {hasVenue && hasHousing ? 'All Properties' : hasVenue ? myRoom?.name : 'Housing Listings'}
                        </span>
                    </p>
                </div>
            </div>

            {/* FLAG/SUSPENSION ALERT BANNER */}
            {activeFlags.length > 0 && (
                <div className="space-y-3 animate-in fade-in slide-in-from-top-3 duration-300">
                    {activeFlags.map((flag: TrustFlag) => {
                        // 'escalated' or 'rejected' = severe (suspended), 'active' = warning
                        const isSevere = flag.status === 'escalated' || flag.status === 'rejected';
                        return (
                            <div
                                key={flag.id}
                                className={`p-4 rounded-xl border-l-4 ${isSevere
                                    ? 'bg-red-50 border-red-500'
                                    : 'bg-orange-50 border-orange-500'
                                    }`}
                            >
                                <div className="flex items-start gap-3">
                                    <div className={`p-2 rounded-lg flex-shrink-0 ${isSevere ? 'bg-red-100 text-red-600' : 'bg-orange-100 text-orange-600'
                                        }`}>
                                        {isSevere ? (
                                            <XCircle className="w-6 h-6" />
                                        ) : (
                                            <ShieldAlert className="w-6 h-6" />
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className={`font-bold ${isSevere ? 'text-red-900' : 'text-orange-900'
                                                }`}>
                                                {isSevere ? '🚫 Listing Suspended' : '⚠️ Action Required'}
                                            </h3>
                                            <Badge variant={isSevere ? 'error' : 'warning'}>
                                                {flag.entity_name}
                                            </Badge>
                                        </div>
                                        <p className={`text-sm mb-2 ${isSevere ? 'text-red-700' : 'text-orange-700'
                                            }`}>
                                            {isSevere
                                                ? 'Your listing has been suspended and is not visible to users.'
                                                : 'Your listing has been flagged and requires your attention.'}
                                        </p>
                                        <div className="bg-white/60 rounded-lg p-3 mb-3">
                                            <p className="text-xs font-semibold text-gray-500 uppercase mb-1">Reason</p>
                                            <p className="text-sm text-gray-800">
                                                {flag.custom_reason || flag.flag_type?.replace(/_/g, ' ') || 'Please contact support for details.'}
                                            </p>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            <Button
                                                size="sm"
                                                variant={isSevere ? 'danger' : 'outline'}
                                                onClick={() => {
                                                    setSelectedFlag(flag);
                                                    setIsResolveModalOpen(true);
                                                }}
                                            >
                                                <FileWarning className="w-4 h-4 mr-1" />
                                                Resolve Issue
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => {
                                                    setSelectedFlag(flag);
                                                    setIsSupportModalOpen(true);
                                                }}
                                            >
                                                Contact Support
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Owner Ad Banner */}
            {targetedAd && (
                <div className="animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Partner Offer</div>
                    <AdBanner ad={targetedAd} variant="banner" />
                </div>
            )}

            {/* --- SECTION 1: VENUE / READING ROOM --- */}
            {
                hasVenue && myRoom && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
                        <div className="flex items-center justify-between border-b border-gray-200 pb-2">
                            <h2 className="text-lg font-bold text-gray-800 flex items-center">
                                <Building2 className="w-5 h-5 mr-2 text-indigo-500" /> Reading Room
                            </h2>
                            <Link to={`/admin/venue/${myRoom.id}`}>
                                <Button size="sm">Manage Venue</Button>
                            </Link>
                        </div>

                        {/* Venue Overview Card */}
                        <Card className="p-0 overflow-hidden flex flex-col md:flex-row">
                            <div className="w-full md:w-1/4 h-32 md:h-auto relative bg-gray-200">
                                <img src={myRoom.imageUrl} alt={myRoom.name} className="w-full h-full object-cover" />
                            </div>
                            <div className="p-5 flex-1 flex flex-col justify-center">
                                <div className="flex items-center justify-between mb-1">
                                    <h3 className="text-xl font-bold text-gray-900">{myRoom.name}</h3>
                                    {getVerificationBadge(myRoom.status || '', myRoom.isVerified || false, (myRoom as any).trust_status, myRoom.id)}
                                </div>
                                <div className="flex items-center text-gray-600 text-sm mt-1">
                                    <MapPin className="w-4 h-4 mr-1 text-gray-400" /> {myRoom.address}
                                </div>
                            </div>
                        </Card>

                        {/* Venue Stats */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            {[
                                { label: 'Total Revenue', value: `₹${totalRevenue.toLocaleString()}`, icon: DollarSign, color: 'bg-green-500' },
                                { label: 'Occupancy Rate', value: `${occupancyRate}%`, icon: Home, color: 'bg-blue-500' },
                                { label: 'Total Cabins', value: totalCabins.toString(), icon: Building2, color: 'bg-indigo-500' },
                                { label: 'Maintenance', value: `${occupancyData[2].value} Cabins`, icon: Activity, color: 'bg-orange-500' },
                            ].map((stat) => (
                                <Card key={stat.label} className="p-4 md:p-5 flex items-center shadow-sm">
                                    <div className={`p-3 rounded-lg mr-4 text-white ${stat.color} flex-shrink-0`}>
                                        <stat.icon className="h-5 w-5 md:h-6 md:w-6" />
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-sm font-medium text-gray-500 truncate">{stat.label}</p>
                                        <p className="text-xl md:text-2xl font-bold text-gray-900">{stat.value}</p>
                                    </div>
                                </Card>
                            ))}
                        </div>

                        {/* Venue Charts */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            <Card className="p-6">
                                <h3 className="text-lg font-medium text-gray-900 mb-4">Revenue Analytics</h3>
                                <div className="h-64 w-full min-w-0" style={{ minHeight: 256, minWidth: 100 }}>
                                    {isMounted && (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <BarChart data={revenueData}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" />
                                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                                                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} tickFormatter={(val) => `₹${val}`} />
                                                <Tooltip
                                                    contentStyle={{ backgroundColor: '#fff', borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                                                    cursor={{ fill: '#f9fafb' }}
                                                />
                                                <Bar dataKey="amt" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    )}
                                </div>
                            </Card>
                            <Card className="p-6">
                                <h3 className="text-lg font-medium text-gray-900 mb-4">Real-time Occupancy</h3>
                                <div className="h-64 w-full min-w-0 relative" style={{ minHeight: 256, minWidth: 100 }}>
                                    {isMounted && (
                                        <ResponsiveContainer width="100%" height="100%">
                                            <PieChart>
                                                <Pie
                                                    data={occupancyData}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={60}
                                                    outerRadius={80}
                                                    fill="#8884d8"
                                                    paddingAngle={5}
                                                    dataKey="value"
                                                >
                                                    {occupancyData.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                    ))}
                                                </Pie>
                                                <Tooltip />
                                            </PieChart>
                                        </ResponsiveContainer>
                                    )}
                                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                        <div className="text-center">
                                            <p className="text-2xl font-bold text-gray-900">{occupancyRate}%</p>
                                            <p className="text-xs text-gray-500">Occupied</p>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex flex-wrap justify-center gap-3 mt-2">
                                    {occupancyData.map((d, i) => (
                                        <div key={d.name} className="flex items-center text-xs font-medium text-gray-600">
                                            <span className="w-2.5 h-2.5 rounded-full mr-1.5" style={{ backgroundColor: COLORS[i] }}></span>
                                            {d.name} ({d.value})
                                        </div>
                                    ))}
                                </div>
                            </Card>
                        </div>
                    </div>
                )
            }

            {/* --- SECTION 2: HOUSING / ACCOMMODATION --- */}
            {
                hasHousing && (
                    <div className={`space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700 ${hasVenue ? 'pt-8 border-t border-gray-200' : ''}`}>
                        <div className="flex items-center justify-between border-b border-gray-200 pb-2">
                            <h2 className="text-lg font-bold text-gray-800 flex items-center">
                                <Home className="w-5 h-5 mr-2 text-orange-500" /> {hasVenue ? 'Housing Inventory' : 'Housing Dashboard'}
                            </h2>
                            <Link to="/admin/accommodation">
                                <Button variant="ghost" size="sm">Manage Listings</Button>
                            </Link>
                        </div>

                        {/* Housing Stats */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            <Card className="p-5 border-l-4 border-orange-500 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Total Properties</p>
                                    <p className="text-2xl font-bold text-gray-900">{totalProperties}</p>
                                </div>
                                <div className="p-3 bg-orange-50 rounded-lg text-orange-500">
                                    <Home className="w-6 h-6" />
                                </div>
                            </Card>
                            <Card className="p-5 border-l-4 border-purple-500 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Listing Types</p>
                                    <p className="text-sm font-bold text-gray-900 mt-1">{pgCount} PGs • {hostelCount} Hostels</p>
                                </div>
                                <div className="p-3 bg-purple-50 rounded-lg text-purple-500">
                                    <Building2 className="w-6 h-6" />
                                </div>
                            </Card>
                            <Card className="p-5 border-l-4 border-blue-500 shadow-sm flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-medium text-gray-500">Total Capacity</p>
                                    <p className="text-2xl font-bold text-gray-900">~{estimatedCapacity}</p>
                                    <p className="text-xs text-gray-400">Estimated Beds</p>
                                </div>
                                <div className="p-3 bg-blue-50 rounded-lg text-blue-500">
                                    <BedDouble className="w-6 h-6" />
                                </div>
                            </Card>
                        </div>

                        {/* Housing List */}
                        <div>
                            <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">Your Listings</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                                {myAccommodations.map(acc => (
                                    <Card key={acc.id} className="overflow-hidden group hover:shadow-md transition-shadow">
                                        <div className="flex h-full flex-col">
                                            <div className="h-40 relative">
                                                <img src={acc.imageUrl} alt={acc.name} className="w-full h-full object-cover" />
                                                <div className="absolute top-2 right-2">
                                                    <Badge variant={acc.type === 'PG' ? 'info' : 'warning'}>{acc.type}</Badge>
                                                </div>
                                            </div>
                                            <div className="p-4 flex-1 flex flex-col">
                                                <div className="flex items-center justify-between mb-1">
                                                    <h4 className="font-bold text-gray-900">{acc.name}</h4>
                                                    {getVerificationBadge(acc.status || '', acc.isVerified || false)}
                                                </div>
                                                <p className="text-sm text-gray-500 flex items-center mb-3">
                                                    <MapPin className="w-3 h-3 mr-1" /> {acc.address}
                                                </p>
                                                <div className="mt-auto flex items-center justify-between pt-3 border-t border-gray-50">
                                                    <span className="font-bold text-indigo-600">₹{acc.price.toLocaleString()}/mo</span>
                                                    <span className="text-xs text-gray-500">{acc.sharing} Sharing</span>
                                                </div>
                                            </div>
                                        </div>
                                    </Card>
                                ))}
                            </div>
                        </div>
                    </div>
                )
            }
            {/* Modals */}
            <ResolveFlagModal
                isOpen={isResolveModalOpen}
                onClose={() => setIsResolveModalOpen(false)}
                flag={selectedFlag}
                user={state.currentUser!}
                onSuccess={() => {
                    // Refresh flags
                    const fetchFlags = async () => {
                        if (!state.currentUser?.id) return;
                        const flags = await trustService.getOwnerFlags(state.currentUser.id);
                        const active = flags.filter((f: any) => f.status !== 'resolved' && f.status !== 'approved');
                        setActiveFlags(active);
                    };
                    fetchFlags();
                }}
            />

            <CreateSupportTicketModal
                isOpen={isSupportModalOpen}
                onClose={() => setIsSupportModalOpen(false)}
                user={state.currentUser!}
                initialSubject={selectedFlag ? `Appeal for Flag: ${selectedFlag.entity_name}` : ''}
                initialDescription={selectedFlag ? `Regarding flag on ${selectedFlag.entity_name} (${selectedFlag.flag_type})...\n\n` : ''}
                category="VENUE_ISSUE"
            />
        </div >
    );
};
