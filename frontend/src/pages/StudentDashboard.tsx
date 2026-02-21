import React, { useMemo, useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import toast from 'react-hot-toast';
import { AppState, User, ReadingRoom } from '../types';
import { Button, Card, Badge, Modal } from '../components/UI';
import { AdBanner } from '../components/AdBanner';
import { SkeletonCard } from '../components/SkeletonCard';
import { NotificationDropdown } from '../components/NotificationDropdown';
import { getTargetedAd } from '../services/adService';
import { venueService } from '../services/venueService'; // Added import
import { boostService, BoostRequest } from '../services/boostService'; // For featured listings
import { Calendar, Clock, AlertCircle, ArrowRight, CreditCard, User as UserIcon, Star, MessageSquare, MapPin, QrCode, CheckCircle, Phone, Sparkles, Bell, Heart, TrendingUp, Share2 } from 'lucide-react';


interface StudentDashboardProps {
    state: AppState;
    user: User;
    onAddReview: (review: { readingRoomId?: string, accommodationId?: string, rating: number, comment: string }) => Promise<void>;
    onExtendBooking?: (bookingId: string, months: number, extensionAmount?: number) => Promise<void>;
}

// Helper to format dates to IST
import { format, parseISO } from 'date-fns';

const formatToIST = (dateString: string) => {
    try {
        const date = new Date(dateString);
        // Manual offset adjustment not needed if browser is in IST, but to enforce "IST feel":
        // using date-fns format with readable string is safer
        return format(date, "d MMM yyyy"); // e.g. 17 Jan 2026
    } catch (e) {
        return dateString;
    }
};

const formatToISTWithTime = (dateString: string) => {
    try {
        const date = new Date(dateString);
        return format(date, "d MMM yyyy, h:mm a"); // e.g. 17 Jan 2026, 12:00 AM
    } catch (e) {
        return dateString;
    }
};

export const StudentDashboard: React.FC<StudentDashboardProps> = ({ state, user, onAddReview, onExtendBooking }) => {
    // --- State ---
    const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
    const [isSubmittingReview, setIsSubmittingReview] = useState(false);
    const [reviewRating, setReviewRating] = useState(5);
    const [reviewComment, setReviewComment] = useState('');
    const [hasReviewed, setHasReviewed] = useState(false);
    const [featuredListings, setFeaturedListings] = useState<{ venueId: string, venueType: string, venueName: string }[]>([]);

    // Phase 2: Search & Filter
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'EXPIRED'>('ALL');
    const [isLoading, setIsLoading] = useState(true);

    // Phase 2: Notifications
    const [notifications, setNotifications] = useState([
        { id: '1', type: 'booking' as const, title: 'Booking Confirmed', message: 'Your booking for Study Haven has been confirmed', timestamp: '2 hours ago', read: false },
        { id: '2', type: 'payment' as const, title: 'Payment Successful', message: 'Payment of ₹2,500 received', timestamp: '1 day ago', read: false },
        { id: '3', type: 'alert' as const, title: 'Booking Expiring Soon', message: 'Your booking expires in 5 days', timestamp: '2 days ago', read: true },
    ]);

    // Fetch featured listings (public endpoint - no auth required)
    useEffect(() => {
        const loadFeaturedListings = async () => {
            try {
                const featured = await boostService.getFeaturedListings();
                setFeaturedListings(featured);
            } catch (error) {
                // console.log('Could not load featured listings');
            }
        };
        loadFeaturedListings();
    }, []);

    // Get ALL Active Bookings (not just one)
    // Users can have multiple active bookings across different venues
    const activeBookings = useMemo(() => {
        const now = new Date();
        return (state.bookings || []).filter(b =>
            b.userId === user.id &&
            b.status === 'ACTIVE' &&
            new Date(b.endDate) > now
        );
    }, [state.bookings, user.id]);

    // For backward compatibility - first active booking (used in some modals)
    const activeBooking = activeBookings.length > 0 ? activeBookings[0] : null;

    useEffect(() => {
        const checkReview = async () => {
            // Resolve Reading Room ID through cabin
            let rrId: string | undefined = undefined;
            if (activeBooking?.cabinId) {
                const cabin = state.cabins.find(c => c.id === activeBooking.cabinId);
                rrId = cabin?.readingRoomId;
            }

            if (rrId) {
                // Check review status for this reading room
                try {
                    const reviewed = await venueService.checkReviewStatus(rrId, undefined);
                    setHasReviewed(reviewed);
                } catch (e) {
                    // console.error("Failed to check review status", e);
                }
            } else {
                // No reading room found - skip review check
            }
        };
        checkReview();
    }, [activeBooking, state.cabins]);

    // Details Modal State
    const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);

    // Extend Modal State - tracks WHICH booking is being extended
    const [isExtendModalOpen, setIsExtendModalOpen] = useState(false);
    const [selectedBookingForExtend, setSelectedBookingForExtend] = useState<any>(null);
    const [extensionDuration, setExtensionDuration] = useState(1);
    const [isProcessingExtension, setIsProcessingExtension] = useState(false);
    const [extensionSuccess, setExtensionSuccess] = useState(false);

    // Ad State
    const [showWelcomeAd, setShowWelcomeAd] = useState(false);
    const [ads, setAds] = useState<any[]>([]); // Cache ads

    // Fetch Ads on Mount
    useEffect(() => {
        const fetchAds = async () => {
            try {
                // Dynamically import to avoid circular dependency if needed, or just import adService
                const { adService } = await import('../services/adService');
                const fetchedAds = await adService.getAds();
                setAds(fetchedAds);
            } catch (e) {
                // console.error("Failed to load ads", e);
            }
        };
        fetchAds();
    }, []);

    // --- Derived Data ---
    // activeBooking removed from here as it is now defined above to support review check


    const bookingHistory = useMemo(() => {
        return (state.bookings || []).filter(b => b.userId === user.id).sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime());
    }, [state.bookings, user.id]);

    // Phase 2: Statistics calculations
    const totalBookingsCount = useMemo(() => {
        return bookingHistory.length;
    }, [bookingHistory]);

    const totalDaysBooked = useMemo(() => {
        return bookingHistory.reduce((total, booking) => {
            const days = Math.ceil(
                (new Date(booking.endDate).getTime() - new Date(booking.startDate).getTime()) / (1000 * 60 * 60 * 24)
            );
            return total + days;
        }, 0);
    }, [bookingHistory]);

    const favoritesCount = useMemo(() => {
        return (state.favorites || []).length;
    }, [state.favorites]);

    // Determine related data for active booking
    const activeCabin = useMemo(() => {
        if (!activeBooking) {
            return null;
        }
        const cabin = (state.cabins || []).find(c => c.id === activeBooking.cabinId);
        return cabin || null;
    }, [activeBooking, state.cabins]);

    const activeVenue = useMemo(() => {
        if (!activeCabin) {
            return null;
        }
        const venue = (state.readingRooms || []).find(r => r.id === activeCabin.readingRoomId);
        return venue || null;
    }, [activeCabin, state.readingRooms]);

    // Determine which venue to review (prefer active, otherwise most recent)
    const venueToReview = useMemo(() => {
        if (activeVenue) return activeVenue;
        if (bookingHistory.length > 0) {
            const recentCabin = state.cabins.find(c => c.id === bookingHistory[0].cabinId);
            return state.readingRooms.find(r => r.id === recentCabin?.readingRoomId);
        }
        return null;
    }, [activeVenue, bookingHistory, state.cabins, state.readingRooms]);

    // Waitlist
    const myWaitlist = useMemo(() => {
        return state.waitlist.filter(w => w.userId === user.id);
    }, [state.waitlist, user.id]);

    // Get Targeted Ad
    const targetedAd = useMemo(() => {
        // Pass loaded 'ads' array
        return getTargetedAd(ads, user.role, !!activeBooking, 'DASHBOARD');
    }, [user.role, activeBooking, ads]);

    const popupAd = useMemo(() => {
        // Use a different ad for the popup logic, possibly randomized from the service
        return getTargetedAd(ads, user.role, !!activeBooking, 'DASHBOARD');
    }, [user.role, activeBooking, ads]);

    // --- Effects ---
    useEffect(() => {
        // Show "Welcome Ad" popup once per session (mock logic)
        const hasSeenAd = sessionStorage.getItem('hasSeenWelcomeAd');
        if (!hasSeenAd) {
            const timer = setTimeout(() => {
                setShowWelcomeAd(true);
                sessionStorage.setItem('hasSeenWelcomeAd', 'true');
            }, 2000); // Show after 2 seconds
            return () => clearTimeout(timer);
        }
    }, []);

    // --- Handlers ---

    const handleSubmitReview = async () => {
        if (venueToReview) {
            setIsSubmittingReview(true);
            try {
                // Ensure venueToReview.id is valid
                if (!venueToReview.id) {
                    throw new Error("Cannot identify the venue to review.");
                }

                await onAddReview({
                    readingRoomId: venueToReview.id,
                    // Pass accommodationId if available, but strict match the backend
                    accommodationId: undefined, // Or check if venue is an accommodation
                    rating: reviewRating,
                    comment: reviewComment
                });

                // Success Handling
                toast.success("Thanks for your feedback!");
                setHasReviewed(true); // Update state to disable buttons
                setIsReviewModalOpen(false);
                setReviewComment('');
                setReviewRating(5);
            } catch (error) {
                // console.error("Review submission error:", error);
                // Handled in App.tsx
            } finally {
                setIsSubmittingReview(false);
            }
        } else {
            toast.error("No venue found to review.");
        }
    };

    const handleExtendSubmit = async () => {
        // Use selected booking, not first active booking
        if (!selectedBookingForExtend || !onExtendBooking) return;

        setIsProcessingExtension(true);

        try {
            // Get cabin price to calculate extension amount
            const bookingCabin = state.cabins.find(c => c.id === selectedBookingForExtend.cabinId);
            const extensionAmount = (bookingCabin?.price || 1500) * extensionDuration;

            // Call the parent handler (which is async and calls backend)
            await onExtendBooking(selectedBookingForExtend.id, extensionDuration, extensionAmount);

            setExtensionSuccess(true);
        } catch (error) {
            // console.error('Extension failed:', error);
            toast.error('Failed to extend booking. Please try again.');
        } finally {
            setIsProcessingExtension(false);
        }
    };

    const closeExtendModal = () => {
        setIsExtendModalOpen(false);
        setSelectedBookingForExtend(null);
        setExtensionSuccess(false);
        setExtensionDuration(1);
    };

    // Helper to open extend modal for a specific booking
    const openExtendModal = (booking: any) => {
        setSelectedBookingForExtend(booking);
        setIsExtendModalOpen(true);
    };

    // Helper for rating text
    const getRatingLabel = (stars: number) => {
        switch (stars) {
            case 5: return "Excellent!";
            case 4: return "Very Good";
            case 3: return "Average";
            case 2: return "Poor";
            case 1: return "Terrible";
            default: return "Select a rating";
        }
    };

    // Phase 2: Notification handlers
    const handleMarkAsRead = (id: string) => {
        setNotifications(prev =>
            prev.map(n => n.id === id ? { ...n, read: true } : n)
        );
    };

    const handleMarkAllAsRead = () => {
        setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    };

    const handleClearAllNotifications = () => {
        setNotifications([]);
    };

    // Phase 2: Simulate loading
    useEffect(() => {
        const timer = setTimeout(() => setIsLoading(false), 1000);
        return () => clearTimeout(timer);
    }, []);

    // Phase 2: Filter and search bookings
    const filteredBookings = useMemo(() => {
        let filtered = [...activeBookings];

        // Apply status filter
        if (statusFilter === 'ACTIVE') {
            filtered = filtered.filter(b => {
                const daysRemaining = Math.max(0, Math.ceil((new Date(b.endDate).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)));
                return daysRemaining > 0;
            });
        } else if (statusFilter === 'EXPIRED') {
            filtered = filtered.filter(b => {
                const daysRemaining = Math.max(0, Math.ceil((new Date(b.endDate).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)));
                return daysRemaining === 0;
            });
        }

        // Apply search query
        if (searchQuery) {
            filtered = filtered.filter(b => {
                const cabin = state.cabins.find(c => c.id === b.cabinId);
                const venue = cabin ? state.readingRooms.find(r => r.id === cabin.readingRoomId) : null;
                const searchLower = searchQuery.toLowerCase();
                return (
                    venue?.name.toLowerCase().includes(searchLower) ||
                    venue?.locality?.toLowerCase().includes(searchLower) ||
                    venue?.city?.toLowerCase().includes(searchLower) ||
                    b.cabinNumber?.toLowerCase().includes(searchLower)
                );
            });
        }

        return filtered;
    }, [activeBookings, statusFilter, searchQuery, state.cabins, state.readingRooms]);

    // --- Render ---


    return (

        <div className="space-y-4 md:space-y-8 max-w-5xl mx-auto">
            {/* Header Section - Desktop Only */}
            <div className="hidden md:flex bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex-col md:flex-row items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <div className="h-14 w-14 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 text-xl font-bold">
                        {user.name.charAt(0)}
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Hello, {user.name}</h1>
                        <p className="text-gray-500">Welcome to your personalized study space dashboard.</p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    {/* Notification Dropdown */}
                    <NotificationDropdown
                        notifications={notifications}
                        onMarkAsRead={handleMarkAsRead}
                        onMarkAllAsRead={handleMarkAllAsRead}
                        onClearAll={handleClearAllNotifications}
                    />
                    {!activeBooking && (
                        <Link to="/student/book">
                            <Button size="lg" className="shadow-lg shadow-indigo-200">
                                Book a Cabin Now <ArrowRight className="ml-2 h-4 w-4" />
                            </Button>
                        </Link>
                    )}
                </div>
            </div>

            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                {isLoading ? (
                    <>
                        <SkeletonCard variant="statistics" />
                        <SkeletonCard variant="statistics" />
                        <SkeletonCard variant="statistics" />
                    </>
                ) : (
                    <>
                        <Card className="p-6 hover:shadow-lg transition-shadow">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-500 mb-1">Total Bookings</p>
                                    <p className="text-3xl font-bold text-gray-900">{totalBookingsCount}</p>
                                </div>
                                <div className="w-14 h-14 bg-gradient-to-br from-green-400 to-green-600 rounded-xl flex items-center justify-center">
                                    <TrendingUp className="w-7 h-7 text-white" />
                                </div>
                            </div>
                        </Card>

                        <Card className="p-6 hover:shadow-lg transition-shadow">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-500 mb-1">Days Booked</p>
                                    <p className="text-3xl font-bold text-gray-900">{totalDaysBooked}</p>
                                </div>
                                <div className="w-14 h-14 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center">
                                    <Calendar className="w-7 h-7 text-white" />
                                </div>
                            </div>
                        </Card>

                        <Card className="p-6 hover:shadow-lg transition-shadow">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-gray-500 mb-1">Favorites</p>
                                    <p className="text-3xl font-bold text-gray-900">{favoritesCount}</p>
                                </div>
                                <div className="w-14 h-14 bg-gradient-to-br from-red-400 to-red-600 rounded-xl flex items-center justify-center">
                                    <Heart className="w-7 h-7 text-white" />
                                </div>
                            </div>
                        </Card>
                    </>
                )}
            </div>

            {/* Quick Actions Grid - Enhanced */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <Link to="/student/book" className="block group">
                    <Card className="p-5 hover:shadow-lg transition-all hover:scale-105 cursor-pointer border-2 border-transparent hover:border-blue-200">
                        <div className="flex flex-col items-center text-center gap-3">
                            <div className="w-14 h-14 bg-gradient-to-br from-blue-100 to-blue-200 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                                <Calendar className="w-7 h-7 text-blue-600" />
                            </div>
                            <div>
                                <p className="font-semibold text-gray-900 mb-1">Book Cabin</p>
                                <p className="text-xs text-gray-500">Find study spaces</p>
                            </div>
                        </div>
                    </Card>
                </Link>

                <Link to="/student/accommodation" className="block group">
                    <Card className="p-5 hover:shadow-lg transition-all hover:scale-105 cursor-pointer border-2 border-transparent hover:border-green-200">
                        <div className="flex flex-col items-center text-center gap-3">
                            <div className="w-14 h-14 bg-gradient-to-br from-green-100 to-green-200 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                                <MapPin className="w-7 h-7 text-green-600" />
                            </div>
                            <div>
                                <p className="font-semibold text-gray-900 mb-1">Accommodations</p>
                                <p className="text-xs text-gray-500">Find PG/Hostels</p>
                            </div>
                        </div>
                    </Card>
                </Link>

                <Link to="/student/favorites" className="block group">
                    <Card className="p-5 hover:shadow-lg transition-all hover:scale-105 cursor-pointer border-2 border-transparent hover:border-red-200">
                        <div className="flex flex-col items-center text-center gap-3">
                            <div className="w-14 h-14 bg-gradient-to-br from-red-100 to-red-200 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                                <Heart className="w-7 h-7 text-red-600" />
                            </div>
                            <div>
                                <p className="font-semibold text-gray-900 mb-1">My Favorites</p>
                                <p className="text-xs text-gray-500">Saved venues</p>
                            </div>
                        </div>
                    </Card>
                </Link>

                <Link to="/student/payments" className="block group">
                    <Card className="p-5 hover:shadow-lg transition-all hover:scale-105 cursor-pointer border-2 border-transparent hover:border-purple-200">
                        <div className="flex flex-col items-center text-center gap-3">
                            <div className="w-14 h-14 bg-gradient-to-br from-purple-100 to-purple-200 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                                <CreditCard className="w-7 h-7 text-purple-600" />
                            </div>
                            <div>
                                <p className="font-semibold text-gray-900 mb-1">Payments</p>
                                <p className="text-xs text-gray-500">View history</p>
                            </div>
                        </div>
                    </Card>
                </Link>
            </div>


            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Column */}
                <div className="lg:col-span-2 space-y-8">
                    {/* Active Subscriptions Section - Multiple Cards */}
                    <div>
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-900">My Active Bookings</h2>
                            {activeBookings.length > 0 && (
                                <Badge variant="success">{activeBookings.length} Active</Badge>
                            )}
                        </div>

                        {/* Phase 2: Search & Filter Bar */}
                        {activeBookings.length > 0 && (
                            <Card className="p-4 mb-4">
                                <div className="flex flex-col md:flex-row gap-3">
                                    {/* Search Input */}
                                    <div className="flex-1">
                                        <input
                                            type="text"
                                            placeholder="Search by venue, location, or cabin..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                                        />
                                    </div>

                                    {/* Status Filter */}
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => setStatusFilter('ALL')}
                                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${statusFilter === 'ALL'
                                                ? 'bg-indigo-600 text-white'
                                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                                }`}
                                        >
                                            All
                                        </button>
                                        <button
                                            onClick={() => setStatusFilter('ACTIVE')}
                                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${statusFilter === 'ACTIVE'
                                                ? 'bg-green-600 text-white'
                                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                                }`}
                                        >
                                            Active
                                        </button>
                                        <button
                                            onClick={() => setStatusFilter('EXPIRED')}
                                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${statusFilter === 'EXPIRED'
                                                ? 'bg-gray-600 text-white'
                                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                                }`}
                                        >
                                            Expired
                                        </button>
                                    </div>
                                </div>

                                {/* Search Results Count */}
                                {searchQuery && (
                                    <p className="text-sm text-gray-600 mt-3">
                                        Found {filteredBookings.length} booking(s) matching "{searchQuery}"
                                    </p>
                                )}
                            </Card>
                        )}

                        {isLoading ? (
                            <div className="space-y-4">
                                <SkeletonCard variant="booking" />
                                <SkeletonCard variant="booking" />
                            </div>
                        ) : filteredBookings.length > 0 ? (
                            <div className="space-y-4">
                                {filteredBookings.map((booking, index) => {
                                    // Get cabin and venue for this specific booking
                                    const bookingCabin = state.cabins.find(c => c.id === booking.cabinId);
                                    const bookingVenue = bookingCabin
                                        ? state.readingRooms.find(r => r.id === bookingCabin.readingRoomId)
                                        : null;
                                    const daysRemaining = Math.max(0, Math.ceil((new Date(booking.endDate).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)));
                                    const isExpiringSoon = daysRemaining <= 7;

                                    return (
                                        <Card
                                            key={`${booking.id}-${index}`}
                                            className={`${isExpiringSoon ? 'bg-gradient-to-br from-amber-600 to-orange-700' : 'bg-gradient-to-br from-indigo-600 to-indigo-800'} text-white border-none p-6 relative overflow-hidden`}
                                        >
                                            <div className="absolute top-0 right-0 p-24 bg-white opacity-5 rounded-full transform translate-x-10 -translate-y-10"></div>

                                            <div className="relative z-10 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                                                <div className="flex-1">
                                                    <div className="flex items-center gap-2 mb-2">
                                                        <span className={`px-2 py-0.5 rounded text-xs font-semibold ${isExpiringSoon ? 'bg-amber-500 text-amber-100 border border-amber-400' : 'bg-indigo-500 text-indigo-100 border border-indigo-400'}`}>
                                                            {isExpiringSoon ? 'EXPIRING SOON' : 'ACTIVE'}
                                                        </span>
                                                    </div>

                                                    {/* Venue Name */}
                                                    <h3 className="text-2xl font-bold mb-1 leading-tight">
                                                        {bookingVenue?.name || "Unknown Venue"}
                                                    </h3>

                                                    {/* Location */}
                                                    <p className="text-white/70 text-sm flex items-center gap-1 mb-3">
                                                        <MapPin className="w-3 h-3" />
                                                        {bookingVenue?.locality || bookingVenue?.city || bookingVenue?.address || 'Location'}
                                                    </p>

                                                    {/* Cabin & Dates */}
                                                    <div className="flex flex-wrap gap-4 text-sm mb-4">
                                                        <div className="bg-white/10 px-3 py-2 rounded-lg backdrop-blur-sm">
                                                            <p className="text-xs text-white/60">Cabin</p>
                                                            <p className="font-semibold">{booking.cabinNumber || 'N/A'}</p>
                                                        </div>
                                                        <div className="bg-white/10 px-3 py-2 rounded-lg backdrop-blur-sm">
                                                            <p className="text-xs text-white/60">Validity</p>
                                                            <p className="font-semibold text-sm">
                                                                {formatToIST(booking.startDate)} → {formatToIST(booking.endDate)}
                                                            </p>
                                                        </div>
                                                        <div className="bg-white/10 px-3 py-2 rounded-lg backdrop-blur-sm">
                                                            <p className="text-xs text-white/60">Days Left</p>
                                                            <p className={`font-bold ${isExpiringSoon ? 'text-yellow-200' : ''}`}>{daysRemaining}</p>
                                                        </div>
                                                    </div>

                                                    {/* Progress Bar */}
                                                    <div className="mb-4">
                                                        <div className="flex justify-between text-xs mb-2">
                                                            <span className="text-white/70">Time Progress</span>
                                                            <span className="font-semibold">{Math.round((1 - daysRemaining / Math.max(1, Math.ceil((new Date(booking.endDate).getTime() - new Date(booking.startDate).getTime()) / (1000 * 60 * 60 * 24)))) * 100)}%</span>
                                                        </div>
                                                        <div className="w-full bg-white/20 rounded-full h-2.5">
                                                            <div
                                                                className={`h-2.5 rounded-full transition-all ${isExpiringSoon ? 'bg-amber-300' : 'bg-white'}`}
                                                                style={{ width: `${Math.round((1 - daysRemaining / Math.max(1, Math.ceil((new Date(booking.endDate).getTime() - new Date(booking.startDate).getTime()) / (1000 * 60 * 60 * 24)))) * 100)}%` }}
                                                            ></div>
                                                        </div>
                                                    </div>

                                                    {/* Quick Actions */}
                                                    <div className="grid grid-cols-3 gap-2">
                                                        <button
                                                            onClick={() => window.open(`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(bookingVenue?.address || bookingVenue?.name || '')}`, '_blank')}
                                                            className="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 border border-white/20"
                                                        >
                                                            <MapPin className="w-3.5 h-3.5" />
                                                            <span>Directions</span>
                                                        </button>
                                                        <button
                                                            onClick={() => bookingVenue?.contactPhone && window.open(`tel:${bookingVenue.contactPhone}`, '_self')}
                                                            className="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 border border-white/20"
                                                        >
                                                            <Phone className="w-3.5 h-3.5" />
                                                            <span>Contact</span>
                                                        </button>
                                                        <button
                                                            onClick={async () => {
                                                                if (!bookingVenue) return;
                                                                
                                                                // Generate booking details text without exposing full URL
                                                                const bookingDetails = `📚 My Study Space Booking

