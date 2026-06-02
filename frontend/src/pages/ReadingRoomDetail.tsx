import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { AppState, ReadingRoom, Cabin, CabinStatus, User, BookingDurationType } from '../types';
import { Button, Card, Badge, Modal, LiveIndicator } from '../components/UI';
import { waitlistService } from '../services/waitlistService';
import api from '../services/api';
import { toast } from 'react-hot-toast';
import { ImageGallery } from '../components/ImageGallery';
import { SeatMap } from '../components/SeatMap';
import { VenueTrustSignals } from '../components/VenueTrustSignals';
import { AdBanner } from '../components/AdBanner';
import { getTargetedAd } from '../services/adService';
import { FavoriteButton } from '../components/FavoriteButton';
import { RecommendationRail } from '../components/RecommendationRail';
import Map from '../components/Map';
import { 
  getAvailableDurations, 
  getDurationPrice, 
  formatDurationLabel, 
  formatPrice,
  calculateEndDate,
  getDefaultDuration
} from '../utils/bookingDurations';

import {
    ArrowLeft, MapPin, Phone, Star, Clock, Wifi, Zap,
    CheckCircle, BellRing, Layers, Building2, MessageCircle,
    ChevronDown, ChevronUp
} from 'lucide-react';

interface ReadingRoomDetailProps {
    state: AppState;
    user: User;
    onBookCabin: (cabinId: string, durationMonths: number) => Promise<void>;
    onJoinWaitlist: (cabinId: string) => void;
}

