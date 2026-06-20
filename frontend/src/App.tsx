
import React, { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams, useLocation } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { AuthPage } from './pages/Auth';  // Keep eager — first paint for anon users.

// =====================================================================
// Code-split per route. Each lazy() call becomes its own JS chunk at
// build time (Vite handles this automatically for dynamic imports).
// Initial load only fetches the Layout + Router + current route's chunk.
// `withDefault` wraps the named-export pages so they're compatible with
// React.lazy()'s default-export expectation without polluting each
// page's module signature.
//
// Critically: every returned lazy component carries a `.preload()` method
// that goes through the EXACT SAME loader function React.lazy uses
// internally. Calling it on hover (see lib/routePrefetch.ts) populates
// React.lazy's internal memoization — so the eventual click resolves
// from cache instead of duplicating the import. This also means a
// failed prefetch propagates the rejection through React.lazy's normal
// error path (caught by an ErrorBoundary), instead of silently
// poisoning the browser's module map with no UI feedback.
// =====================================================================
type LazyPage<P = any> = React.LazyExoticComponent<React.ComponentType<P>> & {
    preload: () => Promise<unknown>;
};

const withDefault = <T,>(
    loader: () => Promise<Record<string, T>>,
    name: string,
): LazyPage => {
    const wrapped = () => loader().then(m => ({
        default: m[name] as React.ComponentType<any>,
    }));
    const Component = lazy(wrapped) as LazyPage;
    Component.preload = wrapped;
    return Component;
};

// ---- Student chunk -----------------------------------------------------
const StudentDashboard       = withDefault(() => import('./pages/StudentDashboard'),       'StudentDashboard');
const BookCabin              = withDefault(() => import('./pages/BookCabin'),              'BookCabin');
const FindAccommodation      = withDefault(() => import('./pages/FindAccommodation'),      'FindAccommodation');
const AccommodationDetail    = withDefault(() => import('./pages/AccommodationDetail'),    'AccommodationDetail');
const ReadingRoomDetail      = withDefault(() => import('./pages/ReadingRoomDetail'),      'ReadingRoomDetail');
const StudentPayments        = withDefault(() => import('./pages/StudentPayments'),        'StudentPayments');
const StudentProfile         = withDefault(() => import('./pages/StudentProfile'),         'StudentProfile');
const MyWaitlists            = withDefault(() => import('./pages/MyWaitlists'),            'MyWaitlists');
const FavoritesPage          = withDefault(() => import('./pages/FavoritesPage'),          'FavoritesPage');
const StudentPrivacySettings = withDefault(() => import('./pages/StudentPrivacySettings'), 'StudentPrivacySettings');
const StudentMyIntelligence  = withDefault(() => import('./pages/StudentMyIntelligence'),  'StudentMyIntelligence');

// ---- Admin (owner) chunk -----------------------------------------------
const AdminDashboard         = withDefault(() => import('./pages/AdminDashboard'),         'AdminDashboard');
const AdminListings          = withDefault(() => import('./pages/AdminListings'),          'AdminListings');
const AdminVenue             = withDefault(() => import('./pages/AdminVenue'),             'AdminVenue');
const AdminAccommodation     = withDefault(() => import('./pages/AdminAccommodation'),     'AdminAccommodation');
const AdminMigrations        = withDefault(() => import('./pages/AdminMigrations'),        'AdminMigrations');
const AdminWaitlists         = withDefault(() => import('./pages/AdminWaitlists'),         'AdminWaitlists');
const AdminProfile           = withDefault(() => import('./pages/AdminProfile'),           'AdminProfile');
const AdminStudents          = withDefault(() => import('./pages/AdminStudents'),          'AdminStudents');
const AdminFinancials        = withDefault(() => import('./pages/AdminFinancials'),        'AdminFinancials');
const OwnerBilling           = withDefault(() => import('./pages/OwnerBilling'),           'OwnerBilling');
const OwnerSettings          = withDefault(() => import('./pages/OwnerSettings'),          'OwnerSettings');
const OwnerCompliance        = withDefault(() => import('./pages/OwnerCompliance'),        'OwnerCompliance');
const OwnerKYC               = withDefault(() => import('./pages/OwnerKYC'),               'OwnerKYC');
const OwnerSettlements       = withDefault(() => import('./pages/OwnerSettlements'),       'OwnerSettlements');
const OwnerInsights          = withDefault(() => import('./pages/OwnerInsights'),          'OwnerInsights');
const ListingBillingSettings = withDefault(() => import('./pages/ListingBillingSettings'), 'ListingBillingSettings');

// ---- Super-admin chunk -------------------------------------------------
const SuperAdminDashboard          = withDefault(() => import('./pages/SuperAdminDashboard'),          'SuperAdminDashboard');
const SuperAdminProfile            = withDefault(() => import('./pages/SuperAdminProfile'),            'SuperAdminProfile');
const SuperAdminSettings           = withDefault(() => import('./pages/SuperAdminSettings'),           'SuperAdminSettings');
const SuperAdminAccommodationReview = withDefault(() => import('./pages/SuperAdminAccommodationReview'), 'SuperAdminAccommodationReview');
const SuperAdminReadingRoomReview  = withDefault(() => import('./pages/SuperAdminReadingRoomReview'),  'SuperAdminReadingRoomReview');
const SuperAdminTaxConfig          = withDefault(() => import('./pages/SuperAdminTaxConfig'),          'SuperAdminTaxConfig');
const SuperAdminSettlements        = withDefault(() => import('./pages/SuperAdminSettlements'),        'SuperAdminSettlements');
const SuperAdminKYCReview          = withDefault(() => import('./pages/SuperAdminKYCReview'),          'SuperAdminKYCReview');
const SuperAdminLedger             = withDefault(() => import('./pages/SuperAdminLedger'),             'SuperAdminLedger');
const SuperAdminIntelligence       = withDefault(() => import('./pages/SuperAdminIntelligence'),       'SuperAdminIntelligence');
const SuperAdminSegments           = withDefault(() => import('./pages/SuperAdminSegments'),           'SuperAdminSegments');
const SuperAdminCampaigns          = withDefault(() => import('./pages/SuperAdminCampaigns'),          'SuperAdminCampaigns');
const SuperAdminNotificationRules  = withDefault(() => import('./pages/SuperAdminNotificationRules'),  'SuperAdminNotificationRules');
const SuperAdminAttribution        = withDefault(() => import('./pages/SuperAdminAttribution'),        'SuperAdminAttribution');
const SuperAdminInsightsDashboard  = withDefault(() => import('./pages/SuperAdminInsightsDashboard'),  'SuperAdminInsightsDashboard');
const SuperAdminExperiments        = withDefault(() => import('./pages/SuperAdminExperiments'),        'SuperAdminExperiments');
const SuperAdminCohorts            = withDefault(() => import('./pages/SuperAdminCohorts'),            'SuperAdminCohorts');

