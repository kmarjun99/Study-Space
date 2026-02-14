
import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { Logo } from './Logo';
import {
  LayoutDashboard,
  BookOpen,
  Users,
  Settings,
  LogOut,
  Bell,
  CreditCard,
  Building2,
  Check,
  Home,
  Menu,
  Activity,
  MapPin,
  Verified,
  Layers,
  LineChart,
  DollarSign,
  HelpCircle,
  Zap,
  MessageCircle,
  Clock
} from 'lucide-react';
import { User, UserRole, Notification } from '../types';

interface LayoutProps {
  children: React.ReactNode;
  user: User;
  onLogout: () => void;
  notifications: Notification[];
  onMarkNotificationRead: (id: string) => void;
  hasReadingRooms?: boolean; // New prop to control Waitlist tab visibility
  unreadMessageCount?: number; // New prop for unread messages badge
}

export const Layout: React.FC<LayoutProps> = ({ children, user, onLogout, notifications, onMarkNotificationRead, hasReadingRooms, unreadMessageCount = 0 }) => {

  const location = useLocation();
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const isAdmin = user.role === UserRole.ADMIN;
  const isSuperAdmin = user.role === UserRole.SUPER_ADMIN;
  const unreadCount = notifications.filter(n => !n.read).length;

  let navigation;
  if (isSuperAdmin) {
    navigation = [
      { name: 'Dashboard', href: '/super-admin', icon: Activity },
      { name: 'Cities', href: '/super-admin/cities', icon: MapPin },
      { name: 'Locations', href: '/super-admin/locations', icon: MapPin },
      { name: 'Supply', href: '/super-admin/supply', icon: Building2 },
      { name: 'Users', href: '/super-admin/users', icon: Users },
      { name: 'Bookings', href: '/super-admin/bookings', icon: BookOpen },
      { name: 'Finance', href: '/super-admin/finance', icon: DollarSign },
      { name: 'Trust & Safety', href: '/super-admin/trust', icon: Verified },
      { name: 'Ads', href: '/super-admin/ads', icon: Layers },
      { name: 'Promotions', href: '/super-admin/promotions', icon: Zap },
      { name: 'Plans', href: '/super-admin/plans', icon: CreditCard },
      { name: 'Analytics', href: '/super-admin/analytics', icon: LineChart },
      { name: 'Support Tickets', href: '/super-admin/tickets', icon: HelpCircle },
      { name: 'Settings', href: '/super-admin/settings', icon: Settings },
    ];

  } else if (isAdmin) {
    navigation = [
      { name: 'Dashboard', href: '/admin', icon: LayoutDashboard },
      { name: 'My Listings', href: '/admin/listings', icon: Building2 },
      { name: 'Students', href: '/admin/students', icon: Users },
      { name: 'Financials', href: '/admin/financials', icon: CreditCard },
      ...(hasReadingRooms ? [{ name: 'Waitlists', href: '/admin/waitlists', icon: Clock }] : []),
      { name: 'Messages', href: '/admin/messages', icon: MessageCircle },
    ];

  } else {
    navigation = [
      { name: 'Dashboard', href: '/student', icon: LayoutDashboard },
      { name: 'Book Cabin', href: '/student/book', icon: BookOpen },
      // Conditional Waitlist Tab
      ...(user.has_active_waitlist ? [{ name: 'Waitlists', href: '/student/waitlists', icon: Clock }] : []),
      { name: 'Find PG/Hostel', href: '/student/accommodation', icon: Home },
      { name: 'Payments', href: '/student/payments', icon: CreditCard },
      { name: 'Messages', href: '/student/messages', icon: MessageCircle },
    ];
  }

  const NavItem: React.FC<{ item: any }> = ({ item }) => {
    const isActive = location.pathname === item.href;
    const baseClass = "group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 relative";
    const activeClass = isActive
      ? "bg-indigo-800 text-white shadow-sm translate-x-1"
      : "text-indigo-200 hover:bg-indigo-800/50 hover:text-white hover:translate-x-1";

    return (
      <Link to={item.href} className={`${baseClass} ${activeClass}`}>
        <div className="relative mr-3 flex-shrink-0">
          <item.icon className={`h-5 w-5 ${isActive ? 'text-white' : 'text-indigo-300 group-hover:text-white'}`} />
          {item.name === 'Messages' && unreadMessageCount > 0 && (
            <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white shadow-sm">
              {unreadMessageCount > 9 ? '9+' : unreadMessageCount}
            </span>
          )}
        </div>
        {item.name}
      </Link>
    );
  };

  // --- Notification Panel Component ---
  const NotificationPanel = () => (
    <div className="w-80 bg-white rounded-xl shadow-2xl border border-gray-100 overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-200 origin-top-right">
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 flex justify-between items-center">
        <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
        {unreadCount > 0 && <span className="text-xs font-bold bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">{unreadCount} new</span>}
      </div>
      <div className="max-h-96 overflow-y-auto custom-scrollbar">
        {notifications.length > 0 ? (
          notifications.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).map((notification) => (
            <div
              key={notification.id}
              onClick={() => onMarkNotificationRead(notification.id)}
              className={`px-4 py-3 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-colors ${!notification.read ? 'bg-indigo-50/40' : ''}`}
            >
              <div className="flex justify-between items-start gap-2">
                <p className={`text-sm leading-snug ${!notification.read ? 'font-semibold text-gray-900' : 'text-gray-600'}`}>
                  {notification.title}
                </p>
                {!notification.read ? (
                  <span className="h-2 w-2 bg-indigo-500 rounded-full mt-1.5 flex-shrink-0 animate-pulse"></span>
                ) : (
                  <Check className="h-3 w-3 text-gray-400 mt-1 flex-shrink-0" />
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{notification.message}</p>
              <p className="text-[10px] text-gray-400 mt-2">
                {new Date(notification.date).toLocaleDateString()}
              </p>
            </div>
          ))
        ) : (
          <div className="px-4 py-12 text-center text-gray-400 text-sm flex flex-col items-center">
            <Bell className="h-8 w-8 mb-2 text-gray-200" />
            <p>All caught up!</p>
          </div>
        )}
      </div>
    </div>
  );

  // Backdrop to close notifications
  const Backdrop = () => (
    isNotificationsOpen ? (
      <div className="fixed inset-0 z-40 bg-transparent" onClick={() => setIsNotificationsOpen(false)}></div>
    ) : null
  );


  return (
    <div className="fixed inset-0 w-full bg-gray-50 font-sans antialiased selection:bg-indigo-100 selection:text-indigo-900 flex overflow-hidden">
      <Backdrop />

      {/* Sidebar for Desktop - Static Flex Item */}
      <div className="hidden md:flex w-64 flex-col bg-indigo-900 text-white flex-shrink-0 transition-all duration-300 shadow-xl z-20 relative">






        {/* Navigation */}
        <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar px-4 py-6 space-y-1">
          <p className="px-3 text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">MENU</p>
          {navigation.map((item) => (
            <NavItem key={item.name} item={item} />
          ))}
        </div>


        {/* Sidebar Footer (User Profile) */}
        <div className="flex-shrink-0 bg-indigo-950 p-4 border-t border-indigo-800">
          {isNotificationsOpen && (
            <div className="absolute bottom-20 left-4 w-80 z-50">
              <NotificationPanel />
            </div>
          )}


          <Link
            to={user.role === 'SUPER_ADMIN' ? '/super-admin/profile' : `/${user.role.toLowerCase()}/profile`}
            className="flex items-center w-full hover:bg-indigo-900/50 transition-colors p-1 rounded-lg"
          >
            <div className="relative">
              <div className="h-9 w-9 rounded-full bg-indigo-200 text-indigo-700 flex items-center justify-center overflow-hidden border border-indigo-400">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </div>
              <span className="absolute bottom-0 right-0 block h-2.5 w-2.5 rounded-full ring-2 ring-indigo-900 bg-green-400"></span>
            </div>
            <div className="ml-3 flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user.name}</p>
              <p className="text-xs font-medium text-indigo-400 truncate capitalize">{user.role.toLowerCase()}</p>
            </div>
          </Link>
        </div>
      </div>

      {/* Main Content Area - Flex Grow */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-gray-50 relative">







        {/* Mobile Header - Sticky */}
        <div className="md:hidden flex-shrink-0 flex h-14 bg-white border-b border-gray-200 items-center justify-between px-4 z-30 shadow-sm sticky top-0">

          <div className="flex flex-col">
            <h1 className="text-sm font-bold text-gray-900 leading-tight">Hello, {user.name.split(' ')[0]}</h1>
            <p className="text-[10px] text-gray-500 font-medium">Welcome back</p>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative">
              {isNotificationsOpen && (
                <div className="absolute top-10 right-0 z-50">
                  <NotificationPanel />
                </div>
              )}
              <button
                onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                className="p-1 text-gray-500 hover:text-gray-700 relative"
              >
                <Bell className="h-6 w-6" />
                {unreadCount > 0 && (
                  <span className="absolute top-0 right-0 block h-2 w-2 rounded-full ring-2 ring-white bg-red-500" />
                )}
              </button>
            </div>


            {/* Profile Link (Mobile) */}
            <Link
              to={user.role === 'SUPER_ADMIN' ? '/super-admin/profile' : `/${user.role.toLowerCase()}/profile`}
              className="relative flex items-center justify-center p-1 rounded-full text-gray-400 hover:text-gray-500 hover:bg-gray-100"
            >
              <div className="h-8 w-8 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center overflow-hidden border border-gray-300">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </div>
            </Link>
          </div>
        </div>



        {/* Main Scrollable Content */}
        <main className="flex-1 overflow-y-auto focus:outline-none p-2 pt-2 md:p-8 md:pt-8 pb-32 md:pb-10 scroll-smooth custom-scrollbar" id="main-content">
          <div className="max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>


        {/* Mobile Bottom Navigation - Fixed overlay */}
        <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex justify-around items-center h-16 pb-safe z-40 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
          {/* Logo as Home/Dashboard Anchor */}
          <Link
            to={user.role === UserRole.STUDENT ? '/student' : (user.role === UserRole.ADMIN ? '/admin' : '/super-admin')}
            className={`flex flex-col items-center justify-center w-full h-full space-y-1 transition-colors ${location.pathname === (user.role === UserRole.STUDENT ? '/student' : (user.role === UserRole.ADMIN ? '/admin' : '/super-admin')) ? 'text-indigo-600' : 'text-gray-400 hover:text-gray-600'}`}
          >
            <div className={`p-1 rounded-full transition-all ${location.pathname === (user.role === UserRole.STUDENT ? '/student' : (user.role === UserRole.ADMIN ? '/admin' : '/super-admin')) ? 'bg-indigo-50 translate-y-[-2px]' : ''}`}>
              <Logo variant="icon" className="h-6 w-6" />
            </div>
            <span className={`text-[10px] font-medium ${location.pathname === (user.role === UserRole.STUDENT ? '/student' : (user.role === UserRole.ADMIN ? '/admin' : '/super-admin')) ? 'font-bold' : ''}`}>Home</span>
          </Link>

          {navigation.map((item) => {
            if (item.name === 'Dashboard') return null; // Skip standard Dashboard item to avoid duplicate Home

            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex flex-col items-center justify-center w-full h-full space-y-1 transition-colors ${isActive ? 'text-indigo-600' : 'text-gray-400 hover:text-gray-600'
                  }`}
              >

                <div className={`p-1 rounded-full transition-all relative ${isActive ? 'bg-indigo-50 translate-y-[-2px]' : ''}`}>
                  <item.icon className={`h-5 w-5 ${isActive ? 'fill-current opacity-100' : ''} stroke-current`} strokeWidth={2} />
                  {item.name === 'Messages' && unreadMessageCount > 0 && (
                    <span className="absolute -top-1 -right-1 flex h-3 w-3 items-center justify-center rounded-full bg-red-500 text-[8px] font-bold text-white shadow-sm ring-1 ring-white">
                      {unreadMessageCount > 9 ? '9+' : unreadMessageCount}
                    </span>
                  )}
                </div>
                <span className={`text-[10px] font-medium text-center leading-tight ${isActive ? 'font-bold' : ''}`}>{item.name}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
};
