import React, { useState, useMemo } from 'react';
import { Cabin, CabinStatus } from '../types';
import { Wifi, Zap, Power, Armchair, MapPin, Info, Lock } from 'lucide-react';

interface SeatMapProps {
    cabins: Cabin[];
    selectedCabinId?: string;
    onSelectCabin: (cabin: Cabin) => void;
    activeFloor: number | 'All';
    userWaitlist?: string[]; // Array of cabin IDs user is waitlisted for
    currentUserId?: string; // For detecting if seat is held by current user
}

// STRICTLY use owner-defined zone only - NO FALLBACK
const getZone = (cabin: Cabin): 'FRONT' | 'MIDDLE' | 'BACK' | null => {
    // Only return zone if explicitly set by owner
    if (cabin.zone && ['FRONT', 'MIDDLE', 'BACK'].includes(cabin.zone)) {
        return cabin.zone as 'FRONT' | 'MIDDLE' | 'BACK';
    }
    // NO FALLBACK - return null if not defined
    return null;
};

// Use owner-defined row label if available
const getRowLabel = (cabin: Cabin): string => {
    // Use owner-defined row label if set
    if (cabin.rowLabel) {
        return cabin.rowLabel.toUpperCase();
    }

    // Extract letter prefix if exists (e.g., "A1" -> "A")
    const match = cabin.number.match(/^([A-Za-z]+)/);
    if (match) return match[1].toUpperCase();

    // Otherwise generate from floor
    const rowLabels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    return rowLabels[cabin.floor - 1] || 'A';
};

const ZONE_CONFIG = {
    FRONT: {
        label: 'Front Zone',
        subtitle: 'Near entrance & AC',
        bgClass: 'bg-blue-50/50',
        borderClass: 'border-blue-200',
        icon: '❄️'
    },
    MIDDLE: {
        label: 'Middle Zone',
        subtitle: 'Balanced location',
        bgClass: 'bg-gray-50/50',
        borderClass: 'border-gray-200',
        icon: '📍'
    },
    BACK: {
        label: 'Back Zone',
        subtitle: 'Quiet corner',
        bgClass: 'bg-amber-50/50',
        borderClass: 'border-amber-200',
        icon: '🤫'
    }
};

const SEAT_STATUS_STYLES = {
    [CabinStatus.AVAILABLE]: {
        base: 'bg-gradient-to-br from-green-50 to-green-100 border-green-400 text-green-700 hover:from-green-100 hover:to-green-200 hover:border-green-500 cursor-pointer shadow-sm hover:shadow-md',
        dot: 'bg-green-500',
        ring: 'ring-green-200'
    },
    [CabinStatus.OCCUPIED]: {
        base: 'bg-gray-100 border-gray-300 text-gray-400 cursor-pointer hover:border-amber-400',
        dot: 'bg-gray-400',
        ring: 'ring-gray-200'
    },
    [CabinStatus.MAINTENANCE]: {
        base: 'bg-orange-50 border-orange-300 text-orange-400 cursor-not-allowed opacity-60',
        dot: 'bg-orange-400',
        ring: 'ring-orange-200'
    },
    [CabinStatus.RESERVED]: {
        base: 'bg-yellow-50 border-yellow-300 text-yellow-600 cursor-not-allowed',
        dot: 'bg-yellow-500',
        ring: 'ring-yellow-200'
    }
};

const getAmenityIcon = (amenity: string) => {
    const lower = amenity.toLowerCase();
    if (lower.includes('wifi')) return <Wifi className="w-3 h-3" />;
    if (lower.includes('ac')) return <Zap className="w-3 h-3" />;
    if (lower.includes('power') || lower.includes('plug')) return <Power className="w-3 h-3" />;
    if (lower.includes('chair')) return <Armchair className="w-3 h-3" />;
    return null;
};

