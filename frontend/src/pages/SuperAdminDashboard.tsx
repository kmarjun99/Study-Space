
import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppState } from '../types';

// Extracted View Components
import { SuperAdminDashboardHome } from './SuperAdminDashboardHome';
import { SuperAdminSupplyView } from './SuperAdminSupplyView';
import { SuperAdminBookingsView } from './SuperAdminBookingsView';
import { SuperAdminFinanceView } from './SuperAdminFinanceView';
import { SuperAdminTrustView } from './SuperAdminTrustView';
import { SuperAdminAnalyticsView } from './SuperAdminAnalyticsView';
import { SuperAdminCitiesView } from './SuperAdminCitiesView';
import { SuperAdminUsersView } from './SuperAdminUsersView';
import { SuperAdminAdsView } from './SuperAdminAdsView';
import { SuperAdminSupportManager } from './SuperAdminSupportManager';
import { SuperAdminPromotionManager } from './SuperAdminPromotionManager';
import { SuperAdminSubscriptionPlans } from './SuperAdminSubscriptionPlans';
import { SuperAdminReadingRoomReview } from './SuperAdminReadingRoomReview';
import { SuperAdminAccommodationReview } from './SuperAdminAccommodationReview';
import { LocationManagement } from '../components/LocationManagement';

interface SuperAdminDashboardProps {
    state: AppState;
}

export const SuperAdminDashboard: React.FC<SuperAdminDashboardProps> = ({ state }) => {
    const location = useLocation();

    // Scroll to top on route change
    useEffect(() => {
        window.scrollTo(0, 0);
    }, [location.pathname]);

    return (
        <div className="w-full">
            <Routes>
                <Route path="/" element={<SuperAdminDashboardHome state={state} />} />
                <Route path="/analytics" element={<SuperAdminAnalyticsView users={state.users} readingRooms={state.readingRooms} bookings={state.bookings} />} />
                <Route path="/users" element={<SuperAdminUsersView users={state.users} />} />
                <Route path="/cities" element={<SuperAdminCitiesView />} />
                <Route path="/supply" element={<SuperAdminSupplyView />} />
                <Route path="/bookings" element={<SuperAdminBookingsView />} />
                <Route path="/finance" element={<SuperAdminFinanceView />} />
                <Route path="/promotions" element={<SuperAdminPromotionManager />} />
                <Route path="/ads" element={<SuperAdminAdsView />} />
                <Route path="/tickets" element={<SuperAdminSupportManager />} />
                <Route path="/plans" element={<SuperAdminSubscriptionPlans />} />
                <Route path="/trust" element={<SuperAdminTrustView users={state.users} currentUser={state.currentUser} />} />

                {/* Sub-routes for reviews */}
                <Route path="/supply/verify-venue/:id" element={<SuperAdminReadingRoomReview />} />
                <Route path="/supply/verify-housing/:id" element={<SuperAdminAccommodationReview />} />

                <Route path="/locations" element={<LocationManagement />} />

                {/* Fallback */}
                <Route path="*" element={<Navigate to="/super-admin" replace />} />
            </Routes>
        </div>
    );
};
