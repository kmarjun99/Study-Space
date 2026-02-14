import React from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';

export interface SearchFilters {
  search: string;
  city?: string;
  priceMin?: number;
  priceMax?: number;
  gender?: 'MALE' | 'FEMALE' | 'ANY' | '';
  type?: 'PG' | 'HOSTEL' | 'FLAT' | '';
  amenities?: string[];
}

interface SearchFilterBarProps {
  filters: SearchFilters;
  onFilterChange: (filters: SearchFilters) => void;
  onReset: () => void;
  showAdvanced?: boolean;
}

const COMMON_AMENITIES = [
  'WiFi',
  'AC',
  'Food',
  'Laundry',
  'Security',
  'Parking',
  'Gym',
  'Mess'
];

export const SearchFilterBar: React.FC<SearchFilterBarProps> = ({
  filters,
  onFilterChange,
  onReset,
  showAdvanced = false
}) => {
  const [expanded, setExpanded] = React.useState(showAdvanced);

  const hasActiveFilters = 
    filters.city || 
    filters.priceMin || 
    filters.priceMax || 
    filters.gender || 
    filters.type || 
    (filters.amenities && filters.amenities.length > 0);

  const handleAmenityToggle = (amenity: string) => {
    const current = filters.amenities || [];
    const updated = current.includes(amenity)
      ? current.filter(a => a !== amenity)
      : [...current, amenity];
    onFilterChange({ ...filters, amenities: updated });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Main Search Bar */}
      <div className="p-4">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
            <input
              type="text"
              placeholder="Search by name, location..."
              value={filters.search}
              onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
          >
            <SlidersHorizontal className="h-5 w-5" />
            <span className="hidden sm:inline">Filters</span>
            {hasActiveFilters && (
              <span className="bg-blue-600 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
                {Object.values(filters).filter(v => v && (Array.isArray(v) ? v.length > 0 : true)).length - 1}
              </span>
            )}
          </button>
          {hasActiveFilters && (
            <button
              onClick={onReset}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 flex items-center gap-1"
              title="Clear all filters"
            >
              <X className="h-5 w-5" />
              <span className="hidden sm:inline">Clear</span>
            </button>
          )}
        </div>
      </div>

      {/* Advanced Filters */}
      {expanded && (
        <div className="border-t border-gray-200 p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* City */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                City
              </label>
              <input
                type="text"
                placeholder="e.g. Mumbai"
                value={filters.city || ''}
                onChange={(e) => onFilterChange({ ...filters, city: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Price Min */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Price (₹)
              </label>
              <input
                type="number"
                placeholder="0"
                value={filters.priceMin || ''}
                onChange={(e) => onFilterChange({ ...filters, priceMin: Number(e.target.value) || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Price Max */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Price (₹)
              </label>
              <input
                type="number"
                placeholder="50000"
                value={filters.priceMax || ''}
                onChange={(e) => onFilterChange({ ...filters, priceMax: Number(e.target.value) || undefined })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Gender */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Gender
              </label>
              <select
                value={filters.gender || ''}
                onChange={(e) => onFilterChange({ ...filters, gender: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">All</option>
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="ANY">Any</option>
              </select>
            </div>

            {/* Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Type
              </label>
              <select
                value={filters.type || ''}
                onChange={(e) => onFilterChange({ ...filters, type: e.target.value as any })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">All</option>
                <option value="PG">PG</option>
                <option value="HOSTEL">Hostel</option>
                <option value="FLAT">Flat</option>
              </select>
            </div>
          </div>

          {/* Amenities */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Amenities
            </label>
            <div className="flex flex-wrap gap-2">
              {COMMON_AMENITIES.map(amenity => (
                <button
                  key={amenity}
                  onClick={() => handleAmenityToggle(amenity)}
                  className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                    filters.amenities?.includes(amenity)
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {amenity}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
