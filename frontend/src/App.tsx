
import React, { useState, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Layout } from './components/Layout';
import { AuthPage } from './pages/Auth';
import { StudentDashboard } from './pages/StudentDashboard';
import { BookCabin } from './pages/BookCabin';
import { FindAccommodation } from './pages/FindAccommodation';
import { AccommodationDetail } from './pages/AccommodationDetail';
import { ReadingRoomDetail } from './pages/ReadingRoomDetail';
import { StudentPayments } from './pages/StudentPayments';
import { StudentProfile } from './pages/StudentProfile';
import { MyWaitlists } from './pages/MyWaitlists';
import { FavoritesPage } from './pages/FavoritesPage';
import { AdminDashboard } from './pages/AdminDashboard';
import { AdminListings } from './pages/AdminListings';
import { AdminVenue } from './pages/AdminVenue';
import { AdminAccommodation } from './pages/AdminAccommodation';
import { AdminWaitlists } from './pages/AdminWaitlists';
import { AdminProfile } from './pages/AdminProfile';
import { AdminStudents } from './pages/AdminStudents';
import { AdminFinancials } from './pages/AdminFinancials';
import { OwnerBilling } from './pages/OwnerBilling';
import { OwnerSettings } from './pages/OwnerSettings';
import { OwnerCompliance } from './pages/OwnerCompliance';
import { SuperAdminDashboard } from './pages/SuperAdminDashboard';
import { SuperAdminProfile } from './pages/SuperAdminProfile';
import { SuperAdminSettings } from './pages/SuperAdminSettings';
import { SuperAdminAccommodationReview } from './pages/SuperAdminAccommodationReview';
import { SuperAdminReadingRoomReview } from './pages/SuperAdminReadingRoomReview';
import { SupportPage } from './pages/Support';
import { MessagesPage } from './pages/MessagesPage';
import { MockPaymentGateway } from './pages/MockPaymentGateway';
import { AppState, UserRole, User, Booking, CabinStatus, ReadingRoom, Cabin, Notification, Review, WaitlistEntry, Accommodation, SupportTicket, PlatformSettings, PromotionPlan, PromotionRequest, Message, Conversation } from './types';
import { MOCK_USERS, MOCK_BOOKINGS, generateCabins, MOCK_NOTIFICATIONS, MOCK_READING_ROOMS, MOCK_REVIEWS, MOCK_ACCOMMODATIONS, MOCK_TICKETS, MOCK_PLANS, MOCK_PROMOTION_PLANS, MOCK_PROMOTION_REQUESTS } from './services/mockData';
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
        platformName: 'StudySpace',
        supportEmail: 'support@studyspace.com',
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
          console.log('✅ Loaded subscription plans:', subscriptionPlans.length, subscriptionPlans);
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
            console.log('✅ Loaded favorites:', myFavorites.length);
          } catch (e) {
            console.warn('Failed to fetch favorites:', e);
          }

          // Fetch user's conversations and messages
          let myConversations: Conversation[] = [];
          try {
            myConversations = await messagingService.getConversations();
            console.log('✅ Loaded conversations:', myConversations.length);
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
    if (!appState.currentUser) return;

    // Use readingRoomId from first cabin data if provided (multi-venue support)
    // Otherwise fallback to finding first owned room
    const roomId = newCabinsData[0]?.readingRoomId ||
      appState.readingRooms.find(r => r.ownerId === appState.currentUser?.id)?.id;
    if (!roomId) return;

    try {
      const createdCabins = await venueService.createCabinsBulk(roomId, newCabinsData);
      setAppState(prev => ({
        ...prev,
        cabins: [...prev.cabins, ...createdCabins]
      }));
    } catch (err) {
      console.error("Failed to add cabins:", err);
      toast.error("Failed to batch create cabins. Some may have failed.");
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
    if (!appState.currentUser) return;

    const cabin = appState.cabins.find(c => c.id === cabinId);
    if (!cabin) return;

    try {
      const startDate = new Date().toISOString().split('T')[0];
      const endDate = new Date(Date.now() + durationMonths * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      const amount = (cabin.price || 0) * durationMonths;

      // Call Backend
      const booking = await bookingService.createBooking(cabinId, durationMonths, startDate, endDate, amount);

      // Enrich with correct cabin number (service returns '000')
      const enrichedBooking: Booking = { ...booking, cabinNumber: cabin.number };

      // Optimistic UI Update (or re-fetch)
      setAppState(prev => {
        // Remove from waitlist if present (since booking fulfills it)
        const updatedWaitlist = prev.waitlist.filter(w => w.cabinId !== cabinId);
        const hasActiveWaitlist = updatedWaitlist.length > 0;

        const updatedUser = prev.currentUser ? { ...prev.currentUser, has_active_waitlist: hasActiveWaitlist } : prev.currentUser;
        if (updatedUser) {
          localStorage.setItem('studySpace_user', JSON.stringify(updatedUser));
        }

        return {
          ...prev,
          bookings: [enrichedBooking, ...prev.bookings],
          cabins: prev.cabins.map(c =>
            c.id === cabinId
              ? { ...c, status: CabinStatus.OCCUPIED, currentOccupantId: prev.currentUser?.id }
              : c
          ),
          waitlist: updatedWaitlist,
          currentUser: updatedUser
        };
      });

      // Navigate or show success? (Optional: The UI probably updates automatically)

    } catch (err: any) {
      console.error("Booking failed:", err);
      // Alert with detailed error message for debugging
      const errorMsg = err.response?.data?.detail
        ? (typeof err.response.data.detail === 'object' ? JSON.stringify(err.response.data.detail) : err.response.data.detail)
        : err.message || "Unknown error";
      toast.error(`Booking failed! ${errorMsg}`);
      throw err;
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

      console.log('Booking extended successfully:', result);
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

  // Poll for new messages globally (every 15s) to keep badge updated
  useEffect(() => {
    if (!appState.currentUser) return;

    // Function to fetch fresh conversations
    const refreshConversations = async () => {
      try {
        const freshConversations = await messagingService.getConversations();
        setAppState(prev => ({ ...prev, conversations: freshConversations }));
      } catch (e) {
        console.error("Bg sync failed", e);
      }
    };

    // 1. Initial and Periodic Poll
    const interval = setInterval(refreshConversations, 15000);

    // 2. Listen for 'messagesUpdated' event (triggered by read actions/sending)
    const handleMessagesUpdated = () => {
      refreshConversations();
    };
    window.addEventListener('messagesUpdated', handleMessagesUpdated);

    // Initial fetch to be sure
    // refreshConversations(); // Optional, already done by main fetchData but good safety

    return () => {
      clearInterval(interval);
      window.removeEventListener('messagesUpdated', handleMessagesUpdated);
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
        <AuthPage onLogin={handleLogin} />
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
        <Layout
          user={appState.currentUser}
          onLogout={handleLogout}
          notifications={currentUserNotifications}
          onMarkNotificationRead={handleMarkNotificationRead}
          hasReadingRooms={hasReadingRooms}
          unreadMessageCount={unreadMessageCount}
        >
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
                <Route path="/admin/settings" element={<OwnerSettings user={appState.currentUser} />} />
                <Route path="/admin/compliance" element={<OwnerCompliance state={appState} user={appState.currentUser} onUpdateUser={handleUpdateUser} />} />
                <Route path="/admin/messages" element={
                  <MessagesPage
                    currentUserId={appState.currentUser.id}
                    currentUserRole={appState.currentUser.role}
                  />
                } />
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
                <Route path="/super-admin/*" element={<SuperAdminDashboard state={appState} />} />
              </>
            )}

            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </Layout>
      </Router>
    </ErrorBoundary>
  );
};

export default App;
