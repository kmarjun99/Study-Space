import type { Cabin, ReadingRoom } from '../types';

export type OnboardingStep = 1 | 2 | 3 | 4;

export interface SavedDurationConfig {
    enabledDurations: string[];
    prices: Record<string, number>;
}

const sortedStrings = (values: string[] = []) =>
    [...values].map(value => value.trim()).filter(Boolean).sort();

export const normalizeVenueDetails = (data: Partial<ReadingRoom>) => ({
    name: data.name?.trim() || '',
    contactPhone: data.contactPhone?.trim() || '',
    state: data.state?.trim() || '',
    city: data.city?.trim() || '',
    locality: data.locality?.trim() || '',
    pincode: data.pincode?.trim() || '',
    address: data.address?.trim() || '',
    latitude: data.latitude ?? null,
    longitude: data.longitude ?? null,
    priceStart: Number(data.priceStart || 0),
    amenities: sortedStrings(data.amenities || []),
});

export const isVenueDetailsComplete = (data?: Partial<ReadingRoom> | null) => {
    if (!data) return false;
    const details = normalizeVenueDetails(data);
    return Boolean(
        details.name
        && details.contactPhone
        && details.state
        && details.city
        && details.pincode
        && details.address
        && details.priceStart > 0
        && details.amenities.length > 0
    );
};

export const areVenueDetailsEqual = (
    current: Partial<ReadingRoom>,
    saved?: Partial<ReadingRoom> | null,
) => JSON.stringify(normalizeVenueDetails(current))
    === JSON.stringify(normalizeVenueDetails(saved || {}));

export const normalizeImages = (images: string[] = []) =>
    images.map(image => image.trim()).filter(Boolean);

export const areImagesEqual = (current: string[], saved: string[]) =>
    JSON.stringify(normalizeImages(current)) === JSON.stringify(normalizeImages(saved));

export const isPhotosComplete = (images: string[] = []) =>
    normalizeImages(images).length >= 4;

export const isCabinsComplete = (cabins: Cabin[] = []) => cabins.length > 0;

export const normalizeDurationConfig = (
    enabledDurations: string[] = [],
    prices: Record<string, number> = {},
): SavedDurationConfig => {
    const enabled = sortedStrings(enabledDurations);
    return {
        enabledDurations: enabled,
        prices: Object.fromEntries(
            enabled.map(duration => [duration, Number(prices[duration] || 0)]),
        ),
    };
};

export const isDurationConfigComplete = (
    enabledDurations: string[] = [],
    prices: Record<string, number> = {},
) => {
    const normalized = normalizeDurationConfig(enabledDurations, prices);
    return normalized.enabledDurations.length > 0
        && normalized.enabledDurations.every(duration => normalized.prices[duration] > 0);
};

export const areDurationConfigsEqual = (
    enabledDurations: string[],
    prices: Record<string, number>,
    saved?: SavedDurationConfig | null,
) => {
    if (!saved) return false;
    return JSON.stringify(normalizeDurationConfig(enabledDurations, prices))
        === JSON.stringify(normalizeDurationConfig(saved.enabledDurations, saved.prices));
};
