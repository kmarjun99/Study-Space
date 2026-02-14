
import React, { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppState, Cabin, CabinStatus, User, ReadingRoom } from '../types';
import { Button, Card, Badge, Modal, LiveIndicator, Input } from '../components/UI';
import { AdBanner } from '../components/AdBanner';
import { getTargetedAd } from '../services/adService';
import { paymentService } from '../services/paymentService';

import { Wifi, Zap, CheckCircle, Filter, MapPin, Phone, ArrowLeft, Star, Clock, BellRing, Search, Layers } from 'lucide-react';
import { LocationSearch, LocationResult } from '../components/LocationSearch';
import { useCityPreference } from '../hooks/useCityPreference';
import { FavoriteButton } from '../components/FavoriteButton';


interface BookCabinProps {
  state: AppState;
  user: User;
  onBookCabin: (cabinId: string, durationMonths: number) => Promise<void>;
  onJoinWaitlist: (cabinId: string) => void;
}

export const BookCabin: React.FC<BookCabinProps> = ({ state, user, onBookCabin, onJoinWaitlist }) => {
  const navigate = useNavigate();
  const [selectedVenue, setSelectedVenue] = useState<ReadingRoom | null>(null);

  const [selectedCabin, setSelectedCabin] = useState<Cabin | null>(null);
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [isWaitlistModalOpen, setIsWaitlistModalOpen] = useState(false);
  const [paymentStep, setPaymentStep] = useState<'details' | 'payment' | 'success'>('details');
  const [duration, setDuration] = useState(1);

  // Filters
  const [activeFloor, setActiveFloor] = useState<number | 'All'>('All');
  const [amenityFilter, setAmenityFilter] = useState<string>('all');
  const [seatSearch, setSeatSearch] = useState('');

  // Ad State
  const [ads, setAds] = useState<any[]>([]);

  // Fetch Ads
  useEffect(() => {
    const fetchAds = async () => {
      try {
        const { adService } = await import('../services/adService');
        const fetchedAds = await adService.getAds();
        setAds(fetchedAds);
      } catch (e) {
        console.error("BookCabin: Failed to load ads", e);
      }
    };
    fetchAds();
  }, []);

  const successAd = useMemo(() => getTargetedAd(ads, user.role, true, 'BOOKING_SUCCESS'), [ads, user.role]);

  // Compute available floors when venue changes
  const availableFloors = useMemo(() => {
    if (!selectedVenue) return [];
    const venueCabins = state.cabins.filter(c => c.readingRoomId === selectedVenue.id);
    const floors = new Set(venueCabins.map(c => c.floor));
    return Array.from(floors).sort((a, b) => Number(a) - Number(b));
  }, [selectedVenue, state.cabins]);

  // Auto-select 'All' when venue changes
  useEffect(() => {
    if (selectedVenue) {
      setActiveFloor('All');
    }
  }, [selectedVenue?.id]);

  // --- Handlers ---
  const handleVenueClick = (venue: ReadingRoom) => {
    setSelectedVenue(venue);
    setActiveFloor('All');
  };

  const handleBackToVenues = () => {
    setSelectedVenue(null);
    setSelectedCabin(null);
    setSeatSearch('');
  };

  const handleCabinClick = (cabin: Cabin) => {
    setSelectedCabin(cabin);

    if (cabin.status === CabinStatus.AVAILABLE) {
      setPaymentStep('details');
      setIsBookingModalOpen(true);
    } else if (cabin.status === CabinStatus.OCCUPIED) {
      const alreadyWaiting = state.waitlist.some(w => w.userId === user.id && w.cabinId === cabin.id);
      if (alreadyWaiting) {
        alert("You are already on the waitlist for this cabin.");
      } else {
        setIsWaitlistModalOpen(true);
      }
    }
  };


  const handlePayment = async () => {
    if (!selectedCabin || !selectedVenue) return;

    setPaymentStep('payment');

    try {
      // 1. Load Razorpay Script
      const isLoaded = await loadRazorpayScript();
      if (!isLoaded) {
        alert('Razorpay SDK failed to load. Please check your internet connection.');
        setPaymentStep('details');
        return;
      }

      // 2. Create Order on Backend
      const orderData = await paymentService.createOrder(selectedCabin.price * duration);

      // 3. Initialize Razorpay Options
      const options = {
        key: orderData.key_id, // Key ID from backend
        amount: orderData.amount,
        currency: orderData.currency,
        name: selectedVenue.name,
        description: `Booking for Cabin ${selectedCabin.number} (${duration} mo)`,
        image: selectedVenue.imageUrl || 'https://via.placeholder.com/150', // Fallback logo
        order_id: orderData.id, // Order ID from backend
        handler: async function (response: any) {
          try {
            // 4. Verify Payment on Backend
            await paymentService.verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature
            });

            // 5. Complete Booking (pass transaction info if needed, or just proceed)
            // Ideally, we pass the payment ID to onBookCabin to store it
            await onBookCabin(selectedCabin.id, duration);
            setPaymentStep('success');

          } catch (verificationError) {
            console.error("Payment Verification Failed", verificationError);
            alert("Payment verification failed. Please contact support if money was deducted.");
            setPaymentStep('details');
          }
        },
        prefill: {
          name: user.name,
          email: user.email,
          contact: user.phone || ''
        },
        theme: {
          color: '#4F46E5' // Indigo 600
        },
        modal: {
          ondismiss: function () {
            setPaymentStep('details');
          }
        }
      };

      // 4. Open Razorpay
      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (response: any) {
        alert(`Payment Failed: ${response.error.description}`);
        setPaymentStep('details');
      });
      rzp.open();

    } catch (error) {
      console.error("Payment Initiation Failed", error);
      alert("Could not initiate payment. Please try again.");
      setPaymentStep('details');
    }
  };

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

  const handleConfirmWaitlist = () => {
    if (selectedCabin) {
      onJoinWaitlist(selectedCabin.id);
      setIsWaitlistModalOpen(false);
    }
  };

  const filteredCabins = useMemo(() => {
    if (!selectedVenue) return [];
    return state.cabins
      .filter(c => c.readingRoomId === selectedVenue.id)
      .filter(c => {
        const matchFloor = activeFloor === 'All' || c.floor === activeFloor;
        const matchAmenity = amenityFilter === 'all' || c.amenities.includes(amenityFilter);
        const matchSearch = seatSearch === '' || c.number.toLowerCase().includes(seatSearch.toLowerCase());
        return matchFloor && matchAmenity && matchSearch;
      });
  }, [state.cabins, selectedVenue, activeFloor, amenityFilter, seatSearch]);

  // --- Helpers ---
  const getVenueRating = (venueId: string) => {
    const reviews = state.reviews.filter(r => r.readingRoomId === venueId);
    if (reviews.length === 0) return { average: 0, count: 0 };
    const total = reviews.reduce((acc, curr) => acc + curr.rating, 0);
    return { average: total / reviews.length, count: reviews.length };
  };

  // --- Views ---

  // City Preference (persisted in localStorage)
  const { cityPreference, setCityPreference, clearCityPreference, cityDisplayName } = useCityPreference();

  const [locationFilter, setLocationFilter] = useState(cityDisplayName || '');
  const [selectedLocation, setSelectedLocation] = useState<LocationResult | null>(cityPreference);
  const [isLocating, setIsLocating] = useState(false);
  const [userCoords, setUserCoords] = useState<{ lat: number, lng: number } | null>(null);

  // Sync with city preference on mount
  useEffect(() => {
    if (cityPreference && !selectedLocation) {
      setSelectedLocation(cityPreference);
      setLocationFilter(cityDisplayName);
    }
  }, [cityPreference, cityDisplayName]);

  // Helper to calculate distance (Haversine formula) in km
  const getDistanceFromLatLonInKm = (lat1: number, lon1: number, lat2: number, lon2: number) => {
    const R = 6371; // Radius of the earth in km
    const dLat = deg2rad(lat2 - lat1);
    const dLon = deg2rad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c; // Distance in km
  };

  const deg2rad = (deg: number) => {
    return deg * (Math.PI / 180);
  };

  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;
        setUserCoords({ lat: latitude, lng: longitude });

        // Reverse Geocode to get City/Area text for the search bar
        try {
          const response = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`);
          const data = await response.json();
          const city = data.address.city || data.address.town || data.address.village || data.address.suburb || '';
          if (city) {
            setLocationFilter(city);
          } else {
            setSeatSearch(''); // Clear text search if no city found, rely on sorting
            // Force a re-render or notify user they are sorted by distance
          }
        } catch (error) {
          console.error("Failed to reverse geocode:", error);
        } finally {
          setIsLocating(false);
        }
      },
      (error) => {
        console.error("Geolocation error:", error);
        alert("Unable to retrieve your location. Please check your browser settings.");
        setIsLocating(false);
      }
    );
  };

  // Update venue selection rendering to filter by location AND sort by distance if coords exist
  const filteredVenues = useMemo(() => {
    let venues = state.readingRooms;

    // 1. Location filter - prioritize selectedLocation, fallback to text search
    if (selectedLocation) {
      venues = venues.filter(venue => {
        // Match by locationId if available
        if (venue.locationId && venue.locationId === selectedLocation.id) {
          return true;
        }
        // Fallback: match by city
        const cityMatch = (venue.city || '').toLowerCase() === selectedLocation.city.toLowerCase();
        const localityMatch = selectedLocation.locality &&
          (venue.locality || '').toLowerCase() === selectedLocation.locality.toLowerCase();
        return cityMatch || localityMatch;
      });
    } else if (locationFilter) {
      const lowerFilter = locationFilter.toLowerCase();
      venues = venues.filter(venue =>
        (venue.city?.toLowerCase().includes(lowerFilter)) ||
        (venue.area?.toLowerCase().includes(lowerFilter)) ||
        (venue.address.toLowerCase().includes(lowerFilter)) ||
        (venue.name.toLowerCase().includes(lowerFilter))
      );
    }

    // 2. Distance Sort (if user location is known)
    if (userCoords) {
      // Clone array to sort
      venues = [...venues].sort((a, b) => {
        // Assume default coords if missing (e.g. city center) or skip
        // This is a robust fallback: if venue has no coords, put it at end
        const latA = a.latitude || 0;
        const lngA = a.longitude || 0;
        const latB = b.latitude || 0;
        const lngB = b.longitude || 0;

        if (latA === 0) return 1;
        if (latB === 0) return -1;

        const distA = getDistanceFromLatLonInKm(userCoords.lat, userCoords.lng, latA, lngA);
        const distB = getDistanceFromLatLonInKm(userCoords.lat, userCoords.lng, latB, lngB);

        return distA - distB;
      });
    }

    return venues;
  }, [state.readingRooms, locationFilter, selectedLocation, userCoords]);

  const renderVenueSelection = () => (
    <>
      {/* Venue Search Toolbar */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex-1 max-w-md">
          <LocationSearch
            value={locationFilter}
            placeholder="Search by City or Locality..."
            onSelect={(location) => {
              setSelectedLocation(location);
              setLocationFilter(location.display_name);
              setCityPreference(location); // Persist preference
            }}
            onClear={() => {
              setSelectedLocation(null);
              setLocationFilter('');
              clearCityPreference(); // Clear persisted preference
            }}
          />
        </div>

        {/* Current Location Button */}
        <button
          onClick={handleUseCurrentLocation}
          disabled={isLocating}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:text-indigo-600 transition-colors"
          title="Use My Current Location"
        >
          {isLocating ? (
            <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="22" x2="18" y1="12" y2="12" /><line x1="6" x2="2" y1="12" y2="12" /><line x1="12" x2="12" y1="6" y2="2" /><line x1="12" x2="12" y1="22" y2="18" /></svg>
          )}
          <span className="hidden sm:inline">Near Me</span>
        </button>

        {/* Show "Sorted by proximity" badge if active */}
        {userCoords && (
          <div className="hidden md:flex items-center text-xs text-green-600 bg-green-50 px-3 py-1 rounded-full border border-green-200 animate-in fade-in">
            <CheckCircle className="w-3 h-3 mr-1" /> Sorted by Proximity
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredVenues.length > 0 ? (
          filteredVenues.map(venue => {
            const rating = getVenueRating(venue.id);
            // Calculate distance for display if user location is known
            let distanceLabel = '';
            if (userCoords && venue.latitude && venue.longitude) {
              const d = getDistanceFromLatLonInKm(userCoords.lat, userCoords.lng, venue.latitude, venue.longitude);
              distanceLabel = d < 1 ? `${(d * 1000).toFixed(0)}m away` : `${d.toFixed(1)}km away`;
            }

            return (
              <Card key={venue.id} className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer group" >
                <div className="h-48 overflow-hidden relative bg-gray-200">
                  <img
                    src={venue.imageUrl}
                    alt={venue.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement;
                      target.onerror = null;
                      target.src = 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?auto=format&fit=crop&q=80&w=800';
                    }}
                  />
                  <div className="absolute bottom-2 right-2 bg-white/90 px-2 py-1 rounded-md text-xs font-bold text-indigo-900 shadow-sm">
                    Starts ₹{venue.priceStart}/mo
                  </div>
                  <div className="absolute top-2 right-2">
                    <FavoriteButton
                      readingRoomId={venue.id}
                      size="sm"
                    />
                  </div>
                </div>
                <div className="p-5">
                  <div className="flex justify-between items-start mb-1">
                    <h3 className="text-lg font-bold text-gray-900 group-hover:text-indigo-600 transition-colors">{venue.name}</h3>
                    {distanceLabel && <Badge variant="success" className="text-[10px] ml-2">{distanceLabel}</Badge>}
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {venue.city && <Badge variant="info" className="text-[10px]">{venue.city}</Badge>}
                  </div>
                  <div className="flex items-center text-xs text-gray-500 mb-3">
                    <span className="flex items-center mr-3">
                      <Star className="w-3 h-3 text-yellow-500 fill-yellow-500 mr-1" /> {rating.average > 0 ? rating.average.toFixed(1) : 'New'} ({rating.count})
                    </span>
                  </div>
                  <div className="flex items-start text-gray-500 text-sm mb-3">
                    <MapPin className="w-4 h-4 mr-1 mt-0.5 flex-shrink-0" />
                    <span className="line-clamp-1">{venue.address}</span>
                  </div>
                  <div className="space-y-2">
                    <Button onClick={() => navigate(`/student/reading-room/${venue.id}`)} className="w-full">
                      View Seats
                    </Button>

                  </div>
                </div>
              </Card>
            );
          })
        ) : (
          <div className="col-span-full py-12 text-center text-gray-500 bg-gray-50 rounded-lg dashed-border">
            No reading rooms found matching "{locationFilter}".
          </div>
        )}
      </div>
    </>
  );

  const renderCabinGrid = () => (
    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 gap-2 md:gap-3 mt-6">
      {filteredCabins.map(cabin => {
        const isWaitlisted = state.waitlist.some(w => w.userId === user.id && w.cabinId === cabin.id);
        const statusColors = {
          [CabinStatus.AVAILABLE]: 'bg-white border-green-500 text-green-700 hover:bg-green-50 cursor-pointer ring-1 ring-green-100 hover:shadow-md',
          [CabinStatus.OCCUPIED]: 'bg-gray-50 border-gray-200 text-gray-400 hover:border-amber-300 hover:text-amber-600 cursor-pointer',
          [CabinStatus.MAINTENANCE]: 'bg-orange-50 border-orange-200 text-orange-400 cursor-not-allowed',
          [CabinStatus.RESERVED]: 'bg-yellow-50 border-yellow-200 text-yellow-600 cursor-not-allowed',
        };

        return (
          <div
            key={cabin.id}
            onClick={() => handleCabinClick(cabin)}
            className={`
              relative p-2 rounded-lg border transition-all duration-200
              flex flex-col items-center justify-center min-h-[80px]
              ${statusColors[cabin.status]}
              ${isWaitlisted ? 'ring-2 ring-amber-400 bg-amber-50' : ''}
            `}
          >
            <span className="text-lg font-bold mb-1">{cabin.number}</span>

            {cabin.status === 'AVAILABLE' && (
              <div className="absolute top-1 right-1 w-1.5 h-1.5 bg-green-500 rounded-full"></div>
            )}
            {/* Amenities Icons Mini */}
            <div className="flex gap-0.5 justify-center opacity-50 scale-75">
              {cabin.amenities.includes('AC') && <Zap className="w-3 h-3" />}
              {cabin.amenities.includes('WiFi') && <Wifi className="w-3 h-3" />}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <LiveIndicator />
      {!selectedVenue ? (
        <>
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900">Select a Reading Room</h1>
            <p className="text-gray-500">Choose from our premium locations.</p>
          </div>
          {renderVenueSelection()}
        </>
      ) : (
        <>
          <div className="flex flex-col gap-4">
            {/* Header Navigation */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <button onClick={handleBackToVenues} className="text-indigo-600 hover:text-indigo-800 text-sm flex items-center mb-2 font-medium">
                  <ArrowLeft className="w-4 h-4 mr-1" /> Back to Venues
                </button>
                <h1 className="text-2xl font-bold text-gray-900">{selectedVenue.name}</h1>
                <p className="text-gray-500 text-sm flex items-center gap-2">
                  <MapPin className="w-4 h-4" /> {selectedVenue.address}
                </p>
              </div>

            </div>

            {/* Filters Toolbar */}
            <div className="bg-white p-3 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row gap-3 items-center justify-between">
              <div className="flex items-center gap-2 w-full md:w-auto">
                <div className="relative w-full md:w-48">
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Find Seat #..."
                    className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    value={seatSearch}
                    onChange={(e) => setSeatSearch(e.target.value)}
                  />
                </div>
                <select
                  className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={amenityFilter}
                  onChange={(e) => setAmenityFilter(e.target.value)}
                >
                  <option value="all">Amenities: All</option>
                  <option value="AC">AC Only</option>
                  <option value="WiFi">WiFi Only</option>
                </select>
              </div>

              {/* Legend */}
              <div className="flex gap-4 text-xs font-medium text-gray-600">
                <div className="flex items-center"><div className="w-3 h-3 rounded-full bg-green-500 mr-1.5"></div> Available</div>
                <div className="flex items-center"><div className="w-3 h-3 rounded-full bg-gray-300 mr-1.5"></div> Taken</div>
              </div>
            </div>
          </div>

          <Card className="p-0 overflow-hidden min-h-[500px] flex flex-col">
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

            <div className="p-4 md:p-6 flex-1">
              {filteredCabins.length > 0 ? renderCabinGrid() : (
                <div className="h-64 flex flex-col items-center justify-center text-gray-400">
                  <Search className="w-10 h-10 mb-2 opacity-20" />
                  <p>No cabins match your search.</p>
                </div>
              )}
            </div>
          </Card>
        </>
      )}

      {/* Booking Modal */}
      <Modal
        isOpen={isBookingModalOpen}
        onClose={() => { setIsBookingModalOpen(false); setPaymentStep('details'); }}
        title={paymentStep === 'success' ? 'Booking Confirmed!' : 'Cabin Reservation'}
      >
        {selectedCabin && selectedVenue && paymentStep === 'details' && (
          <div className="space-y-4">
            <div className="bg-indigo-50 p-6 rounded-xl text-center border border-indigo-100">
              <div className="text-xs text-indigo-400 font-bold uppercase mb-1">{selectedVenue.name}</div>
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
                Cabin <strong>{selectedCabin?.number}</strong> at {selectedVenue?.name} is reserved for you.
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
            <h3 className="text-lg font-bold text-gray-900">Cabin {selectedCabin?.number} is Occupied</h3>
            <p className="text-gray-500 text-sm mt-2">
              Would you like to be notified as soon as this cabin becomes available?
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
