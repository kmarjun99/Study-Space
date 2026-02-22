
import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppState, Gender, Accommodation } from '../types';
import { Card, Button, Badge, Modal, Input } from '../components/UI';
import { MapPin, Search, Filter, Star, Phone, Home, CheckCircle, User, Lock, Loader2 } from 'lucide-react';
import { LocationSearch, LocationResult } from '../components/LocationSearch';
import { useCityPreference } from '../hooks/useCityPreference';
import { supplyService } from '../services/supplyService';
import { FavoriteButton } from '../components/FavoriteButton';

interface FindAccommodationProps {
    state: AppState;
}

export const FindAccommodation: React.FC<FindAccommodationProps> = ({ state }) => {
    const navigate = useNavigate();
    // Local state for fetched accommodations
    const [accommodations, setAccommodations] = useState<Accommodation[]>(state.accommodations);
    const [isLoading, setIsLoading] = useState(true);
    const [fetchError, setFetchError] = useState<string | null>(null);

    // Fetch accommodations from backend when page loads
    useEffect(() => {
        const fetchAccommodations = async () => {
            try {
                setIsLoading(true);
                setFetchError(null);
                const data = await supplyService.getAllAccommodations(false, 100);
                if (data) {
                    setAccommodations(data);
                } 
            } catch (error) {
                console.warn('Failed to fetch accommodations from backend:', error);
                setFetchError('Unable to load latest listings.');
                // Do not fallback to mock data to prevent leaking unverified items
                setAccommodations([]);
            } finally {
                setIsLoading(false);
            }
        };
        fetchAccommodations();
    }, []);

    // City Preference (persisted in localStorage)
    const { cityPreference, setCityPreference, clearCityPreference, cityDisplayName } = useCityPreference();

    // Filters
    const [locationSearch, setLocationSearch] = useState(cityDisplayName || '');
    const [selectedLocation, setSelectedLocation] = useState<LocationResult | null>(cityPreference);
    const [priceRange, setPriceRange] = useState<number>(20000);
    const [genderFilter, setGenderFilter] = useState<Gender | 'ALL'>('ALL');
    const [typeFilter, setTypeFilter] = useState<'ALL' | 'PG' | 'HOSTEL' | 'HOUSE'>('ALL');

    // Sync with city preference on mount
    useEffect(() => {
        if (cityPreference && !selectedLocation) {
            setSelectedLocation(cityPreference);
            setLocationSearch(cityDisplayName);
        }
    }, [cityPreference, cityDisplayName]);

    // Contact Modal
    const [selectedAccommodation, setSelectedAccommodation] = useState<Accommodation | null>(null);

    // Review Modal for Details Page
    const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
    const [reviewRating, setReviewRating] = useState(5);
    const [reviewComment, setReviewComment] = useState('');

    // Helper to calculate rating
    const getRating = (accId: string) => {
        const reviews = state.reviews.filter(r => r.accommodationId === accId);
        if (reviews.length === 0) return { avg: 0, count: 0 };
        const total = reviews.reduce((sum, r) => sum + r.rating, 0);
        return { avg: (total / reviews.length).toFixed(1), count: reviews.length };
    };

    // Filter Logic
    const filteredAccommodations = useMemo(() => {
        return accommodations.filter(acc => {
            // If a location is selected, match by location_id or city/locality
            let matchesLocation = true;
            if (selectedLocation) {
                // Match by location_id if available
                if (acc.locationId && acc.locationId === selectedLocation.id) {
                    matchesLocation = true;
                } else {
                    // Fallback: match by city or locality text
                    const cityMatch = (acc.city || '').toLowerCase() === selectedLocation.city.toLowerCase();
                    const localityMatch = selectedLocation.locality &&
                        (acc.locality || '').toLowerCase() === selectedLocation.locality.toLowerCase();
                    matchesLocation = cityMatch || localityMatch;
                }
            } else if (locationSearch.trim()) {
                // Text search fallback when no location selected
                matchesLocation = (acc.address || '').toLowerCase().includes(locationSearch.toLowerCase()) ||
                    (acc.name || '').toLowerCase().includes(locationSearch.toLowerCase()) ||
                    (acc.city || '').toLowerCase().includes(locationSearch.toLowerCase()) ||
                    (acc.locality || '').toLowerCase().includes(locationSearch.toLowerCase());
            }

            const matchesPrice = (acc.price || 0) <= priceRange;
            const matchesGender = genderFilter === 'ALL' || acc.gender === genderFilter || acc.gender === Gender.UNISEX;
            const matchesType = typeFilter === 'ALL' || acc.type === typeFilter;

            return matchesLocation && matchesPrice && matchesGender && matchesType;
        });
    }, [accommodations, locationSearch, selectedLocation, priceRange, genderFilter, typeFilter]);

    // Get reviews for selected accommodation
    const selectedReviews = useMemo(() => {
        if (!selectedAccommodation) return [];
        return state.reviews.filter(r => r.accommodationId === selectedAccommodation.id);
    }, [selectedAccommodation, state.reviews]);

    // Check if current user has a verified booking for selected accommodation
    const hasVerifiedBooking = useMemo(() => {
        if (!selectedAccommodation || !state.currentUser) return false;
        return state.bookings.some(b =>
            b.userId === state.currentUser!.id &&
            b.accommodationId === selectedAccommodation.id
        );
    }, [state.bookings, state.currentUser, selectedAccommodation]);

    // Check if a review author is verified
    const isAuthorVerified = (userId: string, accommodationId: string) => {
        return state.bookings.some(b => b.userId === userId && b.accommodationId === accommodationId);
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto">
            {/* Header & Search */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
                <div className="flex justify-between items-start mb-2">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 mb-2">Find Student Housing</h1>
                        <p className="text-gray-500">Discover PGs and Hostels near your reading room.</p>
                    </div>

                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-4">
                    {/* Location Search with Autocomplete */}
                    <div className="md:col-span-2">
                        <LocationSearch
                            value={locationSearch}
                            placeholder="Search city or locality..."
                            onSelect={(location) => {
                                setSelectedLocation(location);
                                setLocationSearch(location.display_name);
                                setCityPreference(location); // Persist preference
                            }}
                            onClear={() => {
                                setSelectedLocation(null);
                                setLocationSearch('');
                                clearCityPreference(); // Clear persisted preference
                            }}
                        />
                    </div>

                    {/* Gender Filter */}
                    <div className="md:col-span-1">
                        <select
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white text-gray-700"
                            value={genderFilter}
                            onChange={(e) => setGenderFilter(e.target.value as Gender | 'ALL')}
                        >
                            <option value="ALL">Any Gender</option>
                            <option value={Gender.MALE}>Male</option>
                            <option value={Gender.FEMALE}>Female</option>
                            <option value={Gender.UNISEX}>Unisex</option>
                        </select>
                    </div>

                    {/* Type Filter */}
                    <div className="md:col-span-1">
                        <select
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 bg-white text-gray-700"
                            value={typeFilter}
                            onChange={(e) => setTypeFilter(e.target.value as 'ALL' | 'PG' | 'HOSTEL' | 'HOUSE')}
                        >
                            <option value="ALL">All Types</option>
                            <option value="PG">PG</option>
                            <option value="HOSTEL">Hostel</option>
                            <option value="HOUSE">House</option>
                        </select>
                    </div>
                </div>

                {/* Price Slider */}
                <div className="mt-4 pt-4 border-t border-gray-100 flex flex-col sm:flex-row items-center gap-4">
                    <span className="text-sm font-medium text-gray-700 whitespace-nowrap">Max Rent: ₹{priceRange.toLocaleString()}</span>
                    <input
                        type="range"
                        min="3000"
                        max="30000"
                        step="500"
                        value={priceRange}
                        onChange={(e) => setPriceRange(parseInt(e.target.value))}
                        className="w-full h-2 bg-indigo-100 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                    />
                </div>


            </div>

            {/* Results Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredAccommodations.map(acc => {
                    const { avg, count } = getRating(acc.id);
                    return (
                        <Card key={acc.id} className="overflow-hidden group hover:shadow-md transition-all duration-300 flex flex-col">
                            <div className="relative h-48 overflow-hidden bg-gray-200">
                                <img
                                    src={acc.imageUrl}
                                    alt={acc.name}
                                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                    onError={(e) => {
                                        const target = e.target as HTMLImageElement;
                                        target.onerror = null;
                                        target.src = 'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?auto=format&fit=crop&q=80&w=800';
                                    }}
                                />
                                <div className="absolute top-2 right-2 flex gap-2 items-start">
                                    <div className="bg-white/90 backdrop-blur-sm px-2 py-1 rounded-md shadow-sm flex items-center gap-1 text-xs font-bold">
                                        <Star className="w-3 h-3 text-yellow-500 fill-yellow-500" />
                                        {Number(avg) > 0 ? avg : 'New'}
                                        {count > 0 && <span className="text-gray-500 font-normal">({count})</span>}
                                    </div>
                                    <FavoriteButton
                                        accommodationId={acc.id}
                                        size="sm"
                                    />
                                </div>
                                <div className="absolute top-2 left-2">
                                    <Badge variant={acc.type === 'PG' ? 'info' : acc.type === 'HOSTEL' ? 'warning' : 'success'}>{acc.type}</Badge>
                                </div>
                            </div>

                            <div className="p-5 flex-1 flex flex-col">
                                <div className="flex justify-between items-start mb-2">
                                    <h3 className="text-lg font-bold text-gray-900 line-clamp-1">{acc.name}</h3>
                                </div>

                                <p className="text-sm text-gray-500 flex items-start mb-3">
                                    <MapPin className="w-4 h-4 mr-1 mt-0.5 flex-shrink-0 text-gray-400" />
                                    <span className="line-clamp-1">{acc.address}</span>
                                </p>

                                <div className="flex items-center gap-2 mb-4">
                                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${acc.gender === Gender.MALE ? 'bg-blue-50 text-blue-700' :
                                        acc.gender === Gender.FEMALE ? 'bg-pink-50 text-pink-700' :
                                            'bg-purple-50 text-purple-700'
                                        }`}>
                                        {acc.gender === 'UNISEX' ? 'Co-ed' : acc.gender.charAt(0) + acc.gender.slice(1).toLowerCase()}
                                    </span>
                                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">
                                        {acc.sharing} Sharing
                                    </span>
                                </div>

                                <div className="flex flex-wrap gap-1 mb-4 flex-1">
                                    {acc.amenities.slice(0, 3).map(amenity => (
                                        <span key={amenity} className="text-[10px] bg-gray-50 border border-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                                            {amenity}
                                        </span>
                                    ))}
                                    {acc.amenities.length > 3 && (
                                        <span className="text-[10px] text-gray-400 px-1 py-0.5">+{acc.amenities.length - 3}</span>
                                    )}
                                </div>

                                <div className="pt-3 border-t border-gray-50 flex items-center justify-between mt-auto">
                                    <div>
                                        <span className="text-lg font-bold text-indigo-600">₹{acc.price.toLocaleString()}</span>
                                        <span className="text-xs text-gray-400">/mo</span>
                                    </div>
                                    <Button size="sm" variant="outline" onClick={() => navigate(`/student/accommodation/${acc.id}`)}>
                                        View Details
                                    </Button>
                                </div>
                            </div>
                        </Card>
                    )
                })}

                {filteredAccommodations.length === 0 && (
                    <div className="col-span-full text-center py-12">
                        <div className="bg-gray-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                            <Search className="w-8 h-8 text-gray-400" />
                        </div>
                        <h3 className="text-lg font-medium text-gray-900">No accommodations found</h3>
                        <p className="text-gray-500 mt-1">Try adjusting your location or price filters.</p>
                    </div>
                )}
            </div>

            {/* Details Modal */}
            <Modal
                isOpen={!!selectedAccommodation}
                onClose={() => setSelectedAccommodation(null)}
                title="Accommodation Details"
            >
                {selectedAccommodation && (
                    <div className="space-y-6">
                        <div className="text-center">
                            <h3 className="text-xl font-bold text-gray-900">{selectedAccommodation.name}</h3>
                            <p className="text-gray-500 text-sm">{selectedAccommodation.address}</p>
                            <div className="flex justify-center items-center gap-1 mt-2">
                                <div className="flex text-yellow-400">
                                    {[...Array(5)].map((_, i) => (
                                        <Star key={i} className={`w-4 h-4 ${i < Math.round(Number(getRating(selectedAccommodation.id).avg)) ? 'fill-current' : 'text-gray-200'}`} />
                                    ))}
                                </div>
                                <span className="text-sm text-gray-600 font-medium ml-1">{getRating(selectedAccommodation.id).avg}</span>
                                <span className="text-xs text-gray-400">({getRating(selectedAccommodation.id).count} reviews)</span>
                            </div>
                        </div>



                        <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
                            <div>
                                <span className="text-xs text-gray-500 uppercase font-bold">Monthly Rent</span>
                                <p className="text-lg font-bold text-gray-900">₹{selectedAccommodation.price}</p>
                            </div>
                            <div>
                                <span className="text-xs text-gray-500 uppercase font-bold">Deposit</span>
                                <p className="text-lg font-bold text-gray-900">₹{selectedAccommodation.price * 2}</p>
                            </div>
                        </div>

                        <div>
                            <span className="text-sm font-bold text-gray-900 mb-2 block">Amenities</span>
                            <div className="flex flex-wrap gap-2">
                                {selectedAccommodation.amenities.map(a => (
                                    <Badge key={a} variant="info">{a}</Badge>
                                ))}
                            </div>
                        </div>

                        {/* Reviews Section with Verified Gating */}
                        <div className="border-t border-gray-100 pt-4">
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-sm font-bold text-gray-900">Student Reviews</h4>
                                {hasVerifiedBooking ? (
                                    <Button size="sm" variant="outline" onClick={() => setIsReviewModalOpen(true)}>Write Review</Button>
                                ) : (
                                    <span className="text-xs text-gray-400 flex items-center bg-gray-100 px-2 py-1 rounded">
                                        <Lock className="w-3 h-3 mr-1" /> Only verified residents
                                    </span>
                                )}
                            </div>

                            {selectedReviews.length > 0 ? (
                                <div className="space-y-3 max-h-60 overflow-y-auto custom-scrollbar pr-2">
                                    {selectedReviews.map(review => {
                                        const isVerified = isAuthorVerified(review.userId, selectedAccommodation.id);
                                        return (
                                            <div key={review.id} className="bg-gray-50 p-3 rounded-lg text-sm relative">
                                                <div className="flex justify-between items-start mb-1">
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center text-[10px] font-bold text-indigo-600">
                                                            <User className="w-3 h-3" />
                                                        </div>
                                                        <div className="flex flex-col">
                                                            <div className="flex text-yellow-400">
                                                                {[...Array(5)].map((_, i) => (
                                                                    <Star key={i} className={`w-3 h-3 ${i < review.rating ? 'fill-current' : 'text-gray-300'}`} />
                                                                ))}
                                                            </div>
                                                            {isVerified && (
                                                                <span className="text-[10px] text-green-600 flex items-center mt-0.5">
                                                                    <CheckCircle className="w-2.5 h-2.5 mr-0.5" /> Verified Resident
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <span className="text-xs text-gray-400">{review.date}</span>
                                                </div>
                                                <p className="text-gray-600 mt-1">"{review.comment}"</p>
                                            </div>
                                        )
                                    })}
                                </div>
                            ) : (
                                <p className="text-sm text-gray-400 italic">No reviews yet.</p>
                            )}
                        </div>

                        <div className="border-t border-gray-100 pt-4 text-center">
                            <p className="text-sm text-gray-500 mb-3">Contact the owner directly to book a visit.</p>
                            <a href={`tel:${selectedAccommodation.contactPhone}`} className="block w-full">
                                <Button className="w-full" size="lg">
                                    <Phone className="w-4 h-4 mr-2" /> Call {selectedAccommodation.contactPhone}
                                </Button>
                            </a>
                        </div>
                    </div>
                )}
            </Modal>
        </div>
    );
};