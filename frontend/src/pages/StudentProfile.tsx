
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { User, AppState, Accommodation } from '../types';
import { Button, Card, Input, Badge, Modal } from '../components/UI';
import { venueService } from '../services/venueService';
import { inquiryService, Inquiry } from '../services/inquiryService';
import { paymentService, PaymentModesResponse, Refund } from '../services/paymentService';
import {
  User as UserIcon,
  Mail,
  Phone,
  ChevronRight,
  HelpCircle,
  LogOut,
  CreditCard,
  RotateCcw, // Refunds
  Star,
  MapPin,
  Trash2,
  Camera,
  MessageSquare,
  Calendar,
  CheckCircle,
  Clock,
  AlertCircle,
  DollarSign
} from 'lucide-react';

interface StudentProfileProps {
  user: User;
  state: AppState;
  onUpdateUser: (data: Partial<User>) => void;
  onDeleteReview?: (id: string) => void;
  onAddReview: (review: { readingRoomId?: string, accommodationId?: string, rating: number, comment: string }) => void;
  onLogout: () => void;
}

export const StudentProfile: React.FC<StudentProfileProps> = ({ user, state, onUpdateUser, onDeleteReview, onAddReview, onLogout }) => {
  const navigate = useNavigate();

  // --- Edit Profile State ---
  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: user.name,
    email: user.email,
    phone: user.phone || '',
  });
  const [isLoading, setIsLoading] = useState(false);

  // --- Reviews State ---
  const [isReviewsOpen, setIsReviewsOpen] = useState(false);
  const [fetchedReviews, setFetchedReviews] = useState<any[]>([]);
  const [isLoadingReviews, setIsLoadingReviews] = useState(false);

  // Fetch reviews when modal opens
  React.useEffect(() => {
    if (isReviewsOpen && user.id) {
      const fetchReviews = async () => {
        setIsLoadingReviews(true);
        try {
          const reviews = await venueService.getMyReviews(user.id);
          setFetchedReviews(reviews);
        } catch (e) {
          console.error("Failed to fetch reviews", e);
        } finally {
          setIsLoadingReviews(false);
        }
      };
      fetchReviews();
    }
  }, [isReviewsOpen, user.id]);

  // --- My Inquiries State ---
  const [isInquiriesOpen, setIsInquiriesOpen] = useState(false);
  const [myInquiries, setMyInquiries] = useState<Inquiry[]>([]);
  const [isLoadingInquiries, setIsLoadingInquiries] = useState(false);

  React.useEffect(() => {
    if (isInquiriesOpen) {
      const fetchInquiries = async () => {
        setIsLoadingInquiries(true);
        try {
          const data = await inquiryService.getMyInquiries();
          setMyInquiries(data);
        } catch (e) {
          console.error('Failed to fetch inquiries', e);
        } finally {
          setIsLoadingInquiries(false);
        }
      };
      fetchInquiries();
    }
  }, [isInquiriesOpen]);

  // --- Payment Modes State ---
  const [isPaymentModesOpen, setIsPaymentModesOpen] = useState(false);
  const [paymentModes, setPaymentModes] = useState<PaymentModesResponse | null>(null);
  const [isLoadingPaymentModes, setIsLoadingPaymentModes] = useState(false);

  React.useEffect(() => {
    if (isPaymentModesOpen) {
      const fetchPaymentModes = async () => {
        setIsLoadingPaymentModes(true);
        try {
          const data = await paymentService.getPaymentModes();
          setPaymentModes(data);
        } catch (e) {
          console.error('Failed to fetch payment modes', e);
        } finally {
          setIsLoadingPaymentModes(false);
        }
      };
      fetchPaymentModes();
    }
  }, [isPaymentModesOpen]);

  // --- My Refunds State ---
  const [isRefundsOpen, setIsRefundsOpen] = useState(false);
  const [myRefunds, setMyRefunds] = useState<Refund[]>([]);
  const [isLoadingRefunds, setIsLoadingRefunds] = useState(false);

  React.useEffect(() => {
    if (isRefundsOpen) {
      const fetchRefunds = async () => {
        setIsLoadingRefunds(true);
        try {
          const data = await paymentService.getMyRefunds();
          setMyRefunds(data);
        } catch (e) {
          console.error('Failed to fetch refunds', e);
        } finally {
          setIsLoadingRefunds(false);
        }
      };
      fetchRefunds();
    }
  }, [isRefundsOpen]);


  // --- Handlers ---
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

  const getEntityDetails = (review: any) => {
    if (review.readingRoomId) {
      return state.readingRooms.find(r => r.id === review.readingRoomId);
    } else if (review.accommodationId) {
      return state.accommodations.find(a => a.id === review.accommodationId);
    }
    return null;
  };

  // --- Components ---
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
        <ProfileItem icon={HelpCircle} label="Help & Support" onClick={() => navigate('/support')} />
        <ProfileItem icon={UserIcon} label="Edit Profile Details" onClick={() => setIsEditProfileOpen(true)} />
        <ProfileItem icon={Star} label="My Reviews" onClick={() => setIsReviewsOpen(true)} />
        <ProfileItem icon={MessageSquare} label="My Inquiries" onClick={() => setIsInquiriesOpen(true)} />
        <ProfileItem icon={RotateCcw} label="My Refunds" onClick={() => setIsRefundsOpen(true)} />
        <ProfileItem icon={CreditCard} label="Payment Modes" onClick={() => setIsPaymentModesOpen(true)} />
      </div>

      {/* C. Logout */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <ProfileItem icon={LogOut} label="Logout" onClick={onLogout} isDestructive />
      </div>


      {/* --- Modals for Interaction --- */}

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
            <input className="w-full px-3 py-2 border border-gray-200 bg-gray-50 text-gray-500 rounded-lg" value={formData.email} readOnly />
            <Mail className="w-4 h-4 text-gray-400 absolute right-3 top-9" />
          </div>
          <Input label="Phone Number" name="phone" value={formData.phone} onChange={handleChange} placeholder="+91..." />

          <div className="pt-4 flex gap-3">
            <Button type="button" variant="ghost" className="flex-1" onClick={() => setIsEditProfileOpen(false)}>Cancel</Button>
            <Button type="submit" className="flex-1" isLoading={isLoading}>Save Changes</Button>
          </div>
        </form>
      </Modal>

      {/* My Reviews Modal/Drawer */}
      <Modal
        isOpen={isReviewsOpen}
        onClose={() => setIsReviewsOpen(false)}
        title="My Reviews"
      >
        <div className="max-h-[60vh] overflow-y-auto custom-scrollbar -mx-4 px-4">
          {isLoadingReviews ? (
            <div className="text-center py-8">Loading reviews...</div>
          ) : fetchedReviews.length > 0 ? (
            <div className="space-y-4 py-2">
              {fetchedReviews.map(review => {
                const entity = getEntityDetails(review);
                return (
                  <div key={review.id} className="border border-gray-100 rounded-lg p-4 bg-gray-50 text-sm">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-gray-900">{entity?.name || 'Unknown Venue'}</h4>
                      <div className="flex text-yellow-400">
                        {[...Array(5)].map((_, i) => (
                          <Star key={i} className={`w-3 h-3 ${i < review.rating ? 'fill-current' : 'text-gray-300'}`} />
                        ))}
                      </div>
                    </div>
                    <p className="text-gray-600 italic">"{review.comment}"</p>
                    <div className="mt-2 flex justify-between items-center text-xs text-gray-400">
                      <span>{review.created_at ? new Date(review.created_at).toLocaleDateString() : 'Date N/A'}</span>
                      {onDeleteReview && (
                        <button onClick={() => {
                          if (window.confirm('Delete review?')) onDeleteReview(review.id);
                        }} className="text-red-400 hover:text-red-600 flex items-center">
                          <Trash2 className="w-3 h-3 mr-1" /> Delete
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Star className="w-10 h-10 mx-auto text-gray-200 mb-2" />
              <p>No reviews yet.</p>
            </div>
          )}

        </div>
      </Modal>

      {/* My Inquiries Modal */}
      <Modal
        isOpen={isInquiriesOpen}
        onClose={() => setIsInquiriesOpen(false)}
        title="My Questions & Requests"
      >
        <div className="max-h-[60vh] overflow-y-auto custom-scrollbar -mx-4 px-4">
          {isLoadingInquiries ? (
            <div className="text-center py-8">Loading inquiries...</div>
          ) : myInquiries.length > 0 ? (
            <div className="space-y-4 py-2">
              {myInquiries.map(inq => (
                <div key={inq.id} className={`border rounded-lg p-4 ${inq.status === 'REPLIED' ? 'border-green-200 bg-green-50' : 'border-gray-100 bg-gray-50'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${inq.type === 'VISIT' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                      {inq.type === 'VISIT' ? '📅 Visit' : '💬 Question'}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${inq.status === 'PENDING' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'
                      }`}>
                      {inq.status === 'PENDING' ? <><Clock className="w-3 h-3 inline mr-0.5" /> Awaiting Reply</> : <><CheckCircle className="w-3 h-3 inline mr-0.5" /> Replied</>}
                    </span>
                  </div>
                  <h4 className="font-bold text-gray-900 mb-1">{inq.accommodationName}</h4>
                  <p className="text-sm text-gray-600 italic mb-2">"{inq.question}"</p>

                  {inq.type === 'VISIT' && inq.preferredDate && (
                    <p className="text-xs text-indigo-600 mb-2 flex items-center gap-1">
                      <Calendar className="w-3 h-3" /> {inq.preferredDate} at {inq.preferredTime}
                    </p>
                  )}

                  {inq.reply && (
                    <div className="bg-white p-3 rounded-lg border-l-2 border-green-500 mt-2">
                      <p className="text-xs text-green-600 font-bold mb-1">Owner's Reply:</p>
                      <p className="text-gray-800">{inq.reply}</p>
                    </div>
                  )}

                  <p className="text-xs text-gray-400 mt-2">
                    Sent: {new Date(inq.createdAt).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <MessageSquare className="w-10 h-10 mx-auto text-gray-200 mb-2" />
              <p>No inquiries yet.</p>
              <p className="text-sm">When you ask questions or request visits, they'll appear here.</p>
            </div>
          )}

        </div>
      </Modal>

      {/* Payment Modes Modal */}
      <Modal
        isOpen={isPaymentModesOpen}
        onClose={() => setIsPaymentModesOpen(false)}
        title="Payment Modes"
      >
        <div className="py-2">
          {isLoadingPaymentModes ? (
            <div className="text-center py-8">Loading payment info...</div>
          ) : paymentModes ? (
            <div className="space-y-6">
              {/* Supported Methods */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Supported Payment Methods</h4>
                <div className="grid grid-cols-3 gap-3">
                  {paymentModes.supported_methods.map(method => (
                    <div key={method} className="flex flex-col items-center p-3 bg-gray-50 rounded-lg border border-gray-100">
                      <CreditCard className={`w-6 h-6 mb-1 ${method === 'UPI' ? 'text-green-600' : method === 'CARD' ? 'text-blue-600' : 'text-purple-600'}`} />
                      <span className="text-xs font-medium text-gray-700">{method.replace('_', ' ')}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Last Used */}
              {paymentModes.last_used ? (
                <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-100">
                  <h4 className="text-sm font-semibold text-indigo-700 mb-2">Last Used Payment</h4>
                  <p className="text-sm text-gray-700">
                    <span className="font-medium">{paymentModes.last_used.method}</span> via {paymentModes.last_used.gateway}
                  </p>
                  {paymentModes.last_used.reference && (
                    <p className="text-xs text-gray-500 mt-1">{paymentModes.last_used.reference}</p>
                  )}
                  <p className="text-xs text-indigo-500 mt-2">
                    Last used on {new Date(paymentModes.last_used.date).toLocaleDateString()}
                  </p>
                </div>
              ) : (
                <div className="text-center py-4 text-gray-500 text-sm">
                  No payment history yet
                </div>
              )}

              <div className="text-xs text-gray-400 text-center">
                Note: StudySpace does not store card details. Payments are processed securely via Razorpay.
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <CreditCard className="w-10 h-10 mx-auto text-gray-200 mb-2" />
              <p>Unable to load payment information</p>
            </div>
          )}

        </div>
      </Modal>

      {/* My Refunds Modal */}
      <Modal
        isOpen={isRefundsOpen}
        onClose={() => setIsRefundsOpen(false)}
        title="My Refunds"
      >
        <div className="max-h-[60vh] overflow-y-auto custom-scrollbar -mx-4 px-4">
          {isLoadingRefunds ? (
            <div className="text-center py-8">Loading refunds...</div>
          ) : myRefunds.length > 0 ? (
            <div className="space-y-4 py-2">
              {myRefunds.map(refund => {
                const statusColors: Record<string, string> = {
                  REQUESTED: 'bg-yellow-100 text-yellow-700',
                  UNDER_REVIEW: 'bg-blue-100 text-blue-700',
                  APPROVED: 'bg-green-100 text-green-700',
                  REJECTED: 'bg-red-100 text-red-700',
                  PROCESSED: 'bg-emerald-100 text-emerald-700',
                  FAILED: 'bg-red-100 text-red-700'
                };
                const statusIcons: Record<string, React.ReactNode> = {
                  REQUESTED: <Clock className="w-3 h-3" />,
                  UNDER_REVIEW: <Clock className="w-3 h-3" />,
                  APPROVED: <CheckCircle className="w-3 h-3" />,
                  REJECTED: <AlertCircle className="w-3 h-3" />,
                  PROCESSED: <CheckCircle className="w-3 h-3" />,
                  FAILED: <AlertCircle className="w-3 h-3" />
                };
                const statusMessages: Record<string, string> = {
                  REQUESTED: 'Your refund request is being processed.',
                  UNDER_REVIEW: 'Your refund request is under review by StudySpace.',
                  APPROVED: 'Refund approved! Processing payment...',
                  REJECTED: 'Refund request was rejected.',
                  PROCESSED: `₹${refund.amount} refunded to your original payment method.`,
                  FAILED: 'Refund failed. Please contact support.'
                };

                return (
                  <div key={refund.id} className="border border-gray-100 rounded-lg p-4 bg-gray-50">
                    <div className="flex justify-between items-start mb-2">
                      <h4 className="font-bold text-gray-900 text-sm">{refund.venue_name}</h4>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1 ${statusColors[refund.status] || 'bg-gray-100 text-gray-700'}`}>
                        {statusIcons[refund.status]}
                        {refund.status.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="text-lg font-bold text-indigo-600 mb-1">₹{refund.amount.toLocaleString()}</p>
                    <p className="text-sm text-gray-600 mb-2">{statusMessages[refund.status]}</p>
                    {refund.reason_text && (
                      <p className="text-xs text-gray-500 italic mb-2">Reason: {refund.reason_text}</p>
                    )}
                    <p className="text-xs text-gray-400">
                      Requested: {new Date(refund.requested_at).toLocaleDateString()}
                      {refund.processed_at && ` • Processed: ${new Date(refund.processed_at).toLocaleDateString()}`}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <RotateCcw className="w-10 h-10 mx-auto text-gray-200 mb-2" />
              <p>No refund requests yet.</p>
              <p className="text-sm mt-1">Refunds can be requested from your booking details.</p>
            </div>
          )}

        </div>
      </Modal>

    </div>
  );
};