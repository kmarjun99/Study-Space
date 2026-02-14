
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { User } from '../types';
import { Button, Modal, Input, Badge } from '../components/UI';
import {
  User as UserIcon,
  Mail, // Import Mail
  Phone, // Import Phone
  Shield,
  LogOut,
  ChevronRight,
  HelpCircle,
  CreditCard,
  Building2,
  Settings,
  Camera
} from 'lucide-react';

interface AdminProfileProps {
  user: User;
  onUpdateUser: (data: Partial<User>) => void;
  onLogout: () => void;
}

export const AdminProfile: React.FC<AdminProfileProps> = ({ user, onUpdateUser, onLogout }) => {
  const navigate = useNavigate();
  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: user.name,
    phone: user.phone || '',
  });
  const [isLoading, setIsLoading] = useState(false);

  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null); // Keep message state if needed later, though modal handles it

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmitUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    setTimeout(() => {
      onUpdateUser({
        name: formData.name,
        phone: formData.phone,
      });
      setIsLoading(false);
      setIsEditProfileOpen(false);
    }, 800);
  };

  const ProfileItem = ({ icon: Icon, label, onClick, isDestructive = false }: { icon: any, label: string, onClick?: () => void, isDestructive?: boolean }) => (
    <div
      onClick={onClick}
      className={`flex items-center justify-between p-4 bg-white border-b border-gray-50 last:border-none cursor-pointer hover:bg-gray-50 transition-colors ${isDestructive ? 'text-red-600' : 'text-gray-900'}`}
    >
      <div className="flex items-center gap-4">
        <div className={`p-2 rounded-full ${isDestructive ? 'bg-red-50 text-red-600' : 'bg-gray-100 text-gray-600'}`}>
          <Icon className="w-5 h-5" />
        </div>
        <span className={`font-medium ${isDestructive ? 'font-semibold' : ''}`}>{label}</span>
      </div>
      {!isDestructive && <ChevronRight className="w-5 h-5 text-gray-400" />}
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto pb-10">

      {/* A. Profile Header */}
      <div className="bg-white p-6 mb-2 flex flex-col items-center text-center border-b border-gray-100">
        <div className="relative mb-4">
          <div className="h-24 w-24 rounded-full bg-gray-200 text-gray-500 flex items-center justify-center overflow-hidden border-4 border-white shadow-lg">
            {/* Generic Person Avatar */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-12 w-12"
            >
              <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
        </div>

        <h1 className="text-xl font-bold text-gray-900">{user.name}</h1>
        <div className="text-sm text-gray-500 mt-1 flex flex-col gap-0.5">
          <span>{user.email}</span>
          {user.phone && <span>{user.phone}</span>}
        </div>
      </div>

      {/* B. Profile Actions List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden mb-6">
        <ProfileItem icon={UserIcon} label="Edit Profile Details" onClick={() => setIsEditProfileOpen(true)} />
        <ProfileItem icon={Shield} label="Account & Compliance" onClick={() => navigate('/admin/compliance')} />
        <ProfileItem icon={CreditCard} label="Subscription & Billing" onClick={() => navigate('/admin/billing')} />
        <ProfileItem icon={Settings} label="App Settings" onClick={() => navigate('/admin/settings')} />
        <ProfileItem icon={HelpCircle} label="Help & Support" onClick={() => navigate('/support')} />
      </div>

      {/* C. Logout */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <ProfileItem icon={LogOut} label="Logout" onClick={onLogout} isDestructive />
      </div>

      {/* Edit Profile Modal */}
      <Modal
        isOpen={isEditProfileOpen}
        onClose={() => setIsEditProfileOpen(false)}
        title="Edit Profile"
      >
        <form onSubmit={handleSubmitUpdate} className="space-y-4 py-2">
          <Input label="Full Name" name="name" value={formData.name} onChange={handleChange} />
          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input className="w-full px-3 py-2 border border-gray-200 bg-gray-50 text-gray-500 rounded-lg" value={user.email} readOnly />
            <Mail className="w-4 h-4 text-gray-400 absolute right-3 top-9" />
          </div>
          <Input label="Phone Number" name="phone" value={formData.phone} onChange={handleChange} placeholder="+91..." />

          <div className="pt-4 flex gap-3">
            <Button type="button" variant="ghost" className="flex-1" onClick={() => setIsEditProfileOpen(false)}>Cancel</Button>
            <Button type="submit" className="flex-1" isLoading={isLoading}>Save Changes</Button>
          </div>
        </form>
      </Modal>

    </div>
  );
};
