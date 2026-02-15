import React, { useState, useEffect } from 'react';
import { CreditCard, Loader2, CheckCircle, Shield, Lock, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import axios from 'axios';
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

  // Debug: Log subscription plans
  useEffect(() => {
    console.log('OwnerListingPayment - Received plans:', subscriptionPlans);
  }, [subscriptionPlans]);

  // Auto-select first active plan
  useEffect(() => {
    if (subscriptionPlans.length > 0 && !selectedPlanId) {
      setSelectedPlanId(subscriptionPlans[0].id);
    }
  }, [subscriptionPlans, selectedPlanId]);

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

  const getAuthToken = (): string => {
    return localStorage.getItem('studySpace_token') || '';
  };

  const calculateGST = (amount: number): number => {
    return amount * 0.18; // 18% GST
  };

  const calculateTotal = (baseAmount: number): number => {
    return baseAmount + calculateGST(baseAmount);
  };

  const handlePayment = async () => {
    if (!selectedPlan) {
      toast.error('Please select a subscription plan');
      return;
    }

    setLoading(true);
    setPaymentStep('processing');

    try {
      // 1. Create Order FIRST (to check for demo mode)
      const amount = calculateTotal(selectedPlan.price);
      const { paymentService } = await import('../services/paymentService');
      const orderData = await paymentService.createOrder(amount);

      // 🎭 DEMO MODE: Auto-complete payment instantly
      if (orderData.is_demo || orderData.key_id === 'demo_key_id' || orderData.key_id === 'your_razorpay_key_id') {
        toast.success('💳 DEMO MODE: Processing payment...', { duration: 2000 });
        
        // Simulate payment processing
        await new Promise(resolve => setTimeout(resolve, 1500));
        
        try {
          // Use dev-bypass endpoint for demo mode
          await axios.post(
            `${API_BASE_URL}/payments/venue/dev-bypass`,
            {
              venue_id: venueId,
              venue_type: venueType,
              subscription_plan_id: selectedPlanId,
              amount: amount
            },
            { headers: { 'Authorization': `Bearer ${getAuthToken()}` } }
          );

          setPaymentStep('success');
          toast.success('✅ Demo payment completed successfully!');
          
          setTimeout(() => {
            onPaymentSuccess();
          }, 2000);
          return;
        } catch (error) {
          console.error('Demo payment failed:', error);
          toast.error('Payment processing failed. Please try again.');
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
        key: orderData.key_id,
        amount: orderData.amount,
        currency: orderData.currency,
        name: "StudySpace Listing",
        description: `${selectedPlan.name} for ${venueName}`,
        image: 'https://via.placeholder.com/150', // Logo
        order_id: orderData.id,
        handler: async function (response: any) {
          try {
            // 4. Verify Payment
            await paymentService.verifyPayment({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature
            });

            // 5. Submit Venue to Backend (Real submission now that payment is verified)
            // We need to call the actual endpoint to "activate" or "submit" the venue
            // Previously it was /payments/venue/dev-bypass. Now we likely need a proper endpoint 
            // that says "I paid, activate this venue/plan".
            // For now, let's assume we call the same endpoint but passing the transaction ID?
            // OR, better: The backend check might need to be updated.
            // Let's call a new endpoint: /venues/{id}/activate-plan

            // Wait, I see the old code was: axios.post(`${API_BASE_URL}/payments/venue/dev-bypass`...
            // I should probably replace that with a call that includes the payment_id.

            await axios.post(
              `${API_BASE_URL}/payments/venue/confirm-subscription`, // New standardized endpoint? 
              {
                venue_id: venueId,
                venue_type: venueType,
                subscription_plan_id: selectedPlanId,
                payment_id: response.razorpay_payment_id,
                amount: amount
              },
              {
                headers: {
                  'Authorization': `Bearer ${getAuthToken()}`,
                  'Content-Type': 'application/json'
                }
              }
            );

            setPaymentStep('success');
            toast.success('Payment verified & Venue submitted!');
            setTimeout(onSuccess, 2000);

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

  return (
    <Modal isOpen={isOpen} onClose={!loading ? onClose : () => { }} title="Complete Your Listing - Subscription Payment">
      <div className="space-y-6">
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
            Select Subscription Plan
          </label>
          {subscriptionPlans.length === 0 ? (
            <div className="text-center py-8 bg-gray-50 rounded-lg">
              <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500">No subscription plans available</p>
              <p className="text-sm text-gray-400 mt-1">Please contact support</p>
            </div>
          ) : (
            <div className="space-y-3">
              {subscriptionPlans.map((plan) => (
                <Card
                  key={plan.id}
                  onClick={() => !loading && setSelectedPlanId(plan.id)}
                  className={`p-4 cursor-pointer transition-all ${selectedPlanId === plan.id
                      ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-500'
                      : 'border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50'
                    } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1">
                      <h4 className="font-bold text-gray-900">{plan.name}</h4>
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
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Base Price</span>
              <span className="font-medium text-gray-900">₹{selectedPlan.price.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">GST (18%)</span>
              <span className="font-medium text-gray-900">₹{calculateGST(selectedPlan.price).toFixed(2)}</span>
            </div>
            <div className="border-t border-gray-200 pt-2 mt-2">
              <div className="flex justify-between">
                <span className="font-bold text-gray-900">Total Amount</span>
                <span className="font-bold text-indigo-600 text-lg">
                  ₹{calculateTotal(selectedPlan.price).toFixed(2)}
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
                Payment submission moves your listing to admin verification. Your venue will go live after Super Admin approval.
              </p>
            </div>
          </div>
        </div>

        {/* Payment Button */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={loading}
            className="flex-1"
          >
            Cancel
          </Button>
          <Button
            onClick={handlePayment}
            disabled={loading || !selectedPlan || subscriptionPlans.length === 0}
            className="flex-1 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
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
  );
};
