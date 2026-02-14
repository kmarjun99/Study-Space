import React, { useState } from 'react';
import { CreditCard, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import axios from 'axios';

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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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

  const getAuthToken = (): string => {
    return localStorage.getItem('token') || '';
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

      // Create order
      const orderResponse = await axios.post(
        `${API_BASE_URL}/payments/create-order`,
        {
          booking_id: bookingId,
          amount: amount
        },
        {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
            'Content-Type': 'application/json'
          }
        }
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
        name: 'SSPACE',
        description: 'Booking Payment',
        image: '/logo.png', // Optional: Add your logo
        order_id: order_id,
        handler: async (response: any) => {
          try {
            // Verify payment
            await axios.post(
              `${API_BASE_URL}/payments/verify`,
              {
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
                booking_id: bookingId
              },
              {
                headers: {
                  'Authorization': `Bearer ${getAuthToken()}`,
                  'Content-Type': 'application/json'
                }
              }
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