export const SeatMap: React.FC<SeatMapProps> = ({
    cabins,
    selectedCabinId,
    onSelectCabin,
    activeFloor,
    userWaitlist = [],
    currentUserId
}) => {
    const [hoveredCabin, setHoveredCabin] = useState<Cabin | null>(null);
    const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

    // Helper: Check if cabin is held by another user
    const isHeldByOther = (cabin: Cabin): boolean => {
        if (!cabin.heldByUserId || !cabin.holdExpiresAt) return false;
        if (cabin.heldByUserId === currentUserId) return false;
        // Check if hold is still valid
        try {
            const expires = new Date(cabin.holdExpiresAt);
            return new Date() < expires;
        } catch {
            return false;
        }
    };

    // Filter cabins by floor
    const filteredCabins = useMemo(() => {
        if (activeFloor === 'All') return cabins;
        return cabins.filter(c => c.floor === activeFloor);
    }, [cabins, activeFloor]);

    // Get unique zones that exist in the data (ONLY owner-defined zones)
    const existingZones = useMemo(() => {
        const zones = new Set<'FRONT' | 'MIDDLE' | 'BACK'>();
        filteredCabins.forEach(cabin => {
            const zone = getZone(cabin);
            if (zone) zones.add(zone);
        });
        // Return in logical order
        return ['FRONT', 'MIDDLE', 'BACK'].filter(z => zones.has(z as any)) as ('FRONT' | 'MIDDLE' | 'BACK')[];
    }, [filteredCabins]);

    // Group cabins by zone (ONLY owner-defined zones, no auto-assignment)
    const { groupedByZone, unassignedCabins } = useMemo(() => {
        const groups: Record<'FRONT' | 'MIDDLE' | 'BACK', Cabin[]> = {
            FRONT: [],
            MIDDLE: [],
            BACK: []
        };
        const unassigned: Cabin[] = [];

        filteredCabins.forEach(cabin => {
            const zone = getZone(cabin);
            // ONLY add to group if zone is explicitly defined by owner
            if (zone) {
                groups[zone].push(cabin);
            } else {
                // Cabins without zone go to unassigned
                unassigned.push(cabin);
            }
        });

        // Sort within each zone by row label first, then by number
        const sortCabins = (cabins: Cabin[]) => {
            cabins.sort((a, b) => {
                // First sort by row label
                const rowA = getRowLabel(a);
                const rowB = getRowLabel(b);
                if (rowA !== rowB) return rowA.localeCompare(rowB);

                // Then by numeric portion
                const numA = parseInt(a.number.replace(/\D/g, '')) || 0;
                const numB = parseInt(b.number.replace(/\D/g, '')) || 0;
                return numA - numB;
            });
        };

        Object.values(groups).forEach(sortCabins);
        sortCabins(unassigned);

        return { groupedByZone: groups, unassignedCabins: unassigned };
    }, [filteredCabins]);

    const handleMouseEnter = (cabin: Cabin, e: React.MouseEvent) => {
        const rect = (e.target as HTMLElement).getBoundingClientRect();
        setTooltipPosition({
            x: rect.left + rect.width / 2,
            y: rect.top - 10
        });
        setHoveredCabin(cabin);
    };

    const handleMouseLeave = () => {
        setHoveredCabin(null);
    };

    const handleClick = (cabin: Cabin) => {
        if (cabin.status === CabinStatus.MAINTENANCE) return;
        // Block clicks on seats held by other users
        if (isHeldByOther(cabin)) return;
        onSelectCabin(cabin);
    };

    const renderSeat = (cabin: Cabin) => {
        const isSelected = cabin.id === selectedCabinId;
        const isWaitlisted = userWaitlist.includes(cabin.id);
        const isHeld = isHeldByOther(cabin);
        const styles = SEAT_STATUS_STYLES[cabin.status];
        const isClickable = cabin.status !== CabinStatus.MAINTENANCE && !isHeld;

        return (
            <div
                key={cabin.id}
                onClick={() => handleClick(cabin)}
                onMouseEnter={(e) => handleMouseEnter(cabin, e)}
                onMouseLeave={handleMouseLeave}
                className={`
                    relative p-2 md:p-3 rounded-xl border-2 transition-all duration-300 ease-out
                    flex flex-col items-center justify-center min-h-[70px] md:min-h-[85px]
                    ${!isSelected && !isHeld ? styles.base : ''}
                    ${isWaitlisted && !isSelected && !isHeld ? 'ring-2 ring-amber-400 ring-offset-1' : ''}
                    ${isHeld ? `
                        bg-gradient-to-br from-orange-200 to-orange-300
                        border-orange-400
                        text-orange-700
                        opacity-70
                        cursor-not-allowed
                        animate-pulse
                    ` : ''}
                    ${isSelected ? `
                        bg-gradient-to-br from-emerald-400 to-emerald-600 
                        border-emerald-700 
                        text-white 
                        scale-110 
                        shadow-lg shadow-emerald-500/40
                        ring-4 ring-emerald-300 ring-offset-2
                        z-10
                    ` : ''}
                    ${!isClickable ? 'cursor-not-allowed' : 'cursor-pointer'}
                `}
            >
                {/* HELD Badge - Seat held by another user */}
                {isHeld && (
                    <div className="absolute -top-2 -right-2 bg-orange-500 rounded-full p-1 shadow-md">
                        <Lock className="w-3 h-3 text-white" />
                    </div>
                )}

                {/* Selection Checkmark - BookMyShow Style */}
                {isSelected && (
                    <div className="absolute -top-2 -right-2 bg-white rounded-full p-0.5 shadow-lg animate-bounce">
                        <svg className="w-5 h-5 text-emerald-600" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                    </div>
                )}

                {/* Status Dot - Hidden when selected or held */}
                {!isSelected && !isHeld && (
                    <div className={`absolute top-1.5 right-1.5 w-2 h-2 rounded-full ${styles.dot}`} />
                )}

                {/* Waitlist Badge */}
                {isWaitlisted && !isSelected && !isHeld && (
                    <div className="absolute -top-1 -left-1 bg-amber-500 text-white text-[8px] px-1.5 py-0.5 rounded-full font-bold">
                        WAIT
                    </div>
                )}

                {/* Seat Number */}
                <span className={`text-base md:text-lg font-bold ${isSelected ? 'text-white' : ''} ${isHeld ? 'text-orange-700' : ''}`}>
                    {cabin.number}
                </span>

                {/* Price */}
                <span className={`text-[10px] md:text-xs font-medium ${isSelected ? 'text-emerald-100' : ''} ${isHeld ? 'text-orange-600' : 'opacity-70'}`}>
                    ₹{cabin.price}
                </span>

                {/* Amenity Icons */}
                <div className={`flex gap-0.5 mt-1 ${isSelected ? 'opacity-80' : 'opacity-60'}`}>
                    {cabin.amenities.slice(0, 2).map((amenity, i) => (
                        <span key={i}>{getAmenityIcon(amenity)}</span>
                    ))}
                </div>
            </div>
        );
    };

    const renderZone = (zone: 'FRONT' | 'MIDDLE' | 'BACK') => {
        const zoneCabins = groupedByZone[zone];
        if (zoneCabins.length === 0) return null;

        const config = ZONE_CONFIG[zone];

        return (
            <div
                key={zone}
                className={`rounded-xl border ${config.borderClass} ${config.bgClass} p-4 mb-4`}
            >
                {/* Zone Header */}
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200/50">
                    <span className="text-lg">{config.icon}</span>
                    <div>
                        <h4 className="font-semibold text-gray-800 text-sm">{config.label}</h4>
                        <p className="text-xs text-gray-500">{config.subtitle}</p>
                    </div>
                </div>

                {/* Seats Grid */}
                <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2 md:gap-3">
                    {zoneCabins.map(cabin => renderSeat(cabin))}
                </div>
            </div>
        );
    };

    return (
        <div className="relative">
            {/* Legend */}
            <div className="flex flex-wrap gap-4 mb-4 p-3 bg-white rounded-lg border border-gray-100 shadow-sm">
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-gradient-to-br from-green-400 to-green-500 shadow-sm" />
                    <span className="text-xs font-medium text-gray-600">Available</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-sm ring-2 ring-emerald-300">
                        <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                    </div>
                    <span className="text-xs font-medium text-gray-600">Selected</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-gradient-to-br from-orange-200 to-orange-400 shadow-sm animate-pulse">
                        <Lock className="w-4 h-4 text-orange-700 p-0.5" />
                    </div>
                    <span className="text-xs font-medium text-gray-600">Held</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-gray-300 shadow-sm" />
                    <span className="text-xs font-medium text-gray-600">Taken</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-orange-300 shadow-sm" />
                    <span className="text-xs font-medium text-gray-600">Maintenance</span>
                </div>
            </div>

            {/* Zones - Only render zones that have cabins */}
            {renderZone('FRONT')}
            {renderZone('MIDDLE')}
            {renderZone('BACK')}

            {/* Unassigned Cabins (no zone defined by owner) */}
            {unassignedCabins.length > 0 && (
                <div className="rounded-xl border border-gray-200 bg-white p-4 mb-4">
                    <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200/50">
                        <span className="text-lg">📋</span>
                        <div>
                            <h4 className="font-semibold text-gray-800 text-sm">All Seats</h4>
                            <p className="text-xs text-gray-500">Available seats</p>
                        </div>
                    </div>
                    <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2 md:gap-3">
                        {unassignedCabins.map(cabin => renderSeat(cabin))}
                    </div>
                </div>
            )}

            {/* Empty State */}
            {filteredCabins.length === 0 && (
                <div className="text-center py-12 text-gray-400">
                    <MapPin className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p className="font-medium">No seats available on this floor</p>
                    <p className="text-sm">Try selecting a different floor</p>
                </div>
            )}

            {/* Tooltip */}
            {hoveredCabin && (
                <div
                    className="fixed z-50 bg-gray-900 text-white px-4 py-3 rounded-xl shadow-xl transform -translate-x-1/2 -translate-y-full pointer-events-none animate-in fade-in zoom-in-95 duration-150"
                    style={{
                        left: tooltipPosition.x,
                        top: tooltipPosition.y
                    }}
                >
                    <div className="flex items-center gap-2 mb-1">
                        <span className="font-bold text-lg">{hoveredCabin.number}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${hoveredCabin.status === CabinStatus.AVAILABLE
                            ? 'bg-green-500/20 text-green-300'
                            : 'bg-gray-500/20 text-gray-300'
                            }`}>
                            {hoveredCabin.status}
                        </span>
                    </div>
                    <div className="text-sm text-gray-300 mb-1">Floor {hoveredCabin.floor}</div>
                    <div className="font-semibold text-indigo-300">₹{hoveredCabin.price}/month</div>
                    {hoveredCabin.amenities.length > 0 && (
                        <div className="flex gap-1 mt-2 pt-2 border-t border-gray-700">
                            {hoveredCabin.amenities.map((a, i) => (
                                <span key={i} className="text-xs bg-gray-700 px-2 py-0.5 rounded">{a}</span>
                            ))}
                        </div>
                    )}
                    {/* Arrow */}
                    <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 translate-y-full">
                        <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-l-transparent border-r-transparent border-t-gray-900" />
                    </div>
                </div>
            )}
        </div>
    );
};

export default SeatMap;
