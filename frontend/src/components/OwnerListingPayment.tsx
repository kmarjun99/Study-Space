import React, { useState, useEffect } from 'react';
import { CreditCard, Loader2, CheckCircle, Shield, Lock, AlertCircle, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';
import { Modal, Button, Card } from './UI';

interface OwnerListingPaymentProps {
  isOpen: boolean;
  onClose: () => void;
  venueId: string;
  venueName: string;
  venueType: 'reading_room' | 'accommodation';
  subscriptionPlans: Array<{
    id: string;
    name: string;
    description?: string;
    price: number;
    durationDays?: number;
    features?: string[];
  }>;
  onSuccess: () => void;
}

declare global {
  interface Window {
    Razorpay: any;
  }
}

// API requests go through the shared `api` axios instance — its baseURL
// is empty in production so paths like `/api/...` become relative URLs
// nginx proxies to the backend. The prior raw-axios + env-var pattern
// shipped "http://localhost:8000" into the prod bundle when
// VITE_API_BASE_URL was unset at build time.

export const OwnerListingPayment: React.FC<OwnerListingPaymentProps> = ({
  isOpen,
  onClose,
  venueId,
  venueName,
  venueType,
  subscriptionPlans,
  onSuccess
}) => {
  const [loading, setLoading] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [paymentStep, setPaymentStep] = useState<'plan-selection' | 'processing' | 'success'>('plan-selection');
  
  // 🆕 Upgrade Logic States
  const [currentPlan, setCurrentPlan] = useState<typeof subscriptionPlans[0] | null>(null);
  const [showAlreadyPaidPopup, setShowAlreadyPaidPopup] = useState(false);
  const [isUpgrade, setIsUpgrade] = useState(false);
  const [checkingPlan, setCheckingPlan] = useState(false);

  // 🆕 Check for existing subscription on mount
  useEffect(() => {
    if (isOpen) {
      checkExistingPlan();
    }
  }, [isOpen, venueId]);

  // Auto-select first available plan (upgrade or new)
  useEffect(() => {
    if (subscriptionPlans.length > 0 && !selectedPlanId && !checkingPlan) {
      const availablePlans = getAvailableUpgrades();
      if (availablePlans.length > 0) {
        setSelectedPlanId(availablePlans[0].id);
      } else if (!currentPlan) {
        // No current plan, select first plan
        setSelectedPlanId(subscriptionPlans[0].id);
      } else {
        // Current plan exists but no upgrades - clear selection
        setSelectedPlanId('');
      }
    }
  }, [subscriptionPlans, selectedPlanId, currentPlan, checkingPlan]);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      // Reset all states when modal closes
      setLoading(false);
      setPaymentStep('plan-selection');
      setShowAlreadyPaidPopup(false);
      setIsUpgrade(false);
      setCheckingPlan(false);
      setCurrentPlan(null);
      setSelectedPlanId('');
    }
  }, [isOpen]);

  // 🆕 Check if venue already has an active subscription
  const checkExistingPlan = async () => {
    setCheckingPlan(true);
    try {
      const endpoint = venueType === 'reading_room'
        ? `/api/reading-rooms/${venueId}`
        : `/api/accommodations/${venueId}`;

      const response = await api.get(endpoint);
      const venue = response.data;
      
      // Check if venue has an active subscription
      if (venue.subscription_plan_id) {
        const activePlan = subscriptionPlans.find(p => p.id === venue.subscription_plan_id);
        if (activePlan) {
          setCurrentPlan(activePlan);
        }
      }
    } catch (error) {
      console.error('Error checking existing plan:', error);
      // Continue even if check fails
    } finally {
      setCheckingPlan(false);
    }
  };

  // 🆕 Get only higher-priced plans for upgrades
  const getAvailableUpgrades = (): typeof subscriptionPlans => {
    if (!currentPlan) {
      return subscriptionPlans; // All plans available if no current plan
    }
    return subscriptionPlans.filter(plan => plan.price > currentPlan.price);
  };

  // 🆕 Handle plan selection with upgrade logic
  const handlePlanSelection = (planId: string) => {
    if (loading) return;

    const selectedPlanObj = subscriptionPlans.find(p => p.id === planId);
    
    // If user already has a plan
    if (currentPlan && selectedPlanObj) {
      if (selectedPlanObj.price <= currentPlan.price) {
        // Same or lower plan - show popup
        setShowAlreadyPaidPopup(true);
        return;
      } else {
        // Higher plan - allow upgrade
        setIsUpgrade(true);
      }
    }

    setSelectedPlanId(planId);
  };

  const selectedPlan = subscriptionPlans.find(p => p.id === selectedPlanId);

  const loadRazorpayScript = (): Promise<boolean> => {
    return new Promise((resolve) => {
      if (window.Razorpay) {
        resolve(true);
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  };

  const calculateGST = (amount: number): number => {
    return amount * 0.18; // 18% GST
  };

  const calculateTotal = (baseAmount: number): number => {
    return baseAmount + calculateGST(baseAmount);
  };

  // 🆕 Calculate upgrade price difference
  const getUpgradePrice = (): number => {
    if (!isUpgrade || !currentPlan || !selectedPlan) {
      return selectedPlan?.price || 0;
    }
    // Charge only the difference for upgrades
    return Math.max(0, selectedPlan.price - currentPlan.price);
  };

  const handlePayment = async () => {
    if (!selectedPlan) {
      toast.error('Please select a subscription plan');
      return;
    }

    setLoading(true);
    setPaymentStep('processing');

    try {
      // 🆕 Use upgrade price if applicable
      const basePrice = getUpgradePrice();
      const amount = calculateTotal(basePrice);
      
      const { paymentService } = await import('../services/paymentService');
      const orderData = await paymentService.createVenueOrder({
        venue_id: venueId,
        venue_type: venueType,
        subscription_plan_id: selectedPlanId,
        amount: amount
      });

      // 🎭 DEMO MODE: Auto-complete payment instantly
      if (orderData.is_demo || orderData.razorpay_key_id === 'demo_key_id' || orderData.razorpay_key_id === 'your_razorpay_key_id') {
        toast.success(isUpgrade ? '💳 DEMO MODE: Processing upgrade...' : '💳 DEMO MODE: Processing payment...', { duration: 2000 });
        
        // Simulate payment processing
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        try {
          // Use dev-bypass endpoint for demo mode. Backend mounts payments
          // router at root only (no /api prefix); the wrong `/api/payments/*`
          // path returns 404 on the live backend.
          await api.post(
            `/payments/venue/dev-bypass`,
            {
              venue_id: venueId,
              venue_type: venueType,
              subscription_plan_id: selectedPlanId,
              amount: amount,
            },
          );

          toast.success(isUpgrade ? '✅ Upgrade completed successfully!' : '✅ Demo payment completed successfully!');
          
          // Reset states before calling onSuccess
          setLoading(false);
          setPaymentStep('plan-selection');
          
          // Call onSuccess to trigger parent navigation
          onSuccess();
          return;
        } catch (error: any) {
          console.error('[DEMO PAYMENT] Failed with error:', error);
          console.error('[DEMO PAYMENT] Error response:', error.response?.data);
          console.error('[DEMO PAYMENT] Error status:', error.response?.status);
          
          const errorMsg = error.response?.data?.detail || 'Payment processing failed. Please try again.';
          toast.error(errorMsg);
          setLoading(false);
          setPaymentStep('plan-selection');
          return;
        }
      }

      // 2. REAL PAYMENT MODE: Load Razorpay Script
      const isLoaded = await loadRazorpayScript();
      if (!isLoaded) {
        toast.error('Razorpay SDK failed to load');
        setLoading(false);
        setPaymentStep('plan-selection');
        return;
      }

      // 3. Initialize Razorpay Options
      const options = {
        key: orderData.razorpay_key_id,
        amount: orderData.amount,
        currency: orderData.currency,
        name: "mySpace Listing",
        description: isUpgrade 
          ? `Upgrade to ${selectedPlan.name} for ${venueName}`
          : `${selectedPlan.name} for ${venueName}`,
        image: 'https://via.placeholder.com/150', // Logo
        order_id: orderData.order_id,
        handler: async function (response: any) {
          try {
            // 4. Verify Payment
            await paymentService.verifyVenuePayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
              venue_id: venueId,
              venue_type: venueType,
              subscription_plan_id: selectedPlanId
            });

            toast.success(isUpgrade ? 'Upgrade verified & submitted!' : 'Payment verified & Venue submitted!');
            // Call onSuccess immediately without showing intermediate success modal
            onSuccess();

          } catch (err: any) {
            console.error("Verification/Submission error:", err);
            toast.error("Payment verification failed. Contact support.");
            setPaymentStep('plan-selection'); // Or error state
          }
        },
        prefill: {
          // We can try to get user details if available, else standard
          contact: ''
        },
        theme: { color: '#4F46E5' },
        modal: {
          ondismiss: function () {
            setLoading(false);
            setPaymentStep('plan-selection');
          }
        }
      };

      const rzp = new (window as any).Razorpay(options);
      rzp.on('payment.failed', function (response: any) {
        toast.error(`Payment Failed: ${response.error.description}`);
        setLoading(false);
        setPaymentStep('plan-selection');
      });
      rzp.open();

    } catch (error: any) {
      console.error('Payment Flow Error:', error);
      toast.error('Could not initiate payment. Try again.');
      setLoading(false);
      setPaymentStep('plan-selection');
    }
  };

  if (paymentStep === 'success') {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Payment Successful">
        <div className="text-center py-8">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">Payment Successful!</h3>
          <p className="text-gray-600 mb-4">
            Your listing has been submitted for admin verification.
          </p>
          <p className="text-sm text-gray-500">
            You'll be notified once your venue is approved and live.
          </p>
        </div>
      </Modal>
    );
  }

  // 🆕 Already Paid Popup
  const availableUpgrades = getAvailableUpgrades();
  const hasUpgradesAvailable = currentPlan && availableUpgrades.length > 0;

  return (
    <>
      {/* 🆕 Already Paid Popup */}
      <Modal 
        isOpen={showAlreadyPaidPopup} 
        onClose={() => setShowAlreadyPaidPopup(false)} 
        title="Already Paid!"
      >
        <div className="text-center py-6">
          <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">You've Already Paid!</h3>
          <p className="text-gray-600 mb-4">
            You're currently on the <span className="font-semibold text-indigo-600">{currentPlan?.name}</span> plan.
          </p>
          {hasUpgradesAvailable ? (
            <>
              <p className="text-sm text-gray-500 mb-6">
                You can only upgrade to a higher-tier plan. Select an upgrade option to enhance your listing!
              </p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowAlreadyPaidPopup(false)}
                  className="flex-1"
                >
                  View Upgrades
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-500 mb-6">
                You're already on the highest plan available. No upgrades needed!
              </p>
              <Button
                onClick={() => {
                  setShowAlreadyPaidPopup(false);
                  onClose();
                }}
                className="w-full"
              >
                Got it!
              </Button>
            </>
          )}
        </div>
      </Modal>

      {/* Main Payment Modal */}
      <Modal isOpen={isOpen} onClose={!loading ? onClose : () => { }} title={
        currentPlan 
          ? `Upgrade Your Plan - ${venueName}`
          : `Complete Your Listing - Subscription Payment`
      }>
        <div className="space-y-6">
          {/* 🆕 Current Plan Badge */}
          {currentPlan && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-indigo-600 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-indigo-900">Current Plan: {currentPlan.name}</p>
                  <p className="text-xs text-indigo-700 mt-1">
                    ₹{currentPlan.price} • {currentPlan.durationDays} days
                  </p>
                </div>
                {hasUpgradesAvailable && (
                  <div className="flex items-center gap-1 text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded">
                    <TrendingUp className="w-3 h-3" />
                    Upgrades Available
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Security Badge */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-green-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-green-900">Secure Payment via Razorpay</p>
                <p className="text-xs text-green-700 mt-1">
                  Your payment information is encrypted and secure. We don't store card details.
                </p>
              </div>
            </div>
          </div>

        {/* Venue Info */}
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-semibold text-gray-900 mb-1">{venueName}</h4>
          <p className="text-sm text-gray-600">
            {venueType === 'reading_room' ? 'Reading Room' : 'PG/Hostel'}
          </p>
        </div>

        {/* Plan Selection */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            {currentPlan ? 'Select Upgrade Plan' : 'Select Subscription Plan'}
          </label>
          
          {/* 🆕 No upgrades available message */}
          {currentPlan && !hasUpgradesAvailable ? (
            <div className="text-center py-8 bg-gradient-to-br from-green-50 to-indigo-50 rounded-lg border border-green-200">
              <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <p className="text-gray-700 font-medium">You're on the Highest Plan!</p>
              <p className="text-sm text-gray-500 mt-1">No upgrades available at this time.</p>
            </div>
          ) : subscriptionPlans.length === 0 ? (
            <div className="text-center py-8 bg-gray-50 rounded-lg">
              <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No subscription plans available</p>
              <p className="text-sm text-gray-400 mt-1">Please contact support</p>
            </div>
          ) : (
            <div className="space-y-3">
              {/* 🆕 Show only available plans (upgrades if current plan exists) */}
              {availableUpgrades.map((plan) => (
                <Card
                  key={plan.id}
                  onClick={() => handlePlanSelection(plan.id)}
                  className={`p-4 cursor-pointer transition-all ${selectedPlanId === plan.id
                      ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500'
                      : 'border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50'
                    } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h4 className="font-bold text-gray-900">{plan.name}</h4>
                        {currentPlan && plan.price > currentPlan.price && (
                          <span className="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded">
                            UPGRADE
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{plan.description}</p>
                    </div>
                    <div className="text-right ml-4">
                      <div className="text-2xl font-bold text-indigo-600">₹{plan.price}</div>
                      {plan.durationDays && (
                        <div className="text-xs text-gray-500">{plan.durationDays} days</div>
                      )}
                    </div>
                  </div>
                  {plan.features && plan.features.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {plan.features.map((feature, idx) => (
                        <li key={idx} className="text-sm text-gray-600 flex items-start gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500 mt-0.5 flex-shrink-0" />
                          <span>{feature}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Pricing Breakdown */}
        {selectedPlan && (
          <div className="bg-gray-50 rounded-lg p-4 space-y-2">
            <h4 className="font-semibold text-gray-900 mb-3">Payment Summary</h4>
            
            {/* 🆕 Show upgrade pricing breakdown */}
            {isUpgrade && currentPlan ? (
              <>
                <div className="flex justify-between text-sm text-gray-500">
                  <span>Current Plan ({currentPlan.name})</span>
                  <span>₹{currentPlan.price.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">New Plan ({selectedPlan.name})</span>
                  <span className="font-medium text-gray-900">₹{selectedPlan.price.toFixed(2)}</span>
                </div>
                <div className="border-t border-gray-300 pt-2 mt-2">
                  <div className="flex justify-between text-sm font-medium text-indigo-600">
                    <span>Upgrade Difference</span>
                    <span>₹{getUpgradePrice().toFixed(2)}</span>
                  </div>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">GST (18%)</span>
                  <span className="font-medium text-gray-900">₹{calculateGST(getUpgradePrice()).toFixed(2)}</span>
                </div>
              </>
            ) : (
              <>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Base Price</span>
                  <span className="font-medium text-gray-900">₹{selectedPlan.price.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">GST (18%)</span>
                  <span className="font-medium text-gray-900">₹{calculateGST(selectedPlan.price).toFixed(2)}</span>
                </div>
              </>
            )}
            
            <div className="border-t border-gray-200 pt-2 mt-2">
              <div className="flex justify-between">
                <span className="font-bold text-gray-900">Total Amount</span>
                <span className="font-bold text-indigo-600 text-lg">
                  ₹{calculateTotal(getUpgradePrice()).toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Important Note */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-yellow-900 mb-1">Important Note</p>
              <p className="text-yellow-800">
                {isUpgrade 
                  ? 'Upgrading your plan will enhance your listing visibility and features. Changes take effect immediately after payment.'
                  : 'Payment submission moves your listing to admin verification. Your venue will go live after Super Admin approval.'
                }
              </p>
            </div>
          </div>
        </div>

        {/* Payment Button */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={loading || checkingPlan}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handlePayment}
            disabled={loading || checkingPlan || !selectedPlan || (currentPlan && !hasUpgradesAvailable)}
            className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {checkingPlan ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Checking Plan...
              </>
            ) : loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (currentPlan && !hasUpgradesAvailable) ? (
              <>
                <Lock className="w-4 h-4 mr-2" />
                Already on Highest Plan
              </>
            ) : isUpgrade ? (
              <>
                <TrendingUp className="w-4 h-4 mr-2" />
                Upgrade for ₹{selectedPlan ? calculateTotal(getUpgradePrice()).toFixed(2) : '0'}
              </>
            ) : (
              <>
                <Lock className="w-4 h-4 mr-2" />
                Pay ₹{selectedPlan ? calculateTotal(selectedPlan.price).toFixed(2) : '0'} Securely
              </>
            )}
          </Button>
        </div>

        {/* Security Footer */}
        <p className="text-xs text-center text-gray-500">
          <Lock className="w-3 h-3 inline mr-1" />
          Secured by Razorpay • PCI DSS Compliant
        </p>
      </div>
    </Modal>
    </>
  );
};