🏢 ${bookingVenue.name}
📍 ${bookingVenue.locality || bookingVenue.city || bookingVenue.address || 'Location'}

🪑 Cabin: ${booking.cabinNumber || 'N/A'}
📅 Valid: ${formatToIST(booking.startDate)} to ${formatToIST(booking.endDate)}
⏰ Days Left: ${daysRemaining}

✨ View on StudySpace App (studyspaceapp.in)`;
                                                                
                                                                const shareData = {
                                                                    title: `My Booking at ${bookingVenue.name}`,
                                                                    text: bookingDetails
                                                                };
                                                                
                                                                try {
                                                                    // Try Web Share API first (mobile)
                                                                    if (navigator.share && navigator.canShare && navigator.canShare(shareData)) {
                                                                        await navigator.share(shareData);
                                                                        toast.success('Booking details shared successfully!');
                                                                    } else {
                                                                        // Fallback to clipboard
                                                                        await navigator.clipboard.writeText(bookingDetails);
                                                                        toast.success('Booking details copied to clipboard!');
                                                                    }
                                                                } catch (error: any) {
                                                                    // User cancelled or error occurred
                                                                    if (error.name !== 'AbortError') {
                                                                        // Try clipboard as last resort
                                                                        try {
                                                                            await navigator.clipboard.writeText(bookingDetails);
                                                                            toast.success('Booking details copied to clipboard!');
                                                                        } catch {
                                                                            toast.error('Unable to share. Please try again.');
                                                                        }
                                                                    }
                                                                }
                                                            }}
                                                            className="bg-white/20 hover:bg-white/30 backdrop-blur-sm px-3 py-2 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 border border-white/20"
                                                        >
                                                            <Share2 className="w-3.5 h-3.5" />
                                                            <span>Share</span>
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Actions */}
                                                <div className="w-full md:w-auto flex flex-row md:flex-col gap-2">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="bg-white text-indigo-900 border-none hover:bg-indigo-50 flex-1 md:flex-none justify-center"
                                                        onClick={() => openExtendModal(booking)}
                                                    >
                                                        Extend Plan
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="text-white/80 hover:text-white hover:bg-white/10 flex-1 md:flex-none justify-center"
                                                        onClick={() => setIsDetailsModalOpen(true)}
                                                    >
                                                        Details
                                                    </Button>
                                                </div>
                                            </div>
                                        </Card>
                                    );
                                })}
                            </div>
                        ) : (
                            <Card className="bg-orange-50 border-orange-200 p-8 text-center border-dashed border-2">
                                <div className="max-w-md mx-auto">
                                    <div className="mx-auto h-12 w-12 bg-orange-100 rounded-full flex items-center justify-center mb-4">
                                        <AlertCircle className="h-6 w-6 text-orange-600" />
                                    </div>
                                    <h3 className="text-lg font-medium text-orange-900">No Active Bookings</h3>
                                    <p className="text-orange-700 mt-2 mb-6 text-sm">
                                        You don't have any active bookings at the moment. Browse our reading rooms to find your perfect study spot.
                                    </p>
                                    <Link to="/student/book">
                                        <Button variant="primary">Browse Reading Rooms</Button>
                                    </Link>
                                </div>
                            </Card>
                        )}
                    </div>

                    {/* In-Feed Native Ad */}
                    <AdBanner ad={targetedAd} variant="banner" />

                    {/* Booking History */}
                    <div>
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-900">Recent History</h2>
                            <Link to="/student/payments">
                                <Button variant="ghost" size="sm">View All</Button>
                            </Link>
                        </div>
                        <Card className="overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead className="bg-gray-50">
                                        <tr>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cabin</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody className="bg-white divide-y divide-gray-200">
                                        {bookingHistory.length > 0 ? (
                                            bookingHistory.map((booking, index) => (
                                                <tr key={`${booking.id}-${index}`} className="hover:bg-gray-50">
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatToIST(booking.startDate)}</td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">Cabin {booking.cabinNumber}</td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">₹{booking.amount}</td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <Badge variant={booking.status === 'ACTIVE' ? 'success' : 'warning'}>{booking.status}</Badge>
                                                    </td>
                                                </tr>
                                            ))
                                        ) : (
                                            <tr>
                                                <td colSpan={4} className="px-6 py-8 text-center text-sm text-gray-500">No history found.</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    </div>

                    {/* Featured Listings - MOVED HERE (Full Width) */}
                    <div className="overflow-visible">
                        {(() => {
                            // CORE BUSINESS RULE: Featured status is derived from APPROVED BoostRequests
                            // Fetched from public backend API - Super Admin is the source of truth

                            // Build featured venues based on approved boosts from public API
                            // Deduplicate by venueId - only show each venue once even if multiple boosts
                            const uniqueListings = featuredListings.filter((listing, idx, arr) =>
                                arr.findIndex(l => l.venueId === listing.venueId) === idx
                            );

                            const featuredVenues = uniqueListings.map(featured => {
                                if (featured.venueType === 'reading_room') {
                                    const room = state.readingRooms.find(r => r.id === featured.venueId);
                                    return room ? { ...room, type: 'Reading Room' as const, venueName: featured.venueName } : null;
                                } else {
                                    const acc = state.accommodations.find(a => a.id === featured.venueId);
                                    return acc ? { ...acc, type: 'PG / Hostel' as const, venueName: featured.venueName } : null;
                                }
                            }).filter(Boolean).slice(0, 10);

                            if (featuredVenues.length === 0) return null;

                            return (
                                <div>
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="font-bold text-gray-900 text-lg">
                                            Featured Listings
                                        </h3>
                                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest bg-gray-100 px-2 py-1 rounded border border-gray-200">Sponsored</span>
                                    </div>

                                    {/* Horizontal Carousel Container */}
                                    <div
                                        className="flex overflow-x-auto snap-x snap-mandatory gap-4 pb-4 -mx-4 px-4 md:mx-0 md:px-0 hide-scrollbar"
                                        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
                                    >
                                        {featuredVenues.map((venue, index) => (
                                            <div
                                                key={`${venue.id}-${index}`}
                                                className="snap-center flex-shrink-0 w-[280px] bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden group hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1"
                                            >
                                                {/* Image Area */}
                                                <div className="relative h-40 w-full bg-gray-200 overflow-hidden">
                                                    <img
                                                        src={venue.imageUrl}
                                                        alt={venue.name}
                                                        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                                                        onError={(e) => {
                                                            const target = e.target as HTMLImageElement;
                                                            target.onerror = null;
                                                            target.src = 'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&q=80&w=800';
                                                        }}
                                                    />
                                                    {/* Badges */}
                                                    <div className="absolute top-3 left-3">
                                                        <span className="bg-yellow-400 text-yellow-950 text-[10px] font-extrabold px-2.5 py-1 rounded-md shadow-sm tracking-wide">
                                                            FEATURED
                                                        </span>
                                                    </div>
                                                    <div className="absolute top-3 right-3">
                                                        <span className="text-[10px] font-bold text-white bg-black/40 backdrop-blur-md px-2.5 py-1 rounded-md border border-white/10">
                                                            {venue.type === 'Reading Room' ? 'Reading Room' : 'PG / Hostel'}
                                                        </span>
                                                    </div>
                                                </div>

                                                {/* Body Content */}
                                                <div className="p-4 flex flex-col h-[150px] justify-between">
                                                    <div>
                                                        <h4 className="font-bold text-gray-900 text-lg truncate leading-tight mb-1.5" title={venue.name}>{venue.name}</h4>
                                                        <div className="flex items-start text-sm text-gray-500">
                                                            <MapPin className="w-3.5 h-3.5 mr-1.5 mt-0.5 flex-shrink-0 text-gray-400" />
                                                            <span className="line-clamp-2 text-xs leading-relaxed">{venue.locality}, {venue.city || 'City'}</span>
                                                        </div>
                                                    </div>

                                                    <Link to={venue.type === 'Reading Room' ? `/student/reading-room/${venue.id}` : `/student/accommodation/${venue.id}`} className="mt-3 block">
                                                        <Button className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow-md shadow-indigo-100 transition-all hover:shadow-indigo-200 active:scale-[0.98]">
                                                            View Details
                                                        </Button>
                                                    </Link>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                </div>

                {/* Sidebar Column */}
                <div className="space-y-6">

                    {/* Recent Activity Timeline */}
                    <Card className="p-5">
                        <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
                            <Clock className="w-4 h-4 mr-2 text-indigo-600" /> Recent Activity
                        </h3>
                        <div className="space-y-4">
                            {isLoading ? (
                                <>
                                    <SkeletonCard variant="timeline" />
                                    <SkeletonCard variant="timeline" />
                                    <SkeletonCard variant="timeline" />
                                </>
                            ) : bookingHistory.length > 0 ? (
                                bookingHistory.slice(0, 5).map((booking, index) => {
                                    const bookingCabin = state.cabins.find(c => c.id === booking.cabinId);
                                    const bookingVenue = bookingCabin
                                        ? state.readingRooms.find(r => r.id === bookingCabin.readingRoomId)
                                        : null;

                                    return (
                                        <div key={`activity-${booking.id}-${index}`} className="flex gap-3 relative">
                                            {/* Timeline Line */}
                                            {index < Math.min(bookingHistory.length, 5) - 1 && (
                                                <div className="absolute left-4 top-8 bottom-0 w-px bg-gray-200"></div>
                                            )}

                                            {/* Icon */}
                                            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${booking.status === 'ACTIVE' ? 'bg-green-100' :
                                                booking.status === 'EXPIRED' ? 'bg-gray-100' :
                                                    'bg-blue-100'
                                                }`}>
                                                <CheckCircle className={`w-4 h-4 ${booking.status === 'ACTIVE' ? 'text-green-600' :
                                                    booking.status === 'EXPIRED' ? 'text-gray-600' :
                                                        'text-blue-600'
                                                    }`} />
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1">
                                                <p className="text-sm font-medium text-gray-900">
                                                    {booking.status === 'ACTIVE' ? 'Active Booking' :
                                                        booking.status === 'EXPIRED' ? 'Booking Expired' :
                                                            'Booking Confirmed'}
                                                </p>
                                                <p className="text-xs text-gray-500 mt-0.5">
                                                    {bookingVenue?.name || 'Unknown Venue'} • Cabin {booking.cabinNumber}
                                                </p>
                                                <p className="text-xs text-gray-400 mt-1">
                                                    {formatToIST(booking.startDate)}
                                                </p>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="text-center py-6">
                                    <div className="mx-auto h-10 w-10 bg-gray-100 rounded-full flex items-center justify-center mb-3">
                                        <Clock className="h-5 w-5 text-gray-400" />
                                    </div>
                                    <p className="text-sm text-gray-500">No activity yet</p>
                                    <p className="text-xs text-gray-400 mt-1">Your bookings will appear here</p>
                                </div>
                            )}
                        </div>
                    </Card>

                    {/* Waitlist Card */}
                    {myWaitlist.length > 0 && (
                        <Card className="p-5 border-amber-200 bg-amber-50">
                            <h3 className="font-semibold text-amber-900 mb-3 flex items-center">
                                <Bell className="w-4 h-4 mr-2" /> My Waitlist
                            </h3>
                            <div className="space-y-2">
                                {myWaitlist.map(entry => {
                                    const cabin = state.cabins.find(c => c.id === entry.cabinId);
                                    return (
                                        <div key={entry.id} className="flex justify-between items-center bg-white p-3 rounded-lg shadow-sm border border-amber-100">
                                            <span className="text-sm font-medium text-gray-700">Cabin {cabin?.number || 'Unknown'}</span>
                                            <Badge variant="warning">Waiting</Badge>
                                        </div>
                                    );
                                })}
                            </div>
                            <p className="text-xs text-amber-600 mt-3">We'll notify you as soon as a spot opens up.</p>
                        </Card>
                    )}

                    {/* Sidebar Ad */}
                    <div className="hidden lg:block">
                        <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Partner Offer</div>
                        <AdBanner ad={popupAd} variant="card" />
                    </div>

                    {/* Rating Prompt Card */}
                    {venueToReview && !hasReviewed ? (
                        <Card className="p-6 bg-gradient-to-br from-yellow-50 to-orange-50 border-yellow-100 relative overflow-hidden group">
                            <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-yellow-100 rounded-full opacity-50 group-hover:scale-150 transition-transform duration-500"></div>

                            <div className="relative z-10">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="font-bold text-yellow-900">Rate Your Experience</h3>
                                    <div className="bg-white p-1.5 rounded-full shadow-sm">
                                        <Star className="h-5 w-5 text-yellow-500 fill-yellow-500" />
                                    </div>
                                </div>
                                <p className="text-sm text-yellow-800 mb-4 leading-relaxed">
                                    How is your study time at <strong>{venueToReview.name}</strong>?
                                </p>
                                <Button
                                    className="w-full bg-white text-yellow-700 border border-yellow-200 hover:bg-yellow-50 hover:border-yellow-300 shadow-sm"
                                    onClick={() => setIsReviewModalOpen(true)}
                                >
                                    Write a Review
                                </Button>
                            </div>
                        </Card>
                    ) : venueToReview && hasReviewed ? (
                        <Card className="p-6 bg-gray-50 border-gray-100 relative overflow-hidden">
                            <div className="relative z-10">
                                <div className="flex items-center justify-between mb-3">
                                    <h3 className="font-bold text-gray-900">Experience Rated</h3>
                                    <div className="bg-green-100 p-1.5 rounded-full shadow-sm">
                                        <CheckCircle className="h-5 w-5 text-green-600" />
                                    </div>
                                </div>
                                <p className="text-sm text-gray-600 mb-2">
                                    Thanks for reviewing <strong>{venueToReview.name}</strong>.
                                </p>
                                <div className="text-xs text-green-600 font-semibold flex items-center">
                                    <CheckCircle className="w-3 h-3 mr-1" /> Review Submitted
                                </div>
                            </div>
                        </Card>
                    ) : null}




                    <Card className="p-5 bg-purple-50 border-purple-100">
                        <h3 className="font-semibold text-purple-900 mb-2">Need Help?</h3>
                        <p className="text-sm text-purple-700 mb-4">Contact support for any booking or subscription issues.</p>
                        <Link to="/support">
                            <Button variant="secondary" size="sm" className="w-full">
                                Contact Support
                            </Button>
                        </Link>
                    </Card>
                </div>
            </div>

            {/* Review Modal */}
            <Modal
                isOpen={isReviewModalOpen}
                onClose={() => setIsReviewModalOpen(false)}
                title="Rate & Review"
            >
                <div className="space-y-6 py-2">
                    <div className="text-center">
                        <p className="text-gray-500 text-sm mb-4">How would you rate your experience at <br /><span className="font-semibold text-gray-900">{venueToReview?.name}</span>?</p>

                        {/* Interactive Stars */}
                        <div className="flex justify-center gap-3 mb-2">
                            {[1, 2, 3, 4, 5].map((star) => (
                                <button
                                    key={star}
                                    type="button"
                                    onMouseEnter={() => setReviewRating(star)}
                                    onClick={() => setReviewRating(star)}
                                    className="focus:outline-none transition-transform active:scale-95 hover:scale-110"
                                >
                                    <Star
                                        className={`w-10 h-10 transition-colors duration-200 ${star <= reviewRating
                                            ? 'text-yellow-400 fill-yellow-400 drop-shadow-sm'
                                            : 'text-gray-200 fill-gray-50'
                                            }`}
                                    />
                                </button>
                            ))}
                        </div>

                        {/* Rating Label Animation */}
                        <p className="h-6 font-bold text-lg text-yellow-600 animate-in fade-in slide-in-from-bottom-1 duration-200 key={reviewRating}">
                            {getRatingLabel(reviewRating)}
                        </p>
                    </div>

                    <div className="bg-gray-50 p-4 rounded-lg border border-gray-100">
                        <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                            Written Feedback
                        </label>
                        <textarea
                            className="w-full p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 min-h-[120px] text-sm resize-none"
                            placeholder="What did you like the most? What could be improved?"
                            value={reviewComment}
                            onChange={(e) => setReviewComment(e.target.value)}
                        />
                        <p className="text-right text-xs text-gray-400 mt-1">
                            {reviewComment.length}/500
                        </p>
                    </div>

                    <div className="pt-2 flex gap-3">
                        <Button variant="ghost" className="flex-1" onClick={() => setIsReviewModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button className="flex-1" size="lg" onClick={handleSubmitReview} isLoading={isSubmittingReview}>
                            Submit Review
                        </Button>
                    </div>
                </div>
            </Modal>

            {/* Extend Plan Modal - Uses SELECTED booking */}
            <Modal
                isOpen={isExtendModalOpen}
                onClose={closeExtendModal}
                title="Extend Subscription"
            >
                {!extensionSuccess ? (
                    selectedBookingForExtend ? (() => {
                        // Get cabin for selected booking (not activeBooking)
                        const selectedCabin = state.cabins.find(c => c.id === selectedBookingForExtend.cabinId);
                        const selectedVenue = selectedCabin
                            ? state.readingRooms.find(r => r.id === selectedCabin.readingRoomId)
                            : null;
                        const cabinPrice = selectedCabin?.price || 1500;

                        return (
                            <div className="space-y-6">
                                {/* Show which booking is being extended */}
                                <div className="bg-indigo-50 p-4 rounded-lg">
                                    <div className="text-xs text-indigo-600 mb-1 font-semibold">EXTENDING</div>
                                    <div className="text-lg font-bold text-indigo-900">{selectedVenue?.name || 'Unknown Venue'}</div>
                                    <div className="text-sm text-indigo-700">Cabin {selectedBookingForExtend.cabinNumber}</div>
                                    <div className="text-sm text-indigo-600 mt-2">
                                        Current End Date: <strong>{formatToIST(selectedBookingForExtend.endDate)}</strong>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-3">Extend By</label>
                                    <div className="grid grid-cols-3 gap-3">
                                        {[1, 3, 6].map(m => (
                                            <button
                                                key={m}
                                                onClick={() => setExtensionDuration(m)}
                                                className={`py-3 px-1 text-sm font-medium rounded-lg border transition-all ${extensionDuration === m
                                                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600'
                                                    : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                                                    }`}
                                            >
                                                <span className="block text-lg font-bold">{m}</span>
                                                Month{m > 1 ? 's' : ''}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="bg-gray-50 p-4 rounded-lg flex justify-between items-center">
                                    <span className="text-gray-600 font-medium">Total to Pay</span>
                                    <span className="text-2xl font-bold text-gray-900">₹{cabinPrice * extensionDuration}</span>
                                </div>

                                <div className="pt-2 flex gap-3">
                                    <Button variant="ghost" className="flex-1" onClick={closeExtendModal} disabled={isProcessingExtension}>Cancel</Button>
                                    <Button className="flex-1" size="lg" onClick={handleExtendSubmit} isLoading={isProcessingExtension}>
                                        Pay & Extend
                                    </Button>
                                </div>
                            </div>
                        );
                    })() : <div>Error loading plan details.</div>
                ) : (
                    <div className="text-center py-6 space-y-4">
                        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100">
                            <CheckCircle className="h-10 w-10 text-green-600" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-gray-900">Extended Successfully!</h3>
                            <p className="text-sm text-gray-500 mt-2">
                                Your booking for Cabin {selectedBookingForExtend?.cabinNumber} has been extended.
                            </p>
                        </div>
                        <Button onClick={closeExtendModal} className="w-full">Close</Button>
                    </div>
                )}
            </Modal>

            {/* View Details Modal */}
            <Modal
                isOpen={isDetailsModalOpen}
                onClose={() => setIsDetailsModalOpen(false)}
                title="Booking Details"
            >
                {activeBooking && activeVenue ? (
                    <div className="space-y-6">
                        {/* Image Header */}
                        <div className="h-32 w-full rounded-lg overflow-hidden bg-gray-200 relative">
                            <img
                                src={activeVenue.imageUrl}
                                alt={activeVenue.name}
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                    const target = e.target as HTMLImageElement;
                                    target.onerror = null;
                                    target.src = 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?auto=format&fit=crop&q=80&w=800';
                                }}
                            />
                            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-3">
                                <h3 className="text-white font-bold truncate">{activeVenue.name}</h3>
                            </div>
                        </div>

                        {/* Info Grid */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="p-3 bg-gray-50 rounded-lg">
                                <span className="text-xs text-gray-500 uppercase font-bold block mb-1">Cabin</span>
                                <span className="text-lg font-bold text-gray-900">{activeBooking.cabinNumber}</span>
                            </div>
                            <div className="p-3 bg-gray-50 rounded-lg">
                                <span className="text-xs text-gray-500 uppercase font-bold block mb-1">Status</span>
                                <Badge variant="success">Active</Badge>
                            </div>
                            <div className="p-3 bg-gray-50 rounded-lg col-span-2">
                                <span className="text-xs text-gray-500 uppercase font-bold block mb-1">Duration</span>
                                <div className="flex justify-between items-center text-sm font-medium text-gray-900">
                                    <span>{formatToISTWithTime(activeBooking.startDate)}</span>
                                    <ArrowRight className="w-4 h-4 text-gray-400" />
                                    <span>{formatToISTWithTime(activeBooking.endDate)}</span>
                                </div>
                            </div>
                        </div>

                        <div className="border-t border-gray-100 pt-4">
                            <div className="flex items-start gap-3 mb-3">
                                <MapPin className="w-5 h-5 text-gray-400 flex-shrink-0 mt-0.5" />
                                <div>
                                    <p className="text-sm font-medium text-gray-900">Address</p>
                                    <p className="text-sm text-gray-500">{activeVenue.address}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <Phone className="w-5 h-5 text-gray-400 flex-shrink-0" />
                                <div>
                                    <p className="text-sm font-medium text-gray-900">Contact</p>
                                    <p className="text-sm text-gray-500">{activeVenue.contactPhone}</p>
                                </div>
                            </div>
                        </div>

                        {/* Access Code / QR */}
                        <div className="bg-white border-2 border-dashed border-gray-200 rounded-xl p-4 flex flex-col items-center justify-center text-center">
                            <div className="bg-gray-900 p-3 rounded-lg mb-2">
                                <QrCode className="w-20 h-20 text-white" />
                            </div>
                            <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Access QR Code</p>
                            <p className="text-[10px] text-gray-400 mt-1">Scan at entry</p>
                        </div>

                        <div className="pt-2">
                            <Button variant="outline" className="w-full" onClick={() => setIsDetailsModalOpen(false)}>Close</Button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4 py-4">
                        {activeBooking ? (
                            <>
                                <div className="text-center">
                                    <p className="text-lg font-semibold text-gray-900">Your Booking</p>
                                    <p className="text-sm text-gray-500">Cabin {activeBooking.cabinNumber || 'N/A'}</p>
                                </div>
                                <div className="grid grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <p className="text-gray-500">Start Date</p>
                                        <p className="font-medium">{new Date(activeBooking.startDate).toLocaleDateString()}</p>
                                    </div>
                                    <div>
                                        <p className="text-gray-500">End Date</p>
                                        <p className="font-medium">{new Date(activeBooking.endDate).toLocaleDateString()}</p>
                                    </div>
                                    <div>
                                        <p className="text-gray-500">Amount Paid</p>
                                        <p className="font-medium">₹{activeBooking.amount?.toLocaleString()}</p>
                                    </div>
                                    <div>
                                        <p className="text-gray-500">Status</p>
                                        <p className="font-medium text-green-600">{activeBooking.status}</p>
                                    </div>
                                </div>
                                <Button variant="outline" className="w-full mt-4" onClick={() => setIsDetailsModalOpen(false)}>Close</Button>
                            </>
                        ) : (
                            <p className="text-gray-500 text-center">No active booking found</p>
                        )}
                    </div>
                )}
            </Modal>

            {/* Special Offer "Popup" Modal */}
            <Modal
                isOpen={showWelcomeAd}
                onClose={() => setShowWelcomeAd(false)}
                title="Student Perk Unlocked!"
            >
                <div className="text-center py-4">
                    <div className="mx-auto w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mb-4 animate-bounce">
                        <Sparkles className="w-8 h-8 text-yellow-600" />
                    </div>
                    <p className="text-gray-600 mb-6">
                        Thanks for using StudySpace. As a valued student member, here is a special offer just for you.
                    </p>
                    <AdBanner ad={popupAd} variant="card" onClose={() => setShowWelcomeAd(false)} />
                    <Button variant="ghost" onClick={() => setShowWelcomeAd(false)} className="mt-4 text-sm text-gray-400">
                        Maybe later
                    </Button>
                </div>
            </Modal>

        </div>
    );
};
