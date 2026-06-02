import React, { useState } from 'react';
import { CreditCard, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';

interface RazorpayPaymentProps {
  bookingId: string;
  amount: number;
  onSuccess: () => void;
  onFailure?: () => void;
}

declare global {
  interface Window {
    Razorpay: any;
  }
}

// Use the shared `api` axios instance (baseURL + auth interceptor) instead
// of the prior raw `axios` calls keyed off `import.meta.env.VITE_API_BASE_URL
// || 'http://localhost:8000'`. That fallback shipped "http://localhost:8000"
// into the prod bundle when the env var wasn't set at build time, breaking
// every Razorpay order creation with ERR_CONNECTION_REFUSED.

export const RazorpayPayment: React.FC<RazorpayPaymentProps> = ({ 
  bookingId, 
  amount, 
  onSuccess, 
  onFailure 
}) => {
  const [loading, setLoading] = useState(false);

  const loadRazorpayScript = (): Promise<boolean> => {
    return new Promise((resolve) => {
      // Check if script already loaded
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

  const handlePayment = async () => {
    setLoading(true);

    try {
      // Load Razorpay script
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded) {
        toast.error('Failed to load payment gateway. Please check your internet connection.');
        setLoading(false);
        return;
      }

      // Create order. NOTE: backend mounts the razorpay router at root
      // ("/razorpay/*"), NOT under "/api". Probed both in prod:
      //   /razorpay/verify       → 401 (proxied to backend) ✓
      //   /api/razorpay/verify   → 405 (route doesn't exist) ✗
      // So this path stays at /razorpay/* even though our `api` axios
      // instance is the same shared instance used by /api/* calls.
      const orderResponse = await api.post(
        `/razorpay/create-order`,
        {
          booking_id: bookingId,
          amount: amount,
        },
      );

      const { order_id, amount: orderAmount, currency, razorpay_key_id } = orderResponse.data;

      // Get user info
      const userName = localStorage.getItem('user_name') || '';
      const userEmail = localStorage.getItem('user_email') || '';

      // Razorpay options
      const options = {
        key: razorpay_key_id,
        amount: orderAmount,
        currency: currency,
        name: 'mySpace',
        description: 'Booking Payment',
        image: '/logo.png', // Optional: Add your logo
        order_id: order_id,
        handler: async (response: any) => {
          try {
            // Verify payment. Same root-mounted path as create-order above.
            await api.post(
              `/razorpay/verify`,
              {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                booking_id: bookingId,
              },
            );

            toast.success('Payment successful! 🎉');
            setLoading(false);
            onSuccess();
          } catch (error: any) {
            console.error('Payment verification error:', error);
            toast.error(error.response?.data?.detail || 'Payment verification failed');
            setLoading(false);
            onFailure?.();
          }
        },
        prefill: {
          name: userName,
          email: userEmail,
        },
        theme: {
          color: '#4F46E5'
        },
        method: {
          upi: true,      // Enable UPI (GPay, PhonePe, PayTM)
          card: true,     // Enable Cards
          netbanking: true, // Enable Net Banking
          wallet: true    // Enable Wallets
        },
        modal: {
          ondismiss: () => {
            toast.error('Payment cancelled');
            setLoading(false);
            onFailure?.();
          }
        }
      };

      const razorpay = new window.Razorpay(options);
      razorpay.open();

    } catch (error: any) {
      console.error('Payment error:', error);
      toast.error(error.response?.data?.detail || 'Failed to initiate payment');
      setLoading(false);
      onFailure?.();
    }
  };

  return (
    <button
      onClick={handlePayment}
      disabled={loading}
      className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3 rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl font-semibold"
    >
      {loading ? (
        <>
          <Loader2 className="w-5 h-5 animate-spin" />
          Processing...
        </>
      ) : (
        <>
          <CreditCard className="w-5 h-5" />
          Pay ₹{amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </>
      )}
    </button>
  );
};