// ---- Shared / cross-role ------------------------------------------------
const SupportPage     = withDefault(() => import('./pages/Support'),            'SupportPage');
const MessagesPage    = withDefault(() => import('./pages/MessagesPage'),       'MessagesPage');
const MockPaymentGateway = lazy(() => import('./pages/MockPaymentGateway'));  // default export

// React-side public/SEO pages have been removed — the SEO surface is now
// served entirely by FastAPI's Jinja2 routes (/reading-rooms/{city},
// /guides/*, etc.). Real users only ever see the auth screen or the
// logged-in app shell.

// =====================================================================
// Path-to-preloader registry. Single source of truth for both lazy()
// loading and hover prefetch — when both use the same wrapped function,
// React.lazy()'s internal memoization deduplicates. lib/routePrefetch.ts
// reads from this map; nav hover triggers warm the lazy cache so the
// subsequent click resolves synchronously.
// =====================================================================
export const ROUTE_PRELOADERS: Record<string, () => Promise<unknown>> = {
    // Student
    '/student':                StudentDashboard.preload,
    '/student/book':           BookCabin.preload,
    '/student/accommodation':  FindAccommodation.preload,
    '/student/payments':       StudentPayments.preload,
    '/student/waitlists':      MyWaitlists.preload,
    '/student/messages':       MessagesPage.preload,
    '/student/profile':        StudentProfile.preload,
    '/student/favorites':      FavoritesPage.preload,
    // Admin (owner)
    '/admin':                  AdminDashboard.preload,
    '/admin/listings':         AdminListings.preload,
    '/admin/students':         AdminStudents.preload,
    '/admin/financials':       AdminFinancials.preload,
    '/admin/billing':          OwnerBilling.preload,
    '/admin/insights':         OwnerInsights.preload,
    '/admin/settlements':      OwnerSettlements.preload,
    '/admin/waitlists':        AdminWaitlists.preload,
    '/admin/messages':         MessagesPage.preload,
    '/admin/profile':          AdminProfile.preload,
    '/admin/settings':         OwnerSettings.preload,
    '/admin/kyc':              OwnerKYC.preload,
    // Super-admin
    '/super-admin':                       SuperAdminDashboard.preload,
    '/super-admin/settlements':           SuperAdminSettlements.preload,
    '/super-admin/tax-config':            SuperAdminTaxConfig.preload,
    '/super-admin/owners/kyc':            SuperAdminKYCReview.preload,
    '/super-admin/ledger':                SuperAdminLedger.preload,
    '/super-admin/intelligence':          SuperAdminIntelligence.preload,
    '/super-admin/segments':              SuperAdminSegments.preload,
    '/super-admin/campaigns':             SuperAdminCampaigns.preload,
    '/super-admin/notification-rules':    SuperAdminNotificationRules.preload,
    '/super-admin/attribution':           SuperAdminAttribution.preload,
    '/super-admin/insights':              SuperAdminInsightsDashboard.preload,
    '/super-admin/experiments':           SuperAdminExperiments.preload,
    '/super-admin/cohorts':               SuperAdminCohorts.preload,
    '/super-admin/tickets':               SupportPage.preload,
    '/super-admin/settings':              SuperAdminSettings.preload,
    '/super-admin/profile':               SuperAdminProfile.preload,
};

// Minimal Suspense fallback. We render *something* (not a blank screen) so
// the user has visual continuity while a route chunk downloads. Keep it
// dependency-free so it never blocks first paint.
const PageLoader: React.FC = () => (
    <div style={{
        minHeight: '60vh',
        display: 'grid',
        placeItems: 'center',
        color: '#6b7280',
        fontSize: 14,
    }}>
        Loading…
    </div>
);

// Per-navigation Suspense + ErrorBoundary. Keyed on `location.pathname`
// so the boundary fully unmounts and remounts whenever the route changes.
//
// Why this matters: React 18's transition behavior keeps the previously-
// committed children of a Suspense boundary visible while the next render
// suspends, so a Suspense placed ABOVE the route swap shows the stale page
// instead of the loader. With a per-pathname `key`, the boundary remounts
// from scratch each time, guaranteeing the prior page is unmounted before
// the new page is requested. A failed chunk (network blip, cached
// rejection from a poisoned prefetch) lands in the inner ErrorBoundary as
// a visible failure, not as a silent stale render.
const RoutedContent: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const location = useLocation();
    return (
        <ErrorBoundary key={location.pathname}>
            <Suspense fallback={<PageLoader />}>
                {children}
            </Suspense>
        </ErrorBoundary>
    );
};
import { AppState, UserRole, User, Booking, CabinStatus, ReadingRoom, Cabin, Notification, Review, WaitlistEntry, Accommodation, SupportTicket, PlatformSettings, PromotionPlan, PromotionRequest, Message, Conversation } from './types';
import { realTimeService } from './services/realTimeService';
import { bookingService } from './services/bookingService';
import { venueService } from './services/venueService';
import { supplyService } from './services/supplyService';
import { userService } from './services/userService';
import { subscriptionService } from './services/subscriptionService';
import { favoritesService } from './services/favoritesService';
import { messagingService } from './services/messagingService';
import { waitlistService } from './services/waitlistService';

// Wrapper to force remount when venueId changes
const AdminVenueWrapper: React.FC<any> = (props) => {
  const { venueId } = useParams<{ venueId: string }>();
  return <AdminVenue key={venueId} {...props} />;
};

