
import React, { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AppState, Accommodation, Gender } from '../types';
import { Card, Button, Badge, Modal, Input } from '../components/UI';
import { X, Send } from 'lucide-react';
import {
    MapPin, Star, Phone, CheckCircle, ChevronLeft, ChevronRight,
    Shield, ArrowLeft, Heart, Calendar, MessageCircle, Wifi,
    Utensils, Droplets, Lock, BookOpen, Zap, User, ExternalLink,
    Home, Users, Clock, HelpCircle
} from 'lucide-react';
import { supplyService } from '../services/supplyService';
import { inquiryService } from '../services/inquiryService';
import { messagingService } from '../services/messagingService';
import { FavoriteButton } from '../components/FavoriteButton';
import Map from '../components/Map';

interface AccommodationDetailProps {
    state: AppState;
}

export const AccommodationDetail: React.FC<AccommodationDetailProps> = ({ state }) => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [accommodation, setAccommodation] = useState<Accommodation | null>(null);
    const [loading, setLoading] = useState(true);
    const [currentImageIndex, setCurrentImageIndex] = useState(0);
    const [isSaved, setIsSaved] = useState(false);

    // Modal states
    const [isQuestionModalOpen, setIsQuestionModalOpen] = useState(false);
    const [isVisitModalOpen, setIsVisitModalOpen] = useState(false);
    const [questionText, setQuestionText] = useState('');
    const [visitDate, setVisitDate] = useState('');
    const [visitTime, setVisitTime] = useState('');
    const [contactName, setContactName] = useState(state.currentUser?.name || '');
    const [contactPhone, setContactPhone] = useState(state.currentUser?.phone || '');
    const [formSubmitted, setFormSubmitted] = useState<'question' | 'visit' | null>(null);

    // Fetch accommodation details
    useEffect(() => {
        const fetchDetails = async () => {
            setLoading(true);
            try {
                // First try from state
                const fromState = state.accommodations.find(a => a.id === id);
                if (fromState) {
                    setAccommodation(fromState);
                } else {
                    // Fetch from backend
                    const all = await supplyService.getAllAccommodations(false, 100);
                    const found = all.find(a => a.id === id);
                    if (found) setAccommodation(found);
                }
            } catch (error) {
                console.error('Failed to fetch accommodation:', error);
            } finally {
                setLoading(false);
            }
        };
        if (id) fetchDetails();
    }, [id, state.accommodations]);

    // Parse images from JSON string
    const images = useMemo(() => {
        if (!accommodation) return [];
        try {
            if (accommodation.images) {
                const parsed = JSON.parse(accommodation.images);
                if (Array.isArray(parsed) && parsed.length > 0) return parsed;
            }
        } catch { }
        return accommodation.imageUrl ? [accommodation.imageUrl] : [
            'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&q=80&w=800'
        ];
    }, [accommodation]);

    // Calculate ratings
    const { avgRating, reviewCount } = useMemo(() => {
        if (!accommodation) return { avgRating: 0, reviewCount: 0 };
        const reviews = state.reviews.filter(r => r.accommodationId === accommodation.id);
        if (reviews.length === 0) return { avgRating: 0, reviewCount: 0 };
        const total = reviews.reduce((sum, r) => sum + r.rating, 0);
        return { avgRating: Number((total / reviews.length).toFixed(1)), reviewCount: reviews.length };
    }, [accommodation, state.reviews]);

    // Get reviews for this accommodation
    const reviews = useMemo(() => {
        if (!accommodation) return [];
        return state.reviews.filter(r => r.accommodationId === accommodation.id).slice(0, 3);
    }, [accommodation, state.reviews]);

    // Check if user has verified booking
    const hasVerifiedBooking = useMemo(() => {
        if (!accommodation || !state.currentUser) return false;
        return state.bookings.some(b =>
            b.userId === state.currentUser!.id &&
            b.accommodationId === accommodation.id
        );
    }, [state.bookings, state.currentUser, accommodation]);

    // Group amenities by category
    const groupedAmenities = useMemo(() => {
        if (!accommodation?.amenities) return {};
        const groups: Record<string, string[]> = {
            'Study & Comfort': [],
            'Food & Kitchen': [],
            'Hygiene & Utilities': [],
            'Safety': []
        };

        const categoryMap: Record<string, string> = {
            'WiFi': 'Study & Comfort',
            'Power Backup': 'Study & Comfort',
            'AC': 'Study & Comfort',
            'TV': 'Study & Comfort',
            'Study Table': 'Study & Comfort',
            'Food': 'Food & Kitchen',
            'Kitchen': 'Food & Kitchen',
            'RO Water': 'Food & Kitchen',
            'Refrigerator': 'Food & Kitchen',
            'Laundry': 'Hygiene & Utilities',
            'Geyser': 'Hygiene & Utilities',
            'Attached Bathroom': 'Hygiene & Utilities',
            'Gym': 'Hygiene & Utilities',
            'Security': 'Safety',
            'CCTV': 'Safety',
            'Biometric': 'Safety'
        };

        accommodation.amenities.forEach(amenity => {
            const category = categoryMap[amenity] || 'Study & Comfort';
            if (!groups[category]) groups[category] = [];
            groups[category].push(amenity);
        });

        // Remove empty groups
        Object.keys(groups).forEach(key => {
            if (groups[key].length === 0) delete groups[key];
        });

        return groups;
    }, [accommodation]);

    // Image carousel navigation
    const nextImage = () => setCurrentImageIndex((prev) => (prev + 1) % images.length);
    const prevImage = () => setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length);

    // Google Maps URL
    const mapsUrl = accommodation ?
        `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${accommodation.address}, ${accommodation.city}`)}` : '';

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="animate-spin rounded-full h-12 w-12 border-4 border-indigo-600 border-t-transparent"></div>
            </div>
        );
    }

    if (!accommodation) {
        return (
            <div className="text-center py-20">
                <Home className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h2 className="text-xl font-bold text-gray-900 mb-2">Accommodation Not Found</h2>
                <p className="text-gray-500 mb-6">The listing you're looking for doesn't exist or has been removed.</p>
                <Button onClick={() => navigate('/student/find-pg')}>
                    <ArrowLeft className="w-4 h-4 mr-2" /> Back to Listings
                </Button>
            </div>
        );
    }

    const isVerified = accommodation.status === 'LIVE' || accommodation.isVerified;
    const deposit = accommodation.price * 2; // Assume 2 months deposit

    return (
        <div className="max-w-5xl mx-auto pb-32 animate-in fade-in">
            {/* Back Navigation */}
            <button
                onClick={() => navigate(-1)}
                className="flex items-center gap-2 text-gray-600 hover:text-indigo-600 transition-colors mb-4 group"
            >
                <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform" />
                <span className="font-medium">Back to Listings</span>
            </button>

            {/* 1. Image Carousel - Hero Section */}
            <div className="relative rounded-2xl overflow-hidden bg-gray-100 mb-6 shadow-lg">
                <div className="aspect-[16/9] md:aspect-[21/9]">
                    <img
                        src={images[currentImageIndex]}
                        alt={`${accommodation.name} - Photo ${currentImageIndex + 1}`}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.onerror = null;
                            target.src = 'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&q=80&w=800';
                        }}
                    />
                </div>

                {/* Navigation Arrows */}
                {images.length > 1 && (
                    <>
                        <button
                            onClick={prevImage}
                            className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white p-2 rounded-full shadow-lg transition-all hover:scale-110"
                        >
                            <ChevronLeft className="w-6 h-6 text-gray-800" />
                        </button>
                        <button
                            onClick={nextImage}
                            className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/90 hover:bg-white p-2 rounded-full shadow-lg transition-all hover:scale-110"
                        >
                            <ChevronRight className="w-6 h-6 text-gray-800" />
                        </button>
                    </>
                )}

                {/* Image Indicators */}
                {images.length > 1 && (
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
                        {images.map((_, i) => (
                            <button
                                key={i}
                                onClick={() => setCurrentImageIndex(i)}
                                className={`w-2 h-2 rounded-full transition-all ${i === currentImageIndex ? 'bg-white w-6' : 'bg-white/50 hover:bg-white/80'
                                    }`}
                            />
                        ))}
                    </div>
                )}

                {/* Top Badges */}
                <div className="absolute top-4 left-4 flex gap-2 flex-wrap">
                    {isVerified && (
                        <span className="bg-green-500 text-white text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-1.5 shadow-lg">
                            <CheckCircle className="w-3.5 h-3.5" /> VERIFIED
                        </span>
                    )}
                    <span className="bg-white/95 backdrop-blur-sm text-gray-800 text-xs font-bold px-3 py-1.5 rounded-full shadow-lg">
                        {accommodation.type || 'PG'} · {accommodation.gender === 'MALE' ? '♂ Male' : accommodation.gender === 'FEMALE' ? '♀ Female' : '⚥ Unisex'}
                    </span>
                </div>

                {/* Wishlist Button */}
                <div className="absolute top-4 right-4">
                    <FavoriteButton
                        accommodationId={accommodation.id}
                        size="lg"
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Main Content Column */}
                <div className="lg:col-span-2 space-y-6">
                    {/* 2. Title Section with Trust & Context */}
                    <Card className="p-6">
                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                            <div className="flex-1">
                                <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-2">
                                    {accommodation.name}
                                </h1>
                                <p className="text-gray-600 flex items-center gap-1 mb-3">
                                    <MapPin className="w-4 h-4 text-indigo-500" />
                                    {accommodation.address}
                                    {accommodation.city && `, ${accommodation.city}`}
                                </p>

                                {/* Rating Stars */}
                                <div className="flex items-center gap-3 flex-wrap">
                                    <div className="flex items-center gap-1">
                                        {[...Array(5)].map((_, i) => (
                                            <Star
                                                key={i}
                                                className={`w-5 h-5 ${i < Math.round(avgRating)
                                                    ? 'text-yellow-400 fill-yellow-400'
                                                    : 'text-gray-200'
                                                    }`}
                                            />
                                        ))}
                                        <span className="ml-2 font-bold text-gray-900">
                                            {avgRating > 0 ? avgRating : '-'}
                                        </span>
                                        <span className="text-sm text-gray-500">
                                            ({reviewCount} {reviewCount === 1 ? 'review' : 'reviews'})
                                        </span>
                                    </div>

                                    {isVerified && (
                                        <span className="text-sm text-green-600 flex items-center gap-1 font-medium bg-green-50 px-2 py-1 rounded-full">
                                            <CheckCircle className="w-4 h-4" /> Verified by StudySpace
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </Card>

                    {/* 4. Amenities Section - Grouped & Scannable */}
                    <Card className="p-6">
                        <h2 className="text-lg font-bold text-gray-900 mb-4">Amenities & Facilities</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {Object.entries(groupedAmenities).map(([category, items]: [string, string[]]) => {
                                const iconMap: Record<string, React.ReactNode> = {
                                    'Study & Comfort': <BookOpen className="w-5 h-5 text-indigo-500" />,
                                    'Food & Kitchen': <Utensils className="w-5 h-5 text-orange-500" />,
                                    'Hygiene & Utilities': <Droplets className="w-5 h-5 text-blue-500" />,
                                    'Safety': <Shield className="w-5 h-5 text-green-500" />
                                };
                                return (
                                    <div key={category} className="bg-gray-50 rounded-xl p-4">
                                        <div className="flex items-center gap-2 mb-3">
                                            {iconMap[category] || <Zap className="w-5 h-5 text-gray-500" />}
                                            <h3 className="font-semibold text-gray-800">{category}</h3>
                                        </div>
                                        <div className="space-y-2">
                                            {items.map(item => (
                                                <div key={item} className="flex items-center gap-2 text-sm text-gray-600">
                                                    <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                                                    {item}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {Object.keys(groupedAmenities).length === 0 && (
                            <p className="text-gray-400 text-center py-4">No amenities listed yet.</p>
                        )}
                    </Card>

                    {/* 5. Reviews Section */}
                    <Card className="p-6">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-900">Student Reviews</h2>
                            {hasVerifiedBooking && (
                                <Button size="sm" variant="outline">Write Review</Button>
                            )}
                        </div>

                        {reviews.length > 0 ? (
                            <div className="space-y-4">
                                {reviews.map(review => (
                                    <div key={review.id} className="bg-gray-50 rounded-xl p-4">
                                        <div className="flex items-start gap-3">
                                            <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center flex-shrink-0">
                                                <User className="w-5 h-5 text-indigo-600" />
                                            </div>
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <div className="flex">
                                                        {[...Array(5)].map((_, i) => (
                                                            <Star
                                                                key={i}
                                                                className={`w-4 h-4 ${i < review.rating
                                                                    ? 'text-yellow-400 fill-yellow-400'
                                                                    : 'text-gray-200'
                                                                    }`}
                                                            />
                                                        ))}
                                                    </div>
                                                    <span className="text-xs text-gray-400">{review.date}</span>
                                                </div>
                                                <p className="text-gray-700">{review.comment}</p>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                                {state.reviews.filter(r => r.accommodationId === accommodation.id).length > 3 && (
                                    <button className="w-full text-center text-indigo-600 font-medium py-2 hover:text-indigo-700">
                                        Read all {state.reviews.filter(r => r.accommodationId === accommodation.id).length} reviews →
                                    </button>
                                )}
                            </div>
                        ) : (
                            <div className="bg-gray-50 rounded-xl p-6 text-center">
                                <Lock className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                                <p className="text-gray-600 font-medium mb-1">No reviews yet</p>
                                <p className="text-sm text-gray-400">
                                    Only verified residents can review. Be the first to review after staying here.
                                </p>
                            </div>
                        )}
                    </Card>

                    {/* 8. Interactive Google Map */}
                    <Card className="p-6">
                        <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <MapPin className="w-5 h-5 text-indigo-500" /> Location
                        </h2>

                        {accommodation.latitude && accommodation.longitude ? (
                            <Map
                                center={{ lat: accommodation.latitude, lng: accommodation.longitude }}
                                markers={[
                                    {
                                        id: accommodation.id,
                                        lat: accommodation.latitude,
                                        lng: accommodation.longitude,
                                        title: accommodation.name,
                                        address: accommodation.address,
                                    },
                                ]}
                                height="400px"
                                className="rounded-xl overflow-hidden mb-3"
                            />
                        ) : (
                            <div className="bg-gray-100 rounded-xl overflow-hidden aspect-video">
                                <iframe
                                    src={`https://www.google.com/maps?q=${encodeURIComponent(`${accommodation.address}, ${accommodation.city}`)}&output=embed`}
                                    className="w-full h-full border-0"
                                    loading="lazy"
                                    referrerPolicy="no-referrer-when-downgrade"
                                ></iframe>
                            </div>
                        )}

                        <p className="text-sm text-gray-500 mt-3">{accommodation.address}</p>
                        <a
                            href={mapsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-700 font-medium mt-2"
                        >
                            <ExternalLink className="w-4 h-4" /> Open in Google Maps
                        </a>
                    </Card>

                    {/* 9. How Booking Works */}
                    <Card className="p-6">
                        <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <HelpCircle className="w-5 h-5 text-indigo-500" /> How Booking Works
                        </h2>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            {[
                                { step: 1, label: 'Explore verified PGs', icon: <Home className="w-6 h-6" /> },
                                { step: 2, label: 'Contact owner directly', icon: <Phone className="w-6 h-6" /> },
                                { step: 3, label: 'Visit & confirm', icon: <Calendar className="w-6 h-6" /> },
                                { step: 4, label: 'Join and review', icon: <Star className="w-6 h-6" /> }
                            ].map(item => (
                                <div key={item.step} className="text-center">
                                    <div className="w-14 h-14 bg-indigo-50 rounded-xl flex items-center justify-center mx-auto mb-2 text-indigo-600">
                                        {item.icon}
                                    </div>
                                    <div className="text-xs font-bold text-indigo-600 mb-1">Step {item.step}</div>
                                    <p className="text-sm text-gray-600">{item.label}</p>
                                </div>
                            ))}
                        </div>
                    </Card>
                </div>

                {/* Sidebar Column */}
                <div className="lg:col-span-1 space-y-6">
                    {/* 3. Pricing Card */}
                    <Card className="p-6 lg:sticky lg:top-4">
                        <div className="text-center mb-5 pb-5 border-b border-gray-100">
                            <div className="text-4xl font-bold text-gray-900">
                                ₹{accommodation.price.toLocaleString()}
                                <span className="text-base font-normal text-gray-400">/month</span>
                            </div>
                            <p className="text-sm text-gray-500 mt-1">
                                + ₹{deposit.toLocaleString()} refundable deposit
                            </p>
                        </div>

                        <div className="space-y-3 mb-6">
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                                <span className="text-gray-700">No brokerage</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                                <span className="text-gray-700">Direct owner contact</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0" />
                                <span className="text-gray-700">Flexible joining</span>
                            </div>
                        </div>

                        {/* CTA Buttons */}
                        <div className="space-y-3">
                            <a href={`tel:${accommodation.contactPhone}`} className="block">
                                <Button className="w-full" size="lg">
                                    <Phone className="w-5 h-5 mr-2" /> Call Owner
                                </Button>
                            </a>
                            <Button variant="outline" className="w-full" size="lg" onClick={async () => {
                                if (state.currentUser && accommodation) {
                                    try {
                                        // Start conversation with specific context
                                        const conversation = await messagingService.startConversationWithOwner(
                                            accommodation.ownerId,
                                            accommodation.id,
                                            'accommodation'
                                        );
                                        // Navigate to messages with the specific conversation selected
                                        navigate('/student/messages', {
                                            state: {
                                                selectedConversationId: conversation.id
                                            }
                                        });
                                    } catch (error) {
                                        console.error('Failed to start conversation:', error);
                                        // Fallback to general messages page
                                        navigate('/student/messages');
                                    }
                                } else {
                                    // If not logged in, maybe redirect to login? 
                                    // For now, let generic auth guard handle it or navigate to messages
                                    navigate('/student/messages');
                                }
                            }}>
                                <MessageCircle className="w-5 h-5 mr-2" /> Message Owner
                            </Button>
                            <Button variant="outline" className="w-full" size="lg" onClick={() => setIsVisitModalOpen(true)}>
                                <Calendar className="w-5 h-5 mr-2" /> Schedule a Visit
                            </Button>
                        </div>
                    </Card>

                    {/* 7. Trust Signals Card */}
                    <Card className="p-6 bg-gradient-to-br from-indigo-50 to-white border-indigo-100">
                        <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
                            <Shield className="w-5 h-5 text-indigo-600" /> Why Book via StudySpace?
                        </h3>
                        <div className="space-y-3">
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                                <span className="text-gray-700">Owner verified</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                                <span className="text-gray-700">Address validated via Google Maps</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                                <span className="text-gray-700">Reviews from real residents</span>
                            </div>
                            <div className="flex items-center gap-3 text-sm">
                                <CheckCircle className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                                <span className="text-gray-700">No middlemen</span>
                            </div>
                        </div>
                    </Card>

                    {/* Property Info Card */}
                    <Card className="p-6">
                        <h3 className="font-bold text-gray-900 mb-4">Property Details</h3>
                        <div className="space-y-3">
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-500">Type</span>
                                <span className="font-medium text-gray-900">{accommodation.type || 'PG'}</span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-500">Gender</span>
                                <span className="font-medium text-gray-900">
                                    {accommodation.gender === 'MALE' ? 'Male Only' :
                                        accommodation.gender === 'FEMALE' ? 'Female Only' : 'Co-ed'}
                                </span>
                            </div>
                            <div className="flex justify-between text-sm">
                                <span className="text-gray-500">Room Sharing</span>
                                <span className="font-medium text-gray-900">{accommodation.sharing || 'Single'}</span>
                            </div>
                        </div>
                    </Card>
                </div>
            </div>

            {/* Sticky Mobile CTA */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 p-4 shadow-lg z-40 lg:hidden">
                <div className="flex items-center justify-between gap-4 max-w-5xl mx-auto">
                    <div>
                        <div className="text-xl font-bold text-gray-900">₹{accommodation.price.toLocaleString()}/mo</div>
                        <p className="text-xs text-gray-500">+ ₹{deposit.toLocaleString()} deposit</p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setIsSaved(!isSaved)}
                            className={`p-3 rounded-xl border ${isSaved ? 'border-red-200 bg-red-50' : 'border-gray-200'}`}
                        >
                            <Heart className={`w-5 h-5 ${isSaved ? 'fill-red-500 text-red-500' : 'text-gray-400'}`} />
                        </button>
                        <a href={`tel:${accommodation.contactPhone}`}>
                            <Button size="lg">
                                <Phone className="w-5 h-5 mr-2" /> Call Owner
                            </Button>
                        </a>
                    </div>
                </div>
            </div>

            {/* Ask a Question Modal */}
            <Modal
                isOpen={isQuestionModalOpen}
                onClose={() => { setIsQuestionModalOpen(false); setFormSubmitted(null); setQuestionText(''); }}
                title="Ask a Question"
            >
                {formSubmitted === 'question' ? (
                    <div className="text-center py-8">
                        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <CheckCircle className="w-8 h-8 text-green-600" />
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">Question Sent!</h3>
                        <p className="text-gray-500 mb-6">
                            The owner of {accommodation.name} will receive your question and respond soon.
                        </p>
                        <Button onClick={() => { setIsQuestionModalOpen(false); setFormSubmitted(null); setQuestionText(''); }}>
                            Close
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <p className="text-gray-500 text-sm">
                            Send a question to the owner of <strong>{accommodation.name}</strong>. They'll respond via phone or email.
                        </p>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Your Name</label>
                            <input
                                type="text"
                                value={contactName}
                                onChange={(e) => setContactName(e.target.value)}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                                placeholder="Enter your name"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Your Phone</label>
                            <input
                                type="tel"
                                value={contactPhone}
                                onChange={(e) => setContactPhone(e.target.value)}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                                placeholder="Enter your phone number"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Your Question</label>
                            <textarea
                                value={questionText}
                                onChange={(e) => setQuestionText(e.target.value)}
                                rows={4}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-none"
                                placeholder="E.g., Is food included? What are the visiting hours? Is there a curfew?"
                            />
                        </div>

                        <Button
                            className="w-full"
                            size="lg"
                            onClick={async () => {
                                if (questionText.trim() && contactName.trim() && accommodation) {
                                    try {
                                        await inquiryService.createInquiry({
                                            accommodationId: accommodation.id,
                                            type: 'QUESTION',
                                            question: questionText,
                                            studentName: contactName,
                                            studentPhone: contactPhone
                                        });
                                        setFormSubmitted('question');
                                    } catch (error) {
                                        console.error('Failed to send question:', error);
                                        alert('Failed to send question. Please try again.');
                                    }
                                }
                            }}
                            disabled={!questionText.trim() || !contactName.trim()}
                        >
                            <Send className="w-4 h-4 mr-2" /> Send Question
                        </Button>
                    </div>
                )}
            </Modal>

            {/* Schedule a Visit Modal */}
            <Modal
                isOpen={isVisitModalOpen}
                onClose={() => { setIsVisitModalOpen(false); setFormSubmitted(null); setVisitDate(''); setVisitTime(''); }}
                title="Schedule a Visit"
            >
                {formSubmitted === 'visit' ? (
                    <div className="text-center py-8">
                        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Calendar className="w-8 h-8 text-green-600" />
                        </div>
                        <h3 className="text-xl font-bold text-gray-900 mb-2">Visit Requested!</h3>
                        <p className="text-gray-500 mb-4">
                            Your visit request for <strong>{visitDate}</strong> at <strong>{visitTime}</strong> has been sent.
                        </p>
                        <p className="text-sm text-gray-400 mb-6">
                            The owner of {accommodation.name} will contact you to confirm the visit.
                        </p>
                        <Button onClick={() => { setIsVisitModalOpen(false); setFormSubmitted(null); setVisitDate(''); setVisitTime(''); }}>
                            Close
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <p className="text-gray-500 text-sm">
                            Request a visit to <strong>{accommodation.name}</strong>. The owner will confirm your preferred time.
                        </p>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Your Name</label>
                            <input
                                type="text"
                                value={contactName}
                                onChange={(e) => setContactName(e.target.value)}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                                placeholder="Enter your name"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Your Phone</label>
                            <input
                                type="tel"
                                value={contactPhone}
                                onChange={(e) => setContactPhone(e.target.value)}
                                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                                placeholder="Enter your phone number"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Date</label>
                                <input
                                    type="date"
                                    value={visitDate}
                                    onChange={(e) => setVisitDate(e.target.value)}
                                    min={new Date().toISOString().split('T')[0]}
                                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Time</label>
                                <select
                                    value={visitTime}
                                    onChange={(e) => setVisitTime(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none bg-white"
                                >
                                    <option value="">Select time</option>
                                    <option value="9:00 AM">9:00 AM</option>
                                    <option value="10:00 AM">10:00 AM</option>
                                    <option value="11:00 AM">11:00 AM</option>
                                    <option value="12:00 PM">12:00 PM</option>
                                    <option value="2:00 PM">2:00 PM</option>
                                    <option value="3:00 PM">3:00 PM</option>
                                    <option value="4:00 PM">4:00 PM</option>
                                    <option value="5:00 PM">5:00 PM</option>
                                    <option value="6:00 PM">6:00 PM</option>
                                </select>
                            </div>
                        </div>

                        <div className="bg-indigo-50 rounded-lg p-3 text-sm text-indigo-700">
                            <strong>💡 Tip:</strong> Visiting in person helps you see the actual room, meet potential roommates, and verify the amenities.
                        </div>

                        <Button
                            className="w-full"
                            size="lg"
                            onClick={async () => {
                                if (visitDate && visitTime && contactName.trim() && contactPhone.trim() && accommodation) {
                                    try {
                                        await inquiryService.createInquiry({
                                            accommodationId: accommodation.id,
                                            type: 'VISIT',
                                            question: `Visit request for ${visitDate} at ${visitTime}`,
                                            studentName: contactName,
                                            studentPhone: contactPhone,
                                            preferredDate: visitDate,
                                            preferredTime: visitTime
                                        });
                                        setFormSubmitted('visit');
                                    } catch (error) {
                                        console.error('Failed to request visit:', error);
                                        alert('Failed to request visit. Please try again.');
                                    }
                                }
                            }}
                            disabled={!visitDate || !visitTime || !contactName.trim() || !contactPhone.trim()}
                        >
                            <Calendar className="w-4 h-4 mr-2" /> Request Visit
                        </Button>
                    </div>
                )}
            </Modal>
        </div>
    );
};