export const ReadingRoomDetail: React.FC<ReadingRoomDetailProps> = ({
    state,
    user,
    onBookCabin,
    onJoinWaitlist
}) => {
    const { roomId } = useParams<{ roomId: string }>();
    const navigate = useNavigate();
    const location = useLocation();

    // Auto-select logic from navigation state
    useEffect(() => {
        if (location.state && location.state.autoOpenBooking && location.state.autoSelectCabinId) {
            const cabinId = location.state.autoSelectCabinId;
            const cabin = state.cabins.find(c => c.id === cabinId);
            if (cabin) {
                setSelectedCabin(cabin);
                setPaymentStep('details');
                setIsBookingModalOpen(true);
                // Clear state to prevent reopening on generic refresh (optional)
                window.history.replaceState({}, document.title);
            }
        }
    }, [location.state, state.cabins]);

    // Find the venue
    const venue = state.readingRooms.find(r => r.id === roomId);
    const venueCabins = state.cabins.filter(c => c.readingRoomId === roomId);

    // State
    const [selectedCabin, setSelectedCabin] = useState<Cabin | null>(null);
    const [activeFloor, setActiveFloor] = useState<number  | 'All'>('All');
    const [selectedDuration, setSelectedDuration] = useState<BookingDurationType>('1_MONTH');
    const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
    const [isWaitlistModalOpen, setIsWaitlistModalOpen] = useState(false);
    const [paymentStep, setPaymentStep] = useState<'details' | 'payment' | 'success'>('details');
    const [showAmenities, setShowAmenities] = useState(false);
    const [ads, setAds] = useState<any[]>([]);

    // Parse venue images
    const venueImages = useMemo(() => {
        console.log('ReadingRoomDetail - Raw venue.images:', venue?.images);
        console.log('ReadingRoomDetail - venue.imageUrl:', venue?.imageUrl);
        
        if (!venue?.images) {
            // Fallback to imageUrl if images is empty
            return venue?.imageUrl ? [venue.imageUrl] : [];
        }
        
        // If images is already an array, use it directly
        if (Array.isArray(venue.images)) {
            console.log('ReadingRoomDetail - images is array:', venue.images);
            return venue.images.length > 0 ? venue.images : (venue.imageUrl ? [venue.imageUrl] : []);
        }
        
        try {
            // Try to parse as JSON array
            const parsed = JSON.parse(venue.images);
            console.log('ReadingRoomDetail - parsed images:', parsed);
            return Array.isArray(parsed) && parsed.length > 0 ? parsed : (venue.imageUrl ? [venue.imageUrl] : []);
        } catch {
            // If parsing fails, check if it's a stringified URL or an actual URL
            // If images is a string that looks like a URL, return it as an array
            if (typeof venue.images === 'string' && (venue.images.startsWith('http') || venue.images.startsWith('data:'))) {
                console.log('ReadingRoomDetail - images is URL string');
                return [venue.images];
            }
            // Final fallback to imageUrl
            console.log('ReadingRoomDetail - fallback to imageUrl');
            return venue?.imageUrl ? [venue.imageUrl] : [];
        }
    }, [venue]);

    // Get available floors
    const availableFloors = useMemo(() => {
        const floors = new Set(venueCabins.map(c => c.floor));
        return Array.from(floors).sort((a: number, b: number) => a - b);
    }, [venueCabins]);

    // Get venue rating
    const venueRating = useMemo(() => {
        const reviews = state.reviews.filter(r => r.readingRoomId === roomId);
        if (reviews.length === 0) return { average: 0, count: 0 };
        const total = reviews.reduce((acc, curr) => acc + curr.rating, 0);
        return { average: total / reviews.length, count: reviews.length };
    }, [state.reviews, roomId]);

    // Calculate active students (unique users with active bookings at this venue)
    // Fetch from API instead of calculating from local state (which only has user's own bookings)
    const [activeStudents, setActiveStudents] = useState(0);
    
    useEffect(() => {
        const fetchActiveStudents = async () => {
            if (!roomId) return;
            try {
                // Use the shared axios instance — its baseURL is set correctly
                // for both dev (http://localhost:8000) and prod (empty string
                // → relative URL → nginx proxies to backend). Raw fetch() with
                // `import.meta.env.VITE_API_BASE_URL` shipped "undefined" into
                // the prod bundle when the env var wasn't set at build time,
                // causing the SPA fallback to return HTML and JSON parsing
                // to fail with "Unexpected token '<'".
                const { data } = await api.get(`/api/reading-rooms/${roomId}/active-students`);
                setActiveStudents(data.active_students || 0);
            } catch (error) {
                console.error('Failed to fetch active students:', error);
            }
        };
        fetchActiveStudents();
    }, [roomId]);

    // Calculate months on platform
    const monthsOnPlatform = useMemo(() => {
        if (!venue?.createdAt) return 0;
        const created = new Date(venue.createdAt);
        const now = new Date();
        const diffMonths = (now.getFullYear() - created.getFullYear()) * 12 + 
                          (now.getMonth() - created.getMonth());
        return Math.max(0, diffMonths);
    }, [venue?.createdAt]);

    // User waitlist entries
    const userWaitlist = useMemo(() => {
        return state.waitlist
            .filter(w => w.userId === user.id && w.readingRoomId === roomId)
            .map(w => w.cabinId);
    }, [state.waitlist, user.id, roomId]);

    // Fetch Ads
    useEffect(() => {
        const fetchAds = async () => {
            try {
                const { adService } = await import('../services/adService');
                const fetchedAds = await adService.getAds();
                setAds(fetchedAds);
            } catch (e) {
                console.error("ReadingRoomDetail: Failed to load ads", e);
            }
        };
        fetchAds();
    }, []);

    const successAd = useMemo(() => getTargetedAd(ads, user.role, true, 'BOOKING_SUCCESS'), [ads, user.role]);

    // Handlers
    const handleSelectCabin = (cabin: Cabin) => {
        if (cabin.status === CabinStatus.MAINTENANCE) return;

        setSelectedCabin(cabin);

        if (cabin.status === CabinStatus.AVAILABLE) {
            // Set default duration based on venue's configuration
            if (venue) {
                const defaultDuration = getDefaultDuration(venue.allowedBookingDurations);
                setSelectedDuration(defaultDuration);
            }
            // Ready to book
        } else if (cabin.status === CabinStatus.OCCUPIED) {
            // Check if already on waitlist (local state check + maybe visual indicator)
            setIsWaitlistModalOpen(true);
        } else if (cabin.status === CabinStatus.RESERVED) {
            // Check if held by ME
            // Note: Frontend types need to track heldBy or we check a separate 'myHolds' list
            // For now, assuming backend logic or detailed cabin object has `heldByUserId`
            // If it's MY hold, allow booking!
            if ((cabin as any).held_by_user_id === user.id) {
                // Set default duration
                if (venue) {
                    const defaultDuration = getDefaultDuration(venue.allowedBookingDurations);
                    setSelectedDuration(defaultDuration);
                }
                // Open booking modal immediately!
                setPaymentStep('details');
                setIsBookingModalOpen(true);
            } else {
                setIsWaitlistModalOpen(true);
            }
        }
    };

    const handleProceedToReview = () => {
        if (selectedCabin && selectedCabin.status === CabinStatus.AVAILABLE) {
            // Set default duration
            if (venue) {
                const defaultDuration = getDefaultDuration(venue.allowedBookingDurations);
                setSelectedDuration(defaultDuration);
            }
            setPaymentStep('details');
            setIsBookingModalOpen(true);
        }
    };

    const handlePayment = async () => {
        if (!selectedCabin || !venue) return;

        setPaymentStep('payment');

        try {
            // Get the price for selected duration
            const durationPrice = getDurationPrice(venue.durationPrices, selectedDuration, venue.priceStart);
            if (!durationPrice) {
                alert('Price not configured for this duration. Please contact the venue owner.');
                setPaymentStep('details');
                return;
            }

            // 1. Hold the cabin first (create booking).
            // Backend calculates dates and amount automatically based on
            // duration_type. Go through the shared `api` axios instance so
            // baseURL + auth interceptor are handled centrally — the prior
            // raw fetch had `${import.meta.env.VITE_API_BASE_URL ||
            // 'http://localhost:8000'}` which baked "http://localhost:8000"
            // into the production bundle when the env var was unset at
            // build time, causing every booking to ERR_CONNECTION_REFUSED.
            let booking: any;
            try {
                const res = await api.post(
                    `/api/bookings/hold?cabin_id=${selectedCabin.id}&duration_type=${selectedDuration}`,
                );
                booking = res.data;
            } catch (err: any) {
                const detail = err?.response?.data?.detail || 'Failed to hold cabin';
                console.error('[BOOKING] Hold failed:', {
                    status: err?.response?.status,
                    error: err?.response?.data,
                });
                throw new Error(detail);
            }
            const bookingId = booking.id;
            const totalAmount = booking.amount; // Use amount calculated by backend

            // 2. Create Razorpay Order
            const { paymentService } = await import('../services/paymentService');
            const orderData = await paymentService.createOrder(bookingId, totalAmount);

            // 🎭 DEMO MODE: Auto-complete payment instantly
            if (orderData.is_demo || orderData.razorpay_key_id === 'demo_key_id' || orderData.razorpay_key_id === 'your_razorpay_key_id') {
                toast.success('💳 DEMO MODE: Processing payment...', { duration: 2000 });
                
                // Simulate payment processing
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                try {
                    // Auto-verify with demo payment data
                    console.log('🔍 Verifying demo payment with:', {
                        razorpay_order_id: orderData.order_id,
                        razorpay_payment_id: `pay_demo_${Date.now()}`,
                        booking_id: bookingId
                    });
                    
                    await paymentService.verifyPayment({
                        razorpay_order_id: orderData.order_id,
                        razorpay_payment_id: `pay_demo_${Date.now()}`,
                        razorpay_signature: `sig_demo_${Date.now()}`,
                        booking_id: bookingId
                    });

                    setPaymentStep('success');
                    toast.success('✅ Booking confirmed successfully!');
                    
                    // Refresh page to update cabin status and bookings
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                    return;
                } catch (error: any) {
                    console.error('Demo payment failed:', error);
                    console.error('Error response:', error.response?.data);

                    // FALLBACK — when verify returns 500, check whether the
                    // booking is ACTUALLY paid on the server. A long-standing
                    // backend bug made verify return 500 even when the
                    // booking had been successfully marked PAID and an
                    // invoice issued (a downstream side-effect was throwing
                    // 7s2a after the critical commit). The user would see
                    // "Booking failed" while their card was actually charged
                    // and the cabin booked. Re-checking the status here
                    // makes the UI honest: if the backend says PAID, we
                    // treat it as success regardless of what verify said.
                    if (error?.response?.status === 500) {
                        try {
                            const { default: api } = await import('../services/api');
                            const status = await api.get(`/razorpay/status/${bookingId}`);
                            if (status.data?.payment_status === 'PAID') {
                                console.warn('[booking] verify returned 500 but status shows PAID — treating as success');
                                setPaymentStep('success');
                                toast.success('✅ Booking confirmed successfully!');
                                setTimeout(() => { window.location.reload(); }, 2000);
                                return;
                            }
                        } catch (_) {
                            // Fall through to normal error display.
                        }
                    }

                    // Extract error message from Pydantic validation errors (array)
                    let errorMessage = 'Booking failed. Please try again.';
                    if (error.response?.data?.detail) {
                        if (Array.isArray(error.response.data.detail)) {
                            errorMessage = error.response.data.detail.map((e: any) => e.msg).join(', ');
                        } else if (typeof error.response.data.detail === 'string') {
                            errorMessage = error.response.data.detail;
                        }
                    }

                    toast.error(errorMessage);
                    setPaymentStep('details');
                    return;
                }
            }

            // 3. REAL PAYMENT MODE: Load Razorpay Script
            const loadRazorpayScript = () => {
                return new Promise((resolve) => {
                    if ((window as any).Razorpay) {
                        resolve(true);
                        return;
                    }
                    const script = document.createElement('script');
                    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
                    script.onload = () => resolve(true);
                    script.onerror = () => resolve(false);
                    document.body.appendChild(script);
                });
            };

            const isLoaded = await loadRazorpayScript();
            if (!isLoaded) {
                alert('Razorpay SDK failed to load. Please check your internet connection.');
                setPaymentStep('details');
                return;
            }

            // 4. Initialize Razorpay Options with UPI/GPay support
            const options = {
                key: orderData.razorpay_key_id,
                amount: orderData.amount,
                currency: orderData.currency,
                name: venue.name,
                description: `Cabin ${selectedCabin.number} - ${formatDurationLabel(selectedDuration)}`,
                image: venue.imageUrl || '/logo.png',
                order_id: orderData.order_id,
                handler: async function (response: any) {
                    try {
                        // Verify Payment on Backend
                        await paymentService.verifyPayment({
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_signature: response.razorpay_signature,
                            booking_id: bookingId
                        });

                        setPaymentStep('success');
                        toast.success('✅ Payment successful! Booking confirmed.');
                        
                        // Refresh page to update cabin status and bookings
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);

                    } catch (verificationError) {
                        console.error("Payment Verification Failed", verificationError);
                        toast.error("Payment verification failed. Please contact support if money was deducted.");
                        setPaymentStep('details');
                    }
                },
                prefill: {
                    name: state.currentUser?.name || '',
                    email: state.currentUser?.email || '',
                    contact: state.currentUser?.phone || ''
                },
                theme: {
                    color: '#4F46E5'
                },
                method: {
                    upi: true,      // Enable UPI (GPay, PhonePe, PayTM)
                    card: true,     // Enable Cards
                    netbanking: true, // Enable Net Banking
                    wallet: true    // Enable Wallets
                },
                modal: {
                    ondismiss: function () {
                        toast.error('Payment cancelled');
                        setPaymentStep('details');
                    }
                }
            };

            // 5. Open Razorpay
            const rzp = new (window as any).Razorpay(options);
            rzp.on('payment.failed', function (response: any) {
                toast.error(`Payment Failed: ${response.error.description}`);
                setPaymentStep('details');
            });
            rzp.open();

        } catch (error) {
            console.error("Payment Initiation Failed", error);
            toast.error("Could not initiate payment. Please try again.");
            setPaymentStep('details');
        }
    };

    const handleConfirmWaitlist = async () => {
        if (selectedCabin && venue) {
            try {
                await waitlistService.joinWaitlist(selectedCabin.id, venue.id);
                toast.success("Joined waitlist successfully! We'll notify you when it's free.");
                setIsWaitlistModalOpen(false);
                if (onJoinWaitlist) onJoinWaitlist(selectedCabin.id); // Refresh parent/state if needed
            } catch (error: any) {
                console.error("Failed to join waitlist:", error);
                toast.error(error.response?.data?.detail || "Failed to join waitlist. You might already be on it.");
                setIsWaitlistModalOpen(false);
            }
        }
    };

    // Not found state
    if (!venue) {
        return (
            <div className="max-w-4xl mx-auto px-4 py-12 text-center">
                <Building2 className="w-16 h-16 mx-auto text-gray-300 mb-4" />
                <h2 className="text-xl font-bold text-gray-700 mb-2">Reading Room Not Found</h2>
                <p className="text-gray-500 mb-6">The venue you're looking for doesn't exist or has been removed.</p>
                <Button onClick={() => navigate('/student/book')}>
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back to Venues
                </Button>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <LiveIndicator />

            {/* Hero Section with Image Gallery */}
            <div className="bg-gray-900">
                <div className="max-w-7xl mx-auto">
                    <ImageGallery
                        images={venueImages}
                        isVerified={venue.isVerified}
                        venueName={venue.name}
                    />
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                {/* Back Button */}
                <button
                    onClick={() => navigate('/student/book')}
                    className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> Back to Venues
                </button>

                {/* Venue Header */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                        <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                                <h1 className="text-2xl md:text-3xl font-bold text-gray-900">{venue.name}</h1>
                                {venue.isVerified && (
                                    <Badge variant="success" className="text-xs">
                                        <CheckCircle className="w-3 h-3 mr-1" /> Verified
                                    </Badge>
                                )}
                            </div>

                            <div className="flex items-start gap-2 text-gray-600 mb-3">
                                <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span className="text-sm">{venue.address}</span>
                            </div>

                            {/* Interactive Map */}
                            {venue.latitude && venue.longitude && (
                                <div className="mb-4">
                                    <Map
                                        center={{ lat: venue.latitude, lng: venue.longitude }}
                                        markers={[
                                            {
                                                id: venue.id,
                                                lat: venue.latitude,
                                                lng: venue.longitude,
                                                title: venue.name,
                                                address: venue.address,
                                            },
                                        ]}
                                        height="250px"
                                        className="rounded-xl overflow-hidden"
                                    />
                                </div>
                            )}

                            {/* Trust Signals */}
                            <VenueTrustSignals
                                isVerified={venue.isVerified}
                                activeSubscribers={activeStudents}
                                monthsOnPlatform={monthsOnPlatform}
                                rating={venueRating.average}
                                reviewCount={venueRating.count}
                                className="mb-4"
                            />

                            {/* Quick Stats */}
                            <div className="flex flex-wrap gap-4 text-sm">
                                <div className="flex items-center gap-1.5 text-gray-600">
                                    <Layers className="w-4 h-4" />
                                    <span>{availableFloors.length} Floor{availableFloors.length !== 1 ? 's' : ''}</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-gray-600">
                                    <Building2 className="w-4 h-4" />
                                    <span>{venueCabins.length} Seats</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-green-600 font-medium">
                                    <CheckCircle className="w-4 h-4" />
                                    <span>{venueCabins.filter(c => c.status === CabinStatus.AVAILABLE).length} Available</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-indigo-600 font-bold">
                                    Starts ₹{venue.priceStart}/mo
                                </div>
                            </div>
                        </div>

                        {/* Contact & Actions */}
                        <div className="flex flex-col sm:flex-row lg:flex-col gap-2">
                            <FavoriteButton
                                readingRoomId={venue.id}
                                size="md"
                            />
                            {venue.contactPhone && (
                                <a
                                    href={`tel:${venue.contactPhone}`}
                                    className="flex items-center justify-center gap-2 px-4 py-2 bg-green-50 text-green-700 rounded-lg border border-green-200 hover:bg-green-100 transition-colors"
                                >
                                    <Phone className="w-4 h-4" />
                                    <span className="text-sm font-medium">Call Venue</span>
                                </a>
                            )}
                            <button
                                onClick={() => navigate(`/student/messages?owner=${venue.ownerId}&venue=${venue.id}`)}
                                className="flex items-center justify-center gap-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100 transition-colors"
                            >
                                <MessageCircle className="w-4 h-4" />
                                <span className="text-sm font-medium">Message Owner</span>
                            </button>

                        </div>
                    </div>

                    {/* Amenities (Collapsible) */}
                    {venue.amenities && venue.amenities.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-gray-100">
                            <button
                                onClick={() => setShowAmenities(!showAmenities)}
                                className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
                            >
                                {showAmenities ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                Amenities ({venue.amenities.length})
                            </button>
                            {showAmenities && (
                                <div className="flex flex-wrap gap-2 mt-3 animate-in slide-in-from-top-2">
                                    {venue.amenities.map((amenity, i) => (
                                        <Badge key={i} variant="info" className="text-xs bg-gray-100">
                                            {amenity}
                                        </Badge>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Description */}
                    {venue.description && (
                        <p className="mt-4 text-sm text-gray-600 leading-relaxed">
                            {venue.description}
                        </p>
                    )}
                </div>

                {/* Seat Selection Section */}
                <Card className="p-0 overflow-hidden mb-6">
                    {/* Floor Tabs */}
                    <div className="bg-gray-50 border-b border-gray-200 px-4 pt-2 flex gap-2 overflow-x-auto custom-scrollbar">
                        <button
                            onClick={() => setActiveFloor('All')}
                            className={`px-4 py-3 text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${activeFloor === 'All'
                                ? 'border-indigo-600 text-indigo-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            <Layers className="w-4 h-4 inline mr-2" />
                            All Floors
                        </button>
                        {availableFloors.map(floor => (
                            <button
                                key={floor}
                                onClick={() => setActiveFloor(floor)}
                                className={`px-4 py-3 text-sm font-bold border-b-2 whitespace-nowrap transition-colors ${activeFloor === floor
                                    ? 'border-indigo-600 text-indigo-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700'
                                    }`}
                            >
                                Floor {floor}
                            </button>
                        ))}
                    </div>

                    {/* Seat Map */}
                    <div className="p-4 md:p-6">
                        <SeatMap
                            cabins={venueCabins}
                            selectedCabinId={selectedCabin?.id}
                            onSelectCabin={handleSelectCabin}
                            activeFloor={activeFloor}
                            userWaitlist={userWaitlist}
                        />
                    </div>
                </Card>

                {/* Selected Seat Summary (Desktop) */}
                {selectedCabin && selectedCabin.status === CabinStatus.AVAILABLE && (
                    <div className="hidden md:block bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-6">
                                <div className="bg-indigo-100 text-indigo-700 px-6 py-4 rounded-xl text-center">
                                    <div className="text-2xl font-bold">{selectedCabin.number}</div>
                                    <div className="text-xs font-medium">Floor {selectedCabin.floor}</div>
                                </div>
                                <div>
                                    <h3 className="font-semibold text-gray-900">Selected Seat</h3>
                                    <div className="flex gap-2 mt-1">
                                        {selectedCabin.amenities.slice(0, 3).map((a, i) => (
                                            <Badge key={i} variant="info" className="text-xs">{a}</Badge>
                                        ))}
                                    </div>
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-2xl font-bold text-gray-900">₹{selectedCabin.price}<span className="text-sm font-normal text-gray-500">/month</span></div>
                                <Button onClick={handleProceedToReview} size="lg" className="mt-2">
                                    Proceed to Book
                                </Button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Mobile Sticky CTA - ABOVE Bottom Navigation */}
            {selectedCabin && selectedCabin.status === CabinStatus.AVAILABLE && (
                <div className="md:hidden fixed bottom-16 left-0 right-0 bg-white border-t border-gray-200 shadow-[0_-4px_12px_rgba(0,0,0,0.15)] p-4 z-50 safe-area-bottom">
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                                <span className="font-bold text-lg text-indigo-600">{selectedCabin.number}</span>
                                <span className="text-sm text-gray-500">• Floor {selectedCabin.floor}</span>
                            </div>
                            <div className="text-lg font-bold text-gray-900">₹{selectedCabin.price}/mo</div>
                        </div>
                        <Button
                            onClick={handleProceedToReview}
                            size="lg"
                            className="flex-shrink-0 min-h-[48px] px-6 text-base font-bold shadow-lg"
                        >
                            Proceed →
                        </Button>
                    </div>
                </div>
            )}

            {/* Bottom Padding for Mobile CTA + Navigation */}
            {selectedCabin && selectedCabin.status === CabinStatus.AVAILABLE && (
                <div className="md:hidden h-40" />
            )}

            {/* Booking Modal */}
            <Modal
                isOpen={isBookingModalOpen}
                onClose={() => { setIsBookingModalOpen(false); setPaymentStep('details'); }}
                title={paymentStep === 'success' ? 'Booking Confirmed!' : 'Cabin Reservation'}
            >
                {selectedCabin && venue && paymentStep === 'details' && (
                    <div className="space-y-4">
                        <div className="bg-indigo-50 p-6 rounded-xl text-center border border-indigo-100">
                            <div className="text-xs text-indigo-400 font-bold uppercase mb-1">{venue.name}</div>
                            <div className="text-4xl font-bold text-indigo-700 mb-1">{selectedCabin.number}</div>
                            <div className="text-sm font-medium text-indigo-900 uppercase tracking-wide">Floor {selectedCabin.floor}</div>
                            <div className="mt-3 inline-flex items-center px-3 py-1 rounded-full bg-white text-indigo-600 text-sm font-bold shadow-sm">
                                ₹{selectedCabin.price}/month
                            </div>
                        </div>

                        <div className="bg-gray-50 p-4 rounded-lg">
                            <label className="block text-sm font-medium text-gray-700 mb-2">Select Duration</label>
                            {(() => {
                                const availableDurations = getAvailableDurations(
                                    venue.allowedBookingDurations,
                                    venue.durationPrices,
                                    venue.priceStart
                                );
                                
                                if (availableDurations.length === 0) {
                                    return (
                                        <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-md border border-amber-200">
                                            No booking durations are currently configured for this venue. Please contact the owner.
                                        </div>
                                    );
                                }

                                return (
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                        {availableDurations.map(durationType => {
                                            const price = getDurationPrice(venue.durationPrices, durationType, venue.priceStart);
                                            return (
                                                <button
                                                    key={durationType}
                                                    onClick={() => setSelectedDuration(durationType)}
                                                    className={`py-3 px-2 text-sm font-medium rounded-md border transition-all ${
                                                        selectedDuration === durationType
                                                            ? 'border-indigo-600 bg-indigo-50 text-indigo-700 ring-2 ring-indigo-600'
                                                            : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                                                    }`}
                                                >
                                                    <div className="font-semibold">{formatDurationLabel(durationType)}</div>
                                                    <div className="text-xs mt-1 font-medium text-indigo-600">
                                                        {formatPrice(price || 0)}
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </div>
                                );
                            })()}
                        </div>

                        <div className="flex justify-between items-center pt-2">
                            <span className="text-gray-600">Total Payable</span>
                            <span className="text-2xl font-bold text-gray-900">
                                {formatPrice(getDurationPrice(venue.durationPrices, selectedDuration, venue.priceStart) || 0)}
                            </span>
                        </div>

                        <Button onClick={handlePayment} className="w-full mt-2" size="lg">Proceed to Pay</Button>
                    </div>
                )}

                {paymentStep === 'payment' && (
                    <div className="space-y-6 text-center py-10">
                        <div className="relative mx-auto w-16 h-16">
                            <div className="absolute inset-0 border-4 border-gray-200 rounded-full"></div>
                            <div className="absolute inset-0 border-4 border-indigo-600 rounded-full border-t-transparent animate-spin"></div>
                        </div>
                        <div>
                            <h3 className="text-lg font-medium text-gray-900">Processing Payment</h3>
                            <p className="text-sm text-gray-500 mt-1">Please do not close this window</p>
                        </div>
                    </div>
                )}

                {paymentStep === 'success' && (
                    <div className="text-center space-y-4">
                        <div className="py-2">
                            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
                                <CheckCircle className="h-10 w-10 text-green-600" />
                            </div>
                            <h3 className="text-lg font-bold text-gray-900">You're all set!</h3>
                            <p className="text-sm text-gray-500 mt-2 px-4 mb-4">
                                Cabin <strong>{selectedCabin?.number}</strong> at {venue?.name} is reserved for you.
                            </p>

                            {/* Native Post-Purchase Ad */}
                            <div className="text-left bg-gray-50 rounded-lg p-1">
                                <AdBanner ad={successAd} variant="card" className="shadow-none border-none bg-transparent" />
                            </div>
                        </div>

                        <div className="pt-2">
                            <Button onClick={() => { setIsBookingModalOpen(false); navigate('/student'); }} className="w-full">
                                Go to Dashboard
                            </Button>
                        </div>
                    </div>
                )}
            </Modal>

            {/* Waitlist Modal */}
            {/* Phase 3 — Similar listings rail. Hidden silently if the
                recommendations service is disabled or returns nothing. */}
            {roomId && (
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-6">
                    <RecommendationRail
                        surface="similar"
                        similarTo={{ type: 'reading_room', id: roomId }}
                        limit={6}
                    />
                </div>
            )}

            <Modal
                isOpen={isWaitlistModalOpen}
                onClose={() => setIsWaitlistModalOpen(false)}
                title="Join Waitlist"
            >
                <div className="space-y-4">
                    <div className="text-center py-4">
                        <div className="mx-auto w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mb-4">
                            <BellRing className="w-6 h-6 text-amber-600" />
                        </div>
                        <h3 className="text-lg font-bold text-gray-900">Seat {selectedCabin?.number} is Occupied</h3>
                        <p className="text-gray-500 text-sm mt-2">
                            Would you like to be notified as soon as this seat becomes available?
                        </p>
                    </div>
                    <div className="flex gap-3 pt-2">
                        <Button variant="ghost" className="flex-1" onClick={() => setIsWaitlistModalOpen(false)}>Cancel</Button>
                        <Button className="flex-1 bg-amber-500 hover:bg-amber-600 border-none" onClick={handleConfirmWaitlist}>Join Waitlist</Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
};

export default ReadingRoomDetail;
