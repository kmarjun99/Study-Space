import React, { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { AppState, ReadingRoom, Cabin, CabinStatus, User } from '../types';
import { Button, Card, Badge, Modal, LiveIndicator } from '../components/UI';
import { waitlistService } from '../services/waitlistService';
import { toast } from 'react-hot-toast';
import { ImageGallery } from '../components/ImageGallery';
import { SeatMap } from '../components/SeatMap';
import { VenueTrustSignals } from '../components/VenueTrustSignals';
import { AdBanner } from '../components/AdBanner';
import { getTargetedAd } from '../services/adService';
import { FavoriteButton } from '../components/FavoriteButton';
import Map from '../components/Map';

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
    const [activeFloor, setActiveFloor] = useState<number | 'All'>('All');
    const [duration, setDuration] = useState(1);
    const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
    const [isWaitlistModalOpen, setIsWaitlistModalOpen] = useState(false);
    const [paymentStep, setPaymentStep] = useState<'details' | 'payment' | 'success'>('details');
    const [showAmenities, setShowAmenities] = useState(false);
    const [ads, setAds] = useState<any[]>([]);

    // Parse venue images
    const venueImages = useMemo(() => {
        if (!venue?.images) {
            // Fallback to imageUrl if images is empty
            return venue?.imageUrl ? [venue.imageUrl] : [];
        }
        try {
            // Try to parse as JSON array
            const parsed = JSON.parse(venue.images);
            return Array.isArray(parsed) && parsed.length > 0 ? parsed : (venue.imageUrl ? [venue.imageUrl] : []);
        } catch {
            // If parsing fails, check if it's a stringified URL or an actual URL
            // If images is a string that looks like a URL, return it as an array
            if (typeof venue.images === 'string' && (venue.images.startsWith('http') || venue.images.startsWith('data:'))) {
                return [venue.images];
            }
            // Final fallback to imageUrl
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
            setPaymentStep('details');
            setIsBookingModalOpen(true);
        }
    };

    const handlePayment = () => {
        setPaymentStep('payment');
        setTimeout(async () => {
            if (selectedCabin) {
                try {
                    await onBookCabin(selectedCabin.id, duration);
                    setPaymentStep('success');
                } catch (e) {
                    console.error(e);
                    setPaymentStep('details');
                }
            }
        }, 1500);
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
                            <div className="grid grid-cols-3 gap-3">
                                {[1, 3, 6].map(m => (
                                    <button
                                        key={m}
                                        onClick={() => setDuration(m)}
                                        className={`py-2 px-1 text-sm font-medium rounded-md border transition-all ${duration === m
                                            ? 'border-indigo-600 bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600'
                                            : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                                            }`}
                                    >
                                        {m} Month{m > 1 ? 's' : ''}
                                        {m > 1 && <span className="block text-[10px] text-green-600">Save {m === 3 ? '5%' : '10%'}</span>}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="flex justify-between items-center pt-2">
                            <span className="text-gray-600">Total Payable</span>
                            <span className="text-2xl font-bold text-gray-900">₹{selectedCabin.price * duration}</span>
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
