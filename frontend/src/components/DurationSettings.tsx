/**
 * DurationSettings Component
 * Allows reading room owners to configure booking durations and pricing
 */

import React, { useState, useEffect } from 'react';
import { BookingDurationType, ReadingRoom, DurationPrice } from '../types';
import { Button, Card } from './UI';
import { 
  ALL_DURATION_TYPES, 
  formatDurationLabel, 
  formatPrice,
  DURATION_CONFIGS 
} from '../utils/bookingDurations';
import { toast } from 'react-hot-toast';
import { CheckCircle, X, DollarSign, Clock, Save } from 'lucide-react';
import api from '../services/api';

interface DurationSettingsProps {
  readingRoom: ReadingRoom;
  onUpdate?: (updated: ReadingRoom) => void;
}

export const DurationSettings: React.FC<DurationSettingsProps> = ({ 
  readingRoom, 
  onUpdate 
}) => {
  // Local state for editing
  const [enabledDurations, setEnabledDurations] = useState<BookingDurationType[]>(
    readingRoom.allowedBookingDurations || ['1_MONTH']
  );
  const [prices, setPrices] = useState<DurationPrice>(
    readingRoom.durationPrices || {}
  );
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Track changes
  useEffect(() => {
    const durationsChanged = JSON.stringify(enabledDurations.sort()) !== 
                            JSON.stringify((readingRoom.allowedBookingDurations || ['1_MONTH']).sort());
    const pricesChanged = JSON.stringify(prices) !== 
                         JSON.stringify(readingRoom.durationPrices || {});
    setHasChanges(durationsChanged || pricesChanged);
  }, [enabledDurations, prices, readingRoom]);

  const handleToggleDuration = (durationType: BookingDurationType) => {
    setEnabledDurations(prev => {
      if (prev.includes(durationType)) {
        const newDurations = prev.filter(d => d !== durationType);
        // Ensure at least one duration is enabled
        if (newDurations.length === 0) {
          toast.error('At least one booking duration must be enabled');
          return prev;
        }
        return newDurations;
      } else {
        return [...prev, durationType];
      }
    });
  };

  const handlePriceChange = (durationType: BookingDurationType, value: string) => {
    const numValue = value === '' ? null : parseFloat(value);
    setPrices(prev => ({
      ...prev,
      [durationType]: numValue
    }));
  };

  const validateSettings = (): boolean => {
    // Check if at least one duration is enabled
    if (enabledDurations.length === 0) {
      toast.error('At least one booking duration must be enabled');
      return false;
    }

    // Check if all enabled durations have valid prices
    const missingPrices = enabledDurations.filter(duration => {
      const price = prices[duration];
      return !price || price <= 0;
    });

    if (missingPrices.length > 0) {
      const labels = missingPrices.map(d => formatDurationLabel(d)).join(', ');
      toast.error(`Please set valid prices for: ${labels}`);
      return false;
    }

    return true;
  };

  const handleSave = async () => {
    if (!validateSettings()) return;

    setIsSaving(true);
    try {
      // Route through the shared axios instance (baseURL + auth header come
      // for free). The prior raw-fetch + env-var pattern baked
      // "http://localhost:8000" into the prod bundle when VITE_API_BASE_URL
      // was unset at build time, breaking saves on the live site.
      const { data: updated } = await api.put(
        `/api/reading-rooms/${readingRoom.id}/duration-config`,
        {
          allowed_booking_durations: enabledDurations,
          duration_prices: prices,
        },
      );
      toast.success('Duration settings saved successfully!');

      if (onUpdate) {
        onUpdate(updated);
      }

      setHasChanges(false);
    } catch (error: any) {
      const detail = error?.response?.data?.detail
        || error?.message
        || 'Failed to save settings';
      console.error('Failed to save duration settings:', error);
      toast.error(detail);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setEnabledDurations(readingRoom.allowedBookingDurations || ['1_MONTH']);
    setPrices(readingRoom.durationPrices || {});
    setHasChanges(false);
  };

  return (
    <Card className="p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Booking Duration Settings</h3>
            <p className="text-sm text-gray-500 mt-1">
              Configure available booking durations and set custom prices for each option.
            </p>
          </div>
          {hasChanges && (
            <Badge variant="warning" className="text-xs">
              Unsaved Changes
            </Badge>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {ALL_DURATION_TYPES.map((durationType) => {
          const isEnabled = enabledDurations.includes(durationType);
          const price = prices[durationType];
          const config = DURATION_CONFIGS[durationType];

          return (
            <div
              key={durationType}
              className={`p-4 rounded-lg border-2 transition-all ${
                isEnabled 
                  ? 'border-indigo-200 bg-indigo-50/50' 
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                {/* Duration Info */}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <button
                      onClick={() => handleToggleDuration(durationType)}
                      className={`flex items-center justify-center w-6 h-6 rounded border-2 transition-all ${
                        isEnabled
                          ? 'bg-indigo-600 border-indigo-600'
                          : 'bg-white border-gray-300 hover:border-indigo-400'
                      }`}
                    >
                      {isEnabled && <CheckCircle className="w-4 h-4 text-white" />}
                    </button>
                    <span className="font-semibold text-gray-900">
                      {config.label}
                    </span>
                    <span className="text-xs text-gray-500">
                      ({config.days} days)
                    </span>
                  </div>

                  {/* Price Input */}
                  <div className={`ml-8 transition-opacity ${isEnabled ? 'opacity-100' : 'opacity-50'}`}>
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1 max-w-xs">
                        <DollarSign className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
                        <input
                          type="number"
                          min="0"
                          step="1"
                          placeholder="Set price"
                          value={price || ''}
                          onChange={(e) => handlePriceChange(durationType, e.target.value)}
                          disabled={!isEnabled}
                          className={`pl-9 pr-4 py-2 border rounded-lg text-sm w-full focus:outline-none focus:ring-2 ${
                            isEnabled
                              ? price && price > 0
                                ? 'border-green-300 focus:ring-green-500 bg-white'
                                : 'border-amber-300 focus:ring-amber-500 bg-white'
                              : 'border-gray-200 bg-gray-100 cursor-not-allowed'
                          }`}
                        />
                      </div>
                      {isEnabled && price && price > 0 && (
                        <span className="text-sm font-medium text-green-600">
                          {formatPrice(price)}
                        </span>
                      )}
                    </div>
                    {isEnabled && (!price || price <= 0) && (
                      <p className="text-xs text-amber-600 mt-1 ml-1">
                        Price required to enable booking
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Action Buttons */}
      <div className="mt-6 pt-6 border-t border-gray-200 flex items-center justify-between">
        <div className="text-sm text-gray-600">
          {enabledDurations.length} duration{enabledDurations.length !== 1 ? 's' : ''} enabled
        </div>
        <div className="flex gap-3">
          {hasChanges && (
            <Button
              variant="ghost"
              onClick={handleReset}
              disabled={isSaving}
            >
              Cancel
            </Button>
          )}
          <Button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            className="flex items-center gap-2"
          >
            {isSaving ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                Saving...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
};

// Badge component if not in UI
const Badge: React.FC<{ variant?: string; className?: string; children: React.ReactNode }> = ({ 
  variant = 'default', 
  className = '', 
  children 
}) => {
  const variants = {
    default: 'bg-gray-100 text-gray-800',
    warning: 'bg-amber-100 text-amber-800',
    success: 'bg-green-100 text-green-800',
  };
  
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${variants[variant as keyof typeof variants] || variants.default} ${className}`}>
      {children}
    </span>
  );
};
