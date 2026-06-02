import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { User } from '../types';
import { Card, Button } from '../components/UI';
import {
    ArrowLeft, Settings, Bell, BellOff, Shield, HelpCircle,
    Mail, MessageSquare, CreditCard, Star, Save, Check
} from 'lucide-react';

interface OwnerSettingsProps {
    user: User;
}

interface NotificationSettings {
    bookingAlerts: boolean;
    paymentAlerts: boolean;
    reviewAlerts: boolean;
    marketingEmails: boolean;
    supportUpdates: boolean;
}

interface PrivacySettings {
    showPhoneToStudents: boolean;
    showEmailToStudents: boolean;
    allowAnalytics: boolean;
}

const STORAGE_KEY = 'studySpace_ownerSettings';

export const OwnerSettings: React.FC<OwnerSettingsProps> = ({ user }) => {
    const navigate = useNavigate();
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);

    // Load settings from localStorage
    const [notifications, setNotifications] = useState<NotificationSettings>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            return parsed.notifications || {
                bookingAlerts: true,
                paymentAlerts: true,
                reviewAlerts: true,
                marketingEmails: false,
                supportUpdates: true
            };
        }
        return {
            bookingAlerts: true,
            paymentAlerts: true,
            reviewAlerts: true,
            marketingEmails: false,
            supportUpdates: true
        };
    });

    const [privacy, setPrivacy] = useState<PrivacySettings>(() => {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            return parsed.privacy || {
                showPhoneToStudents: true,
                showEmailToStudents: false,
                allowAnalytics: true
            };
        }
        return {
            showPhoneToStudents: true,
            showEmailToStudents: false,
            allowAnalytics: true
        };
    });

    const handleSave = () => {
        setIsSaving(true);
        // Save to localStorage
        const settings = { notifications, privacy };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));

        setTimeout(() => {
            setIsSaving(false);
            setSaveMessage('Settings saved successfully!');
            setTimeout(() => setSaveMessage(null), 3000);
        }, 800);
    };

    const ToggleSwitch = ({
        enabled,
        onChange,
        label,
        description,
        icon: Icon
    }: {
        enabled: boolean;
        onChange: (value: boolean) => void;
        label: string;
        description: string;
        icon: any;
    }) => (
        <div className="flex items-start justify-between py-4 border-b border-gray-100 last:border-none">
            <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg ${enabled ? 'bg-indigo-50 text-indigo-600' : 'bg-gray-100 text-gray-400'}`}>
                    <Icon className="w-5 h-5" />
                </div>
                <div>
                    <p className="font-medium text-gray-900">{label}</p>
                    <p className="text-sm text-gray-500">{description}</p>
                </div>
            </div>
            <button
                onClick={() => onChange(!enabled)}
                className={`relative w-12 h-6 rounded-full transition-colors ${enabled ? 'bg-indigo-600' : 'bg-gray-300'
                    }`}
            >
                <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${enabled ? 'translate-x-6' : 'translate-x-0'
                        }`}
                />
            </button>
        </div>
    );

    return (
        <div className="max-w-3xl mx-auto pb-10">
            {/* Header */}
            <div className="mb-6">
                <button
                    onClick={() => navigate('/admin/profile')}
                    className="flex items-center text-indigo-600 hover:text-indigo-800 font-medium mb-4 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4 mr-1" /> Back to Profile
                </button>
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">App Settings</h1>
                        <p className="text-gray-500 mt-1">Manage your notification and privacy preferences</p>
                    </div>
                    <Button onClick={handleSave} isLoading={isSaving}>
                        <Save className="w-4 h-4 mr-2" /> Save Changes
                    </Button>
                </div>
            </div>

            {/* Save Success Message */}
            {saveMessage && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700">
                    <Check className="w-5 h-5" />
                    <span className="font-medium">{saveMessage}</span>
                </div>
            )}

            {/* Notification Preferences */}
            <Card className="p-6 mb-6">
                <div className="flex items-center gap-2 mb-4">
                    <Bell className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-lg font-bold text-gray-900">Notification Preferences</h3>
                </div>
                <p className="text-sm text-gray-500 mb-4">
                    Choose which notifications you'd like to receive
                </p>

                <div className="space-y-1">
                    <ToggleSwitch
                        enabled={notifications.bookingAlerts}
                        onChange={(val) => setNotifications(prev => ({ ...prev, bookingAlerts: val }))}
                        label="Booking Alerts"
                        description="Get notified when a student books or cancels a cabin"
                        icon={CreditCard}
                    />
                    <ToggleSwitch
                        enabled={notifications.paymentAlerts}
                        onChange={(val) => setNotifications(prev => ({ ...prev, paymentAlerts: val }))}
                        label="Payment Notifications"
                        description="Receive alerts for payments and settlements"
                        icon={CreditCard}
                    />
                    <ToggleSwitch
                        enabled={notifications.reviewAlerts}
                        onChange={(val) => setNotifications(prev => ({ ...prev, reviewAlerts: val }))}
                        label="Review Alerts"
                        description="Be notified when students leave reviews"
                        icon={Star}
                    />
                    <ToggleSwitch
                        enabled={notifications.supportUpdates}
                        onChange={(val) => setNotifications(prev => ({ ...prev, supportUpdates: val }))}
                        label="Support Updates"
                        description="Get updates on your support tickets"
                        icon={HelpCircle}
                    />
                    <ToggleSwitch
                        enabled={notifications.marketingEmails}
                        onChange={(val) => setNotifications(prev => ({ ...prev, marketingEmails: val }))}
                        label="Marketing Emails"
                        description="Receive tips, promotions, and platform updates"
                        icon={Mail}
                    />
                </div>
            </Card>

            {/* Privacy Settings */}
            <Card className="p-6 mb-6">
                <div className="flex items-center gap-2 mb-4">
                    <Shield className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-lg font-bold text-gray-900">Privacy & Data</h3>
                </div>
                <p className="text-sm text-gray-500 mb-4">
                    Control what information is visible to students
                </p>

                <div className="space-y-1">
                    <ToggleSwitch
                        enabled={privacy.showPhoneToStudents}
                        onChange={(val) => setPrivacy(prev => ({ ...prev, showPhoneToStudents: val }))}
                        label="Show Phone Number"
                        description="Allow students to see your contact phone on listings"
                        icon={MessageSquare}
                    />
                    <ToggleSwitch
                        enabled={privacy.showEmailToStudents}
                        onChange={(val) => setPrivacy(prev => ({ ...prev, showEmailToStudents: val }))}
                        label="Show Email Address"
                        description="Allow students to see your email on listings"
                        icon={Mail}
                    />
                    <ToggleSwitch
                        enabled={privacy.allowAnalytics}
                        onChange={(val) => setPrivacy(prev => ({ ...prev, allowAnalytics: val }))}
                        label="Usage Analytics"
                        description="Help us improve by sharing anonymous usage data"
                        icon={Settings}
                    />
                </div>
            </Card>

            {/* Support Section */}
            <Card className="p-6">
                <div className="flex items-center gap-2 mb-4">
                    <HelpCircle className="w-5 h-5 text-indigo-600" />
                    <h3 className="text-lg font-bold text-gray-900">Support Preferences</h3>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                    <div className="flex items-start gap-3">
                        <div className="p-2 bg-indigo-100 rounded-lg">
                            <MessageSquare className="w-5 h-5 text-indigo-600" />
                        </div>
                        <div className="flex-1">
                            <p className="font-medium text-gray-900">Need Help?</p>
                            <p className="text-sm text-gray-500 mb-3">
                                Our support team is available 24/7 to assist you with any issues.
                            </p>
                            <Button variant="outline" onClick={() => navigate('/support')}>
                                Contact Support
                            </Button>
                        </div>
                    </div>
                </div>
            </Card>
        </div>
    );
};

export default OwnerSettings;