const App: React.FC = () => {
  // --- Global App State Simulation ---
  const [appState, setAppState] = useState<AppState>(() => {
    // Check local storage for persisted user session
    const savedUserJson = localStorage.getItem('studySpace_user');
    const savedUser = savedUserJson ? JSON.parse(savedUserJson) : null;

    // Load persisted settings ONLY
    const savedDataJson = localStorage.getItem('studySpace_settings');
    const savedSettings = savedDataJson ? JSON.parse(savedDataJson) : null;

    return {
      currentUser: savedUser,
      users: [],
      readingRooms: [],
      cabins: [],
      bookings: [], // Always start empty, wait for fetch
      notifications: [], // Always start empty
      reviews: [],
      waitlist: [],
      accommodations: [],
      favorites: [],
      tickets: [],
      subscriptionPlans: [],
      promotionPlans: [],
      promotionRequests: [],
      messages: [],
      conversations: [],
      settings: savedSettings || {
        platformName: 'mySpace',
        supportEmail: 'support@myspaceapp.in',
        supportPhone: '+91 99999 88888',
        maintenanceMode: false,
        features: {
          featuredListings: true,
          reviews: true,
          waitlist: true,
          newVenueRegistrations: true
        },
        payments: {
          enableNewSubscriptions: true,
          featuredListingPrice: 499,
          venueSubscriptionDurationDays: 30
        },
        locations: {
          cityBasedAvailability: true
        },
        preferences: {
          landingPage: 'DASHBOARD',
          dateFormat: 'DD/MM/YYYY',
          currency: 'INR'
        }
      }
    };
  });

  // Add effect to persist SETTINGS changes only
  useEffect(() => {
    localStorage.setItem('studySpace_settings', JSON.stringify(appState.settings));
  }, [appState.settings]);

  // --- Real-time Service Integration ---
  const [isDataLoaded, setIsDataLoaded] = useState(false);

  // Sync favorites when they change
  useEffect(() => {
    if (!appState.currentUser) return;

    const handleFavoritesChanged = async () => {
      try {
        const myFavorites = await favoritesService.getFavorites();
        setAppState(prev => ({ ...prev, favorites: myFavorites }));
      } catch (e) {
        console.warn('Failed to sync favorites:', e);
      }
    };

    window.addEventListener('favoritesChanged', handleFavoritesChanged);
    return () => window.removeEventListener('favoritesChanged', handleFavoritesChanged);
  }, [appState.currentUser]);

  useEffect(() => {
    // 0. Fetch initial data from Backend if logged in
    const fetchData = async () => {
      try {
        // Fetch Rooms, Cabins, and Accommodations from backend (source of truth)
        const rooms = await venueService.getAllReadingRooms();
        const cabins = await venueService.getAllCabins();
        const accommodations = await supplyService.getAllAccommodations();

        // Always use backend data - don't fall back to mock data
        // Backend already filters to show: LIVE listings OR listings owned by current user
        setAppState(prev => ({
          ...prev,
          readingRooms: rooms,           // Always use backend data (even if empty)
          cabins: cabins,                // Always use backend data (even if empty)
          accommodations: accommodations // Always use backend data (even if empty)
        }));

        // Fetch subscription plans from backend
        try {
          const subscriptionPlans = await subscriptionService.getPlans();
          setAppState(prev => ({
            ...prev,
            subscriptionPlans: subscriptionPlans
          }));
        } catch (e) {
          console.warn('Failed to fetch subscription plans:', e);
        }

        if (appState.currentUser) {
          const myBookings = await bookingService.getMyBookings();

          // Fetch user's favorites
          let myFavorites = [];
          try {
            myFavorites = await favoritesService.getFavorites();
          } catch (e) {
            console.warn('Failed to fetch favorites:', e);
          }

          // Fetch user's conversations and messages
          let myConversations: Conversation[] = [];
          try {
            myConversations = await messagingService.getConversations();
          } catch (e) {
            console.warn('Failed to fetch conversations:', e);
          }

          let myStudents: User[] = [];

          // Fetch waitlists for students
          if (appState.currentUser.role === UserRole.STUDENT) {
            try {
              const myWaitlists = await waitlistService.getMyWaitlists();
              setAppState(prev => ({ ...prev, waitlist: myWaitlists }));
              // Sync has_active_waitlist just in case
              if (myWaitlists.length > 0 && !appState.currentUser.has_active_waitlist) {
                const updatedUser = { ...appState.currentUser, has_active_waitlist: true };
                localStorage.setItem('studySpace_user', JSON.stringify(updatedUser));
                setAppState(prev => ({ ...prev, currentUser: updatedUser }));
              }
            } catch (e) {
              console.warn("Failed to fetch waitlists", e);
            }
          }

          if (appState.currentUser.role === UserRole.SUPER_ADMIN) {
            try {
              // Super Admin sees ALL users
              myStudents = await userService.getAllUsers();
            } catch (e) {
              console.error("Failed to fetch all users", e);
            }
          } else {
            try {
              // @ts-ignore
              myStudents = await venueService.getMyStudents();
            } catch (e) {
              console.warn("Could not fetch students", e);
            }
          }

          // Enrich bookings with cabin data (since backend doesn't join)
          const enrichedBookings = myBookings.map(b => {
            const cabin = cabins.find(c => c.id === b.cabinId);
            return cabin ? { ...b, cabinNumber: cabin.number } : b;
          });

          setAppState(prev => {
            // For Super Admin, we REPLACE the list (to ensure we see everyone exactly as they are)
            // For others, we might want to merge or keep defaults.
            // Since getAllUsers returns everyone, replacing is safe for SA.

            let finalUsers = [...prev.users];
            if (appState.currentUser?.role === UserRole.SUPER_ADMIN) {
              finalUsers = myStudents;
            } else {
              // Merge logic for others
              myStudents.forEach(s => {
                if (!finalUsers.find(u => u.id === s.id)) {
                  finalUsers.push(s);
                }
              });
            }

            return {
              ...prev,
              bookings: enrichedBookings,
              users: finalUsers,
              favorites: myFavorites,
              conversations: myConversations
            };
          });
        }
      } catch (err) {
        console.error("Failed to fetch initial data:", err);
      }
    };
    fetchData().finally(() => setIsDataLoaded(true));

    const unsubscribe = realTimeService.subscribe((event) => {

      if (event.type === 'CABIN_UPDATE') {
        const { cabinId, ...updates } = event.payload;

        setAppState(prev => {
          // 1. Update Cabin Status
          const updatedCabins = prev.cabins.map(c => {

            if (c.id === cabinId) {
              const processedUpdates: any = { ...updates };
              // Handle amenities parsing if it comes as string
              if (processedUpdates.amenities && typeof processedUpdates.amenities === 'string') {
                processedUpdates.amenities = processedUpdates.amenities.split(',').filter(Boolean);
              }
              return { ...c, ...processedUpdates };
            }
            return c;
          });

          const status = updates.status;

          let updatedNotifications = [...prev.notifications];
          let updatedWaitlist = [...prev.waitlist];

          // 2. Check Waitlist if cabin becomes AVAILABLE
          if (status === CabinStatus.AVAILABLE) {
            const waiters = prev.waitlist.filter(w => w.cabinId === cabinId);

            if (waiters.length > 0) {
              waiters.forEach(waiter => {
                const cabin = prev.cabins.find(c => c.id === cabinId);
                const room = prev.readingRooms.find(r => r.id === cabin?.readingRoomId);

                // Send Notification
                updatedNotifications.unshift({
                  id: `notif-wl-${Date.now()}-${waiter.userId}`,
                  userId: waiter.userId,
                  title: 'Spot Available!',
                  message: `Great news! Cabin ${cabin?.number} at ${room?.name} is now available. Book it before it's gone!`,
                  read: false,
                  date: new Date().toISOString(),
                  type: 'success'
                });
              });

              // Remove notified users from waitlist (or keep them until booked - for now remove to clear state)
              updatedWaitlist = prev.waitlist.filter(w => w.cabinId !== cabinId);
            }
          }

          return {
            ...prev,
            cabins: updatedCabins,
            notifications: updatedNotifications,
            waitlist: updatedWaitlist
          };
        });
      }
    });

    return () => unsubscribe();
  }, [appState.currentUser]); // Re-run when user changes (login)

  // Check for expiring bookings and create notifications
  useEffect(() => {
    if (!appState.currentUser || appState.currentUser.role !== UserRole.STUDENT) return;
    
    const checkExpiringBookings = () => {
      const now = new Date();
      const fiveDaysFromNow = new Date(now.getTime() + 5 * 24 * 60 * 60 * 1000);
      
      const userBookings = appState.bookings.filter(b => 
        b.userId === appState.currentUser?.id && 
        b.status === 'ACTIVE'
      );
      
      userBookings.forEach(booking => {
        const endDate = new Date(booking.endDate);
        const daysUntilExpiry = Math.ceil((endDate.getTime() - now.getTime()) / (24 * 60 * 60 * 1000));
        
        // Create notification if booking expires in 5 days or less and no such notification exists
        if (daysUntilExpiry > 0 && daysUntilExpiry <= 5) {
          const notifId = `expiry-${booking.id}`;
          const existingNotif = appState.notifications.find(n => n.id === notifId);
          
          if (!existingNotif) {
            const room = appState.readingRooms.find(r => 
              appState.cabins.some(c => c.id === booking.cabinId && c.readingRoomId === r.id)
            );
            const venueName = room?.name || 'your venue';
            
            setAppState(prev => ({
              ...prev,
              notifications: [{
                id: notifId,
                userId: appState.currentUser!.id,
                title: 'Booking Expiring Soon',
                message: `Your booking at ${venueName} expires in ${daysUntilExpiry} day${daysUntilExpiry > 1 ? 's' : ''}. Consider extending your booking.`,
                read: false,
                date: new Date().toISOString(),
                type: 'warning' as const
              }, ...prev.notifications]
            }));
          }
        }
      });
    };
    
    // Check immediately and then daily
    checkExpiringBookings();
    const interval = setInterval(checkExpiringBookings, 24 * 60 * 60 * 1000); // Check daily
    
    return () => clearInterval(interval);
  }, [appState.bookings, appState.currentUser, appState.notifications, appState.readingRooms, appState.cabins]);

  // --- Actions ---
  const handleLogin = (email: string, role: UserRole, backendUser?: any) => {
    // Find mock user or use backend user, or create a temporary one for demo
    const user = backendUser ? {
      id: backendUser.id,
      name: backendUser.name,
      email: backendUser.email,
      role: backendUser.role as UserRole,
      avatarUrl: backendUser.avatarUrl || `https://ui-avatars.com/api/?name=${email}`,
      phone: backendUser.phone,
      has_active_waitlist: backendUser.has_active_waitlist
    } : (appState.users.find(u => u.email === email && u.role === role) || {
      id: `user-${Date.now()}`,
      name: email.split('@')[0],
      email,
      role,
      avatarUrl: `https://ui-avatars.com/api/?name=${email}`,
    });

    // Check if user has any notifications, if not add a welcome one
    const existingNotifs = appState.notifications.filter(n => n.userId === user.id);
    let newNotifs = [...appState.notifications];

    if (existingNotifs.length === 0) {
      const welcomeNotification: Notification = {
        id: `notif-${Date.now()}`,
        userId: user.id,
        title: `Welcome ${role === UserRole.ADMIN ? 'Admin' : 'Student'}!`,
        message: role === UserRole.ADMIN
          ? 'Manage your reading room, track revenue, and handle bookings from here.'
          : 'Find and book your perfect study spot. Good luck with your studies!',
        read: false,
        date: new Date().toISOString(),
        type: 'info'
      };
      newNotifs.push(welcomeNotification);
    }

    // Persist session
    localStorage.setItem('studySpace_user', JSON.stringify(user));

    setAppState(prev => ({
      ...prev,
      currentUser: user,
      notifications: newNotifs
    }));
  };

  const handleLogout = () => {
    // Clear session
    localStorage.removeItem('studySpace_user');
    setAppState(prev => ({ ...prev, currentUser: null }));
  };

  const handleUpdateUser = (updatedData: Partial<User>) => {
    if (!appState.currentUser) return;

    const updatedUser = { ...appState.currentUser, ...updatedData };

    // Update current user
    setAppState(prev => ({
      ...prev,
      currentUser: updatedUser,
      // Update in users list as well
      users: prev.users.map(u => u.id === updatedUser.id ? updatedUser : u)
    }));

    // Persist to local storage
    localStorage.setItem('studySpace_user', JSON.stringify(updatedUser));
  };

  const handleCreateReadingRoom = async (roomData: Partial<ReadingRoom>): Promise<ReadingRoom> => {
    if (!appState.currentUser) throw new Error("User not logged in");


    try {
      // Use Backend Service
      const newRoom = await venueService.createReadingRoom(roomData);

      setAppState(prev => ({
        ...prev,
        readingRooms: [...prev.readingRooms, newRoom]
      }));

      return newRoom;
    } catch (err: any) {
      console.error("Failed to create reading room:", err);
      // Show specific error from backend validation if available
      const msg = err.response?.data?.detail || err.message || "Failed to create venue. Please try again.";

      // Flatten list errors if any
      const alertMsg = Array.isArray(msg) ? msg.map((e: any) => `${e.loc?.join('.')} ${e.msg}`).join('\n') : msg;
      // toast.error(`Error: ${alertMsg}`); // Removed to prevent double toast
      throw err; // Re-throw to prevent UI from proceeding
    }
  };

  const handleUpdateReadingRoom = async (roomData: Partial<ReadingRoom>) => {
    if (!appState.currentUser) return;

    // Use room ID from roomData if provided, otherwise find first owned room
    const roomId = roomData.id || appState.readingRooms.find(r => r.ownerId === appState.currentUser?.id)?.id;
    if (!roomId) {
      console.error("No room ID found for update");
      return;
    }

    try {
      const updatedRoomFromServer = await venueService.updateReadingRoom(roomId, roomData);
      setAppState(prev => ({
        ...prev,
        readingRooms: prev.readingRooms.map(r => r.id === roomId ? updatedRoomFromServer : r)
      }));
      // toast.success("Changes saved successfully!"); // Removed to prevent double toast
    } catch (err) {
      console.error("Failed to update reading room:", err);
      // toast.error("Failed to save changes. Please try again."); // Removed to allow caller to handle
      throw err; // Required so AdminVenue knows it failed
    }
  };

  const handleAddCabin = async (cabinData: Partial<Cabin>) => {
    if (!appState.currentUser) return;

    // Use readingRoomId from cabinData if provided (multi-venue support)
    // Otherwise fallback to finding first owned room
    const roomId = cabinData.readingRoomId ||
      appState.readingRooms.find(r => r.ownerId === appState.currentUser?.id)?.id;
    if (!roomId) return;

    try {
      const newCabin = await venueService.createCabin(roomId, cabinData);
      setAppState(prev => ({
        ...prev,
        cabins: [...prev.cabins, newCabin]
      }));
    } catch (err) {
      console.error("Failed to add cabin:", err);
      toast.error("Failed to add cabin. Please try again.");
    }
  };

  const handleBulkAddCabins = async (newCabinsData: Partial<Cabin>[]) => {
    if (!appState.currentUser) {
      throw new Error("You must be signed in to create cabins.");
    }

    // Use readingRoomId from first cabin data if provided (multi-venue support)
    // Otherwise fallback to finding first owned room
    const roomId = newCabinsData[0]?.readingRoomId ||
      appState.readingRooms.find(r => r.ownerId === appState.currentUser?.id)?.id;
    if (!roomId) {
      throw new Error("No reading room was found for these cabins.");
    }

    try {
      const createdCabins = await venueService.createCabinsBulk(roomId, newCabinsData);
      setAppState(prev => ({
        ...prev,
        cabins: [...prev.cabins, ...createdCabins]
      }));
      toast.success(`${createdCabins.length} cabins created successfully.`);
    } catch (err) {
      console.error("Failed to add cabins:", err);
      const message = (err as any)?.response?.data?.detail
        || "Failed to batch create cabins. No cabins were created.";
      toast.error(message);
      throw err;
    }
  };


  const handleUpdateCabin = async (cabinId: string, updates: Partial<Cabin>) => {
    try {
      // 1. Update Backend
      const updatedCabin = await venueService.updateCabin(cabinId, updates);

      // 2. Update Local State (Although socket might do it too, optimistic/confirm update is good)
      setAppState(prev => ({
        ...prev,
        cabins: prev.cabins.map(c => c.id === cabinId ? updatedCabin : c)
      }));
    } catch (err) {
      console.error("Failed to update cabin:", err);
      // Revert or alert
      toast.error("Failed to update cabin.");
    }
  };

  const handleBulkUpdateCabins = (cabinIds: string[], updates: Partial<Cabin>) => {
    setAppState(prev => ({
      ...prev,
      cabins: prev.cabins.map(c => cabinIds.includes(c.id) ? { ...c, ...updates } : c)
    }));
  };

  const handleBulkDeleteCabins = async (cabinIds: string[]) => {
    if (!appState.currentUser) return;
    try {
      await venueService.deleteCabins(cabinIds);
      setAppState(prev => ({
        ...prev,
        cabins: prev.cabins.filter(c => !cabinIds.includes(c.id))
      }));
    } catch (err) {
      console.error("Failed to delete cabins:", err);
      toast.error(err.response?.data?.detail || "Failed to delete cabins. Ensure they are not occupied.");
    }
  };

  const handleBookCabin = async (cabinId: string, durationMonths: number) => {
    // This function is deprecated - BookCabin component now handles the entire payment flow
    // It's kept here for backwards compatibility but should not be used
    console.warn('handleBookCabin is deprecated. BookCabin component handles payment flow internally.');
    
    // Refresh bookings to get latest data
    try {
      const bookings = await bookingService.getMyBookings();
      setAppState(prev => ({
        ...prev,
        bookings
      }));
    } catch (error) {
      console.error('Failed to refresh bookings:', error);
    }
  };

  const handleJoinWaitlist = (cabinId: string) => {
    if (!appState.currentUser) return;

    const cabin = appState.cabins.find(c => c.id === cabinId);
    if (!cabin) return;

    const room = appState.readingRooms.find(r => r.id === cabin.readingRoomId);

    const newEntry: WaitlistEntry = {
      id: `wl-${Date.now()}`,
      userId: appState.currentUser.id,
      cabinId: cabin.id,
      readingRoomId: cabin.readingRoomId,
      date: new Date().toISOString(),
      status: 'ACTIVE',
      // Enriched
      venueName: room?.name,
      venueAddress: room?.address,
      cabinNumber: cabin.number
    };

    const updatedUser = { ...appState.currentUser, has_active_waitlist: true };
    localStorage.setItem('studySpace_user', JSON.stringify(updatedUser));

    setAppState(prev => ({
      ...prev,
      currentUser: updatedUser,
      waitlist: [...prev.waitlist, newEntry]
    }));

    // --- SIMULATION FOR DEMO ---
    setTimeout(() => {
      setAppState(prev => {
        const currentCabin = prev.cabins.find(c => c.id === cabinId);
        if (currentCabin?.status !== CabinStatus.AVAILABLE) {
          const updatedCabins = prev.cabins.map(c => c.id === cabinId ? { ...c, status: CabinStatus.AVAILABLE } : c);
          const room = prev.readingRooms.find(r => r.id === cabin.readingRoomId);
          const notif: Notification = {
            id: `notif-wl-sim-${Date.now()}`,
            userId: appState.currentUser!.id,
            title: 'Spot Available!',
            message: `(Demo) Cabin ${cabin.number} at ${room?.name} is now available.`,
            read: false,
            date: new Date().toISOString(),
            type: 'success'
          };
          return {
            ...prev,
            cabins: updatedCabins,
            notifications: [notif, ...prev.notifications],
            waitlist: prev.waitlist.filter(w => w.cabinId !== cabinId)
          };
        }
        return prev;
      });
    }, 10000);
  };

  const handleExtendBooking = async (bookingId: string, durationMonths: number, extensionAmount?: number) => {
    try {
      // Find the booking to get cabin price if extensionAmount not provided
      const booking = appState.bookings.find(b => b.id === bookingId);
      if (!booking) {
        console.error('Booking not found:', bookingId);
        return;
      }

      // Get cabin price for extension amount calculation
      const cabin = appState.cabins.find(c => c.id === booking.cabinId);
      const amount = extensionAmount || (cabin?.price || 1500) * durationMonths;

      // Call backend API to extend booking and create PaymentTransaction
      const result = await bookingService.extendBooking(bookingId, durationMonths, amount, booking.endDate, 'UPI');

      // Update local state with new end date
      setAppState(prev => {
        const updatedBookings = prev.bookings.map(b =>
          b.id === bookingId
            ? { ...b, endDate: result.new_end_date.split('T')[0], amount: result.total_amount }
            : b
        );

        const newNotification: Notification = {
          id: `notif-${Date.now()}`,
          userId: prev.currentUser?.id || '',
          title: 'Subscription Extended',
          message: `Your booking for Cabin ${booking.cabinNumber} has been extended by ${durationMonths} month(s). ₹${amount} paid.`,
          read: false,
          date: new Date().toISOString(),
          type: 'success'
        };

        return {
          ...prev,
          bookings: updatedBookings,
          notifications: [newNotification, ...prev.notifications]
        };
      });
    } catch (error: any) {
      console.error('Failed to extend booking:', error);
      // Add error notification
      setAppState(prev => ({
        ...prev,
        notifications: [{
          id: `notif-${Date.now()}`,
          userId: prev.currentUser?.id || '',
          title: 'Extension Failed',
          message: error.response?.data?.detail || 'Failed to extend booking. Please try again.',
          read: false,
          date: new Date().toISOString(),
          type: 'error'
        }, ...prev.notifications]
      }));
      // Re-throw so calling code knows it failed
      throw error;
    }
  };

  const handleMarkNotificationRead = (id: string) => {
    setAppState(prev => ({
      ...prev,
      notifications: prev.notifications.map(n =>
        n.id === id ? { ...n, read: true } : n
      )
    }));
  };

  const handleMarkAllNotificationsRead = () => {
    setAppState(prev => ({
      ...prev,
      notifications: prev.notifications.map(n => ({ ...n, read: true }))
    }));
  };

  const handleClearAllNotifications = () => {
    setAppState(prev => ({
      ...prev,
      notifications: []
    }));
  };

  const handleAddReview = async (reviewData: { readingRoomId?: string, accommodationId?: string, rating: number, comment: string }) => {
    if (!appState.currentUser) return;
    try {
      await venueService.submitReview(reviewData);

      const newReview: Review = {
        id: `rev-${Date.now()}`,
        userId: appState.currentUser.id,
        readingRoomId: reviewData.readingRoomId,
        accommodationId: reviewData.accommodationId,
        rating: reviewData.rating,
        comment: reviewData.comment,
        date: new Date().toISOString().split('T')[0]
      };
      setAppState(prev => ({
        ...prev,
        reviews: [newReview, ...prev.reviews]
      }));
    } catch (e: any) {
      console.error("Failed to submit review", e);
      const errorMessage = e.response?.data?.detail || "Failed to submit review. Please try again.";
      toast.error(errorMessage);
    }
  };

  const handleDeleteReview = (reviewId: string) => {
    setAppState(prev => ({
      ...prev,
      reviews: prev.reviews.filter(r => r.id !== reviewId)
    }));
  };

  // --- Accommodation Handlers ---

  const handleCreateAccommodation = async (data: Partial<Accommodation>) => {
    if (!appState.currentUser) return;
    try {
      const newAcc = await supplyService.createAccommodation(data);
      setAppState(prev => ({
        ...prev,
        accommodations: [...prev.accommodations, newAcc]
      }));
    } catch (err) {
      console.error("Failed to create accommodation:", err);
      toast.error("Failed to create listing. Please try again.");
    }
  };

  const handleUpdateAccommodation = async (id: string, data: Partial<Accommodation>) => {
    try {
      const updatedAcc = await supplyService.updateAccommodation(id, data);
      setAppState(prev => ({
        ...prev,
        accommodations: prev.accommodations.map(a => a.id === id ? updatedAcc : a)
      }));
    } catch (err) {
      console.error("Failed to update accommodation:", err);
      toast.error("Failed to update listing. Please try again.");
    }
  };

  const handleDeleteAccommodation = (id: string) => {
    setAppState(prev => ({
      ...prev,
      accommodations: prev.accommodations.filter(a => a.id !== id)
    }));
  };

  const handleCreateTicket = (ticket: SupportTicket) => {
    setAppState(prev => ({
      ...prev,
      tickets: [ticket, ...prev.tickets]
    }));
  };


  const handleUpdateSettings = (newSettings: PlatformSettings) => {
    setAppState(prev => ({
      ...prev,
      settings: newSettings
    }));
  };

  const handleSyncFavorites = async () => {
    if (appState.currentUser) {
      try {
        const myFavorites = await favoritesService.getFavorites();
        setAppState(prev => ({ ...prev, favorites: myFavorites }));
      } catch (e) {
        console.warn('Failed to sync favorites:', e);
      }
    }
  };


  const currentUserNotifications = appState.notifications.filter(
    n => n.userId === appState.currentUser?.id
  );

  // Determine if user has any reading rooms to show Waitlist tab
  const hasReadingRooms = appState.readingRooms.some(r => r.ownerId === appState.currentUser?.id);

  // Calculate unread message count from CONVERSATIONS (not raw messages)
  const unreadMessageCount = appState.conversations.reduce((sum, conv) => sum + (conv.unreadCount || 0), 0);

  // Poll for new messages globally to keep the unread badge updated.
  //
  // History: this used to be a naive `setInterval(refresh, 15000)` that:
  //   - kept firing while the tab was backgrounded (waste),
  //   - kept firing while the user was offline (DevTools spam — every
  //     failed request logged a full AxiosError stack trace, which is
  //     where the screenshot's "Bg sync failed" / ERR_INTERNET_DISCONNECTED
  //     noise came from),
  //   - had no backoff, so a brief backend outage caused hundreds of
  //     identical failed requests until the user closed the tab.
  //
  // Now: visibility-aware, online-aware, with exponential backoff on
  // network errors, and a one-shot resume on the browser's `online`
  // event. Real (non-network) errors still surface as warnings.
  useEffect(() => {
    if (!appState.currentUser) return;

    const BASE_INTERVAL_MS = 15_000;
    const MAX_INTERVAL_MS = 5 * 60_000;       // back off no further than 5m
    let timer: ReturnType<typeof setTimeout> | null = null;
    let failures = 0;
    let cancelled = false;

    const isOffline = () =>
      typeof navigator !== 'undefined' && navigator.onLine === false;
    const isHidden = () =>
      typeof document !== 'undefined' && document.hidden === true;

    const isNetworkError = (e: any): boolean => {
      // Axios sets code='ERR_NETWORK' / message='Network Error' when the
      // request never reached the server (offline, DNS, CORS preflight
      // failure). These are expected on flaky connections — log once,
      // never with a stack trace, and back off instead of spamming.
      return (
        e?.code === 'ERR_NETWORK'
        || e?.message === 'Network Error'
        || e?.code === 'ERR_INTERNET_DISCONNECTED'
        || e?.code === 'ERR_NAME_NOT_RESOLVED'
        || e?.code === 'ERR_NETWORK_CHANGED'
      );
    };

    // Cloud Run cold starts + brief container restarts surface as 502/503/
    // 504. Treat them as transient (same backoff as a network error, no
    // per-poll spam) instead of as real backend bugs.
    const isTransientGateway = (e: any): boolean => {
      const s = e?.response?.status;
      return s === 502 || s === 503 || s === 504;
    };

    const runOnce = async () => {
      if (cancelled) return;
      // Skip while offline or backgrounded — saves bandwidth, eliminates
      // console noise, and avoids racing the browser's own connection
      // state. The `online` and `visibilitychange` listeners below pick
      // up the slack.
      if (isOffline() || isHidden()) {
        schedule();
        return;
      }
      try {
        const fresh = await messagingService.getConversations();
        setAppState(prev => ({ ...prev, conversations: fresh }));
        failures = 0;
      } catch (e: any) {
        failures += 1;
        if (isNetworkError(e) || isTransientGateway(e)) {
          // Log once when we first see trouble, then stay quiet through
          // the backoff. Backend cold-starts and brief Cloud Run restarts
          // would otherwise spam the console with one 502 per poll.
          if (failures === 1) {
            const reason = isTransientGateway(e)
              ? `backend returned ${e.response.status}`
              : 'network unavailable';
            console.warn(`[messaging] poll paused — ${reason}`);
          }
        } else {
          // Server returned 4xx/5xx OTHER than 502/503/504 — surface a
          // one-line warning per failure so real backend bugs aren't
          // silenced, but don't dump the whole AxiosError every 15s.
          console.warn(
            '[messaging] poll failed:',
            e?.response?.status ?? e?.message ?? 'unknown',
          );
        }
      } finally {
        schedule();
      }
    };

    const schedule = () => {
      if (cancelled) return;
      // Exponential backoff capped at MAX_INTERVAL_MS. failures==0 means
      // last poll succeeded — go right back to the base 15s cadence.
      const delay = failures === 0
        ? BASE_INTERVAL_MS
        : Math.min(BASE_INTERVAL_MS * 2 ** Math.min(failures, 5), MAX_INTERVAL_MS);
      timer = setTimeout(runOnce, delay);
    };

    // Manual refresh (e.g. user sent / read a message). Reset backoff so
    // the next poll runs at base cadence rather than during a back-off
    // window left over from a transient outage.
    const handleMessagesUpdated = () => {
      failures = 0;
      if (timer) clearTimeout(timer);
      runOnce();
    };

    // Resume promptly when connectivity returns (the next scheduled tick
    // could be up to 5 minutes away if we've backed off).
    const handleOnline = () => {
      failures = 0;
      if (timer) clearTimeout(timer);
      runOnce();
    };

    window.addEventListener('messagesUpdated', handleMessagesUpdated);
    window.addEventListener('online', handleOnline);

    // First tick: defer slightly so the rest of the app's initial fetches
    // don't pile on top of it.
    timer = setTimeout(runOnce, 2_000);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener('messagesUpdated', handleMessagesUpdated);
      window.removeEventListener('online', handleOnline);
    };
  }, [appState.currentUser]);

  if (!appState.currentUser) {
    return (
      <ErrorBoundary>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              background: '#fff',
              color: '#363636',
            },
            success: {
              duration: 3000,
              iconTheme: {
                primary: '#10b981',
                secondary: '#fff',
              },
            },
            error: {
              duration: 5000,
              iconTheme: {
                primary: '#ef4444',
                secondary: '#fff',
              },
            },
          }}
        />
        {/* Login-first: any path served to an anonymous visitor shows the
            auth screen. Backend Jinja2 SEO routes (/reading-rooms/kochi,
            /guides/*, etc.) are unaffected — those are served by FastAPI
            directly and never hit the React SPA. */}
        <Router>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route path="*" element={<AuthPage onLogin={handleLogin} />} />
            </Routes>
          </Suspense>
        </Router>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#fff',
            color: '#363636',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10b981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 5000,
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
      <Router>
        <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Auth screens — kept reachable so a logged-in user can switch
              accounts. AuthPage handles the navigate to the new dashboard. */}
          <Route path="/auth" element={<AuthPage onLogin={handleLogin} />} />
          <Route path="/login" element={<AuthPage onLogin={handleLogin} />} />
          <Route path="/register" element={<AuthPage onLogin={handleLogin} />} />

          {/* Everything else flows through the existing role-aware Layout. */}
          <Route path="/*" element={
            <Layout
              user={appState.currentUser}
              onLogout={handleLogout}
              notifications={currentUserNotifications}
              onMarkNotificationRead={handleMarkNotificationRead}
              hasReadingRooms={hasReadingRooms}
              unreadMessageCount={unreadMessageCount}
            >
          <RoutedContent>
          <Routes>
            {/* Mock Payment Gateway - Available to all users in demo mode */}
            <Route path="/mock-payment" element={<MockPaymentGateway />} />
            
            <Route path="/" element={
              appState.currentUser.role === UserRole.ADMIN
                ? <Navigate to="/admin" />
                : appState.currentUser.role === UserRole.SUPER_ADMIN
                  ? <Navigate to="/super-admin" />
                  : <Navigate to="/student" />
            } />

            <Route path="/support" element={
              appState.currentUser ? (
                <SupportPage
                  user={appState.currentUser}
                  tickets={appState.tickets}
                  onTicketCreate={handleCreateTicket}
                />
              ) : <Navigate to="/auth" />
            } />

            {/* Student Routes */}
            {appState.currentUser.role === UserRole.STUDENT && (
              <>
                <Route path="/student" element={
                  <StudentDashboard
                    state={appState}
                    user={appState.currentUser}
                    onAddReview={handleAddReview}
                    onExtendBooking={handleExtendBooking}
                    onMarkAsRead={handleMarkNotificationRead}
                    onMarkAllAsRead={handleMarkAllNotificationsRead}
                    onClearAll={handleClearAllNotifications}
                  />
                } />
                <Route path="/student/book" element={
                  <BookCabin
                    state={appState}
                    user={appState.currentUser}
                    onBookCabin={handleBookCabin}
                    onJoinWaitlist={handleJoinWaitlist}
                  />
                } />
                <Route path="/student/accommodation" element={
                  <FindAccommodation state={appState} />
                } />
                <Route path="/student/accommodation/:id" element={
                  <AccommodationDetail state={appState} />
                } />
                <Route path="/student/reading-room/:roomId" element={
                  <ReadingRoomDetail
                    state={appState}
                    user={appState.currentUser}
                    onBookCabin={handleBookCabin}
                    onJoinWaitlist={handleJoinWaitlist}
                  />
                } />
                <Route path="/student/payments" element={<StudentPayments state={appState} user={appState.currentUser} />} />
                <Route path="/student/privacy" element={<StudentPrivacySettings />} />
                <Route path="/student/my-data" element={<StudentMyIntelligence />} />
                <Route path="/student/favorites" element={<FavoritesPage onFavoritesChange={handleSyncFavorites} />} />
                <Route path="/student/messages" element={
                  <MessagesPage
                    currentUserId={appState.currentUser.id}
                    currentUserRole={appState.currentUser.role}
                  />
                } />
                <Route path="/student/profile" element={
                  <StudentProfile
                    user={appState.currentUser}
                    state={appState}
                    onUpdateUser={handleUpdateUser}
                    onDeleteReview={handleDeleteReview}
                    onAddReview={handleAddReview}
                    onLogout={handleLogout}
                  />
                } />
                <Route path="/student/waitlists" element={
                  <MyWaitlists
                    state={appState}
                    user={appState.currentUser}
                    onUpdateWaitlistStatus={(hasActive) => handleUpdateUser({ has_active_waitlist: hasActive })}
                  />
                } />
                <Route path="/student/*" element={<div className="p-10 text-center text-gray-500">Feature coming soon...</div>} />
              </>
            )}

            {/* Admin Routes */}
            {appState.currentUser.role === UserRole.ADMIN && (
              <>
                <Route path="/admin" element={<AdminDashboard state={appState} />} />
                <Route path="/admin/listings" element={<AdminListings />} />
                <Route path="/admin/migrations" element={<AdminMigrations />} />
                <Route path="/admin/venue/:venueId" element={
                  <AdminVenueWrapper
                    state={appState}
                    onCreateRoom={handleCreateReadingRoom}
                    onUpdateRoom={handleUpdateReadingRoom}
                    onAddCabin={handleAddCabin}
                    onBulkAddCabins={handleBulkAddCabins}
                    onUpdateCabin={handleUpdateCabin}
                    onBulkUpdateCabins={handleBulkUpdateCabins}
                    onBulkDeleteCabins={handleBulkDeleteCabins}
                  />
                } />
                <Route path="/admin/accommodation/:accommodationId" element={
                  <AdminAccommodation
                    state={appState}
                    onCreateAccommodation={handleCreateAccommodation}
                    onUpdateAccommodation={handleUpdateAccommodation}
                    onDeleteAccommodation={handleDeleteAccommodation}
                  />
                } />

                <Route path="/admin/profile" element={
                  <AdminProfile
                    user={appState.currentUser}
                    onUpdateUser={handleUpdateUser}
                    onLogout={handleLogout}
                  />
                } />
                <Route path="/admin/waitlists" element={<AdminWaitlists state={appState} />} />
                <Route path="/admin/students" element={<AdminStudents state={appState} />} />
                <Route path="/admin/financials" element={<AdminFinancials state={appState} />} />
                <Route path="/admin/billing" element={<OwnerBilling state={appState} user={appState.currentUser} />} />
                <Route path="/admin/settlements" element={<OwnerSettlements />} />
                <Route path="/admin/listings/:listingType/:listingId/billing" element={<ListingBillingSettings />} />
                <Route path="/admin/settings" element={<OwnerSettings user={appState.currentUser} />} />
                <Route path="/admin/compliance" element={<OwnerCompliance state={appState} user={appState.currentUser} onUpdateUser={handleUpdateUser} />} />
                <Route path="/admin/kyc" element={<OwnerKYC user={appState.currentUser} />} />
                <Route path="/admin/messages" element={
                  <MessagesPage
                    currentUserId={appState.currentUser.id}
                    currentUserRole={appState.currentUser.role}
                  />
                } />
                {/* Owner insights. Sidebar (Layout.tsx) and ROUTE_PRELOADERS
                    both point to `/admin/insights` so the canonical path is
                    here. `/owner/insights` is kept as a backwards-compatible
                    alias for any older bookmarks / external links. Without
                    BOTH, the sidebar link 404s into the catch-all and
                    Navigate('/') silently sends the user back to the
                    Dashboard ("URL changed but tab content didn't load"). */}
                <Route path="/admin/insights" element={<OwnerInsights />} />
                <Route path="/owner/insights" element={<OwnerInsights />} />
                {/* Preview route - allows ADMIN to view their venue as students see it */}
                <Route path="/admin/preview/venue/:roomId" element={
                  <ReadingRoomDetail
                    state={appState}
                    user={appState.currentUser}
                    onBookCabin={handleBookCabin}
                    onJoinWaitlist={handleJoinWaitlist}
                  />
                } />
              </>
            )}

            {/* Super Admin Routes */}
            {appState.currentUser.role === UserRole.SUPER_ADMIN && (
              <>
                <Route path="/super-admin/profile" element={
                  <SuperAdminProfile
                    user={appState.currentUser}
                    onUpdateUser={handleUpdateUser}
                    onLogout={handleLogout}
                  />
                } />
                <Route path="/super-admin/settings" element={
                  <SuperAdminSettings
                    settings={appState.settings}
                    onUpdateSettings={handleUpdateSettings}
                  />
                } />
                <Route path="/super-admin/accommodations/:id/review" element={<SuperAdminAccommodationReview />} />
                <Route path="/super-admin/reading-rooms/:id/review" element={<SuperAdminReadingRoomReview />} />
                <Route path="/super-admin/tax-config" element={<SuperAdminTaxConfig />} />
                <Route path="/super-admin/settlements" element={<SuperAdminSettlements />} />
                <Route path="/super-admin/owners/kyc" element={<SuperAdminKYCReview />} />
                <Route path="/super-admin/ledger" element={<SuperAdminLedger />} />
                <Route path="/super-admin/intelligence" element={<SuperAdminIntelligence />} />
                <Route path="/super-admin/segments" element={<SuperAdminSegments />} />
                <Route path="/super-admin/campaigns" element={<SuperAdminCampaigns />} />
                <Route path="/super-admin/notification-rules" element={<SuperAdminNotificationRules />} />
                <Route path="/super-admin/attribution" element={<SuperAdminAttribution />} />
                <Route path="/super-admin/insights" element={<SuperAdminInsightsDashboard />} />
                <Route path="/super-admin/experiments" element={<SuperAdminExperiments />} />
                <Route path="/super-admin/cohorts" element={<SuperAdminCohorts />} />
                <Route path="/super-admin/*" element={<SuperAdminDashboard state={appState} />} />
              </>
            )}

            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
          </RoutedContent>
            </Layout>
          } />
        </Routes>
        </Suspense>
      </Router>
    </ErrorBoundary>
  );
};

export default App;
