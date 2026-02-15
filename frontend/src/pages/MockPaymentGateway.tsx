import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CreditCard, Smartphone, Wallet, Check, X, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';

/**
 * Mock Payment Gateway - Simulates Razorpay payment experience
 * Used in demo mode to test complete payment flow
 */
const MockPaymentGateway: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const [selectedMethod, setSelectedMethod] = useState<'upi' | 'card' | 'wallet' | ''>('');
  const [processing, setProcessing] = useState(false);
  const [upiId, setUpiId] = useState('');
  const [cardNumber, setCardNumber] = useState('');
  const [cardExpiry, setCardExpiry] = useState('');
  const [cardCvv, setCardCvv] = useState('');
  
  // Payment details from URL params
  const amount = searchParams.get('amount') || '0';
  const orderId = searchParams.get('order_id') || '';
  const description = searchParams.get('description') || 'Payment';
  const merchantName = searchParams.get('merchant') || 'StudySpace';
  const callbackUrl = searchParams.get('callback') || '/';

  useEffect(() => {
    // Show toast that we're in demo mode
    toast('🎭 Demo Payment Mode - Test the payment flow!', {
      duration: 3000,
      icon: '💳'
    });
  }, []);

  const handlePayment = async (method: string) => {
    setProcessing(true);
    
    // Simulate payment processing delay
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Generate mock payment data
    const paymentData = {
      razorpay_order_id: orderId,
      razorpay_payment_id: `pay_demo_${Date.now()}_${method}`,
      razorpay_signature: `sig_demo_${Date.now()}`,
      status: 'success'
    };
    
    // Show success animation
    toast.success(`✅ Demo Payment Successful via ${method.toUpperCase()}!`);
    
    // Wait a bit to show success
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Redirect back with payment data
    const params = new URLSearchParams(paymentData);
    if (callbackUrl.includes('?')) {
      window.location.href = `${callbackUrl}&${params.toString()}`;
    } else {
      window.location.href = `${callbackUrl}?${params.toString()}`;
    }
  };

  const handleCancel = () => {
    toast.error('Payment cancelled');
    setTimeout(() => {
      navigate(-1); // Go back
    }, 500);
  };

  const formatAmount = (amount: string) => {
    const amountInRupees = parseFloat(amount) / 100;
    return `₹${amountInRupees.toFixed(2)}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-t-xl shadow-lg p-6 border-b-2 border-purple-200">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">{merchantName}</h1>
              <p className="text-gray-600 text-sm mt-1">{description}</p>
            </div>
            <div className="bg-purple-100 px-4 py-2 rounded-lg">
              <span className="text-xs text-purple-600 font-semibold">DEMO MODE</span>
            </div>
          </div>
          
          <div className="bg-gradient-to-r from-purple-500 to-blue-500 text-white p-4 rounded-lg">
            <p className="text-sm opacity-90">Amount to Pay</p>
            <p className="text-3xl font-bold mt-1">{formatAmount(amount)}</p>
          </div>
        </div>

        {/* Payment Methods */}
        <div className="bg-white shadow-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Select Payment Method</h2>
          
          {/* UPI */}
          <div 
            className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
              selectedMethod === 'upi' 
                ? 'border-purple-500 bg-purple-50' 
                : 'border-gray-200 hover:border-purple-300'
            }`}
            onClick={() => setSelectedMethod('upi')}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${selectedMethod === 'upi' ? 'bg-purple-500' : 'bg-gray-100'}`}>
                <Smartphone className={`w-6 h-6 ${selectedMethod === 'upi' ? 'text-white' : 'text-gray-600'}`} />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800">UPI / Google Pay</h3>
                <p className="text-sm text-gray-500">Pay with any UPI app</p>
              </div>
              {selectedMethod === 'upi' && <Check className="w-5 h-5 text-purple-500" />}
            </div>
            
            {selectedMethod === 'upi' && (
              <div className="mt-4 space-y-3">
                <input
                  type="text"
                  placeholder="Enter UPI ID (e.g., test@paytm)"
                  value={upiId}
                  onChange={(e) => setUpiId(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => handlePayment('googlepay')}
                    disabled={processing}
                    className="flex-1 bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                  >
                    <div className="flex items-center justify-center gap-2">
                      <span className="text-xl">G</span> Google Pay
                    </div>
                  </button>
                  <button
                    onClick={() => handlePayment('phonepe')}
                    disabled={processing}
                    className="flex-1 bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                  >
                    <div className="flex items-center justify-center gap-2">
                      <span className="text-xl">📱</span> PhonePe
                    </div>
                  </button>
                  <button
                    onClick={() => handlePayment('paytm')}
                    disabled={processing}
                    className="flex-1 bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                  >
                    <div className="flex items-center justify-center gap-2">
                      <span className="text-xl">💰</span> Paytm
                    </div>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Cards */}
          <div 
            className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
              selectedMethod === 'card' 
                ? 'border-purple-500 bg-purple-50' 
                : 'border-gray-200 hover:border-purple-300'
            }`}
            onClick={() => setSelectedMethod('card')}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${selectedMethod === 'card' ? 'bg-purple-500' : 'bg-gray-100'}`}>
                <CreditCard className={`w-6 h-6 ${selectedMethod === 'card' ? 'text-white' : 'text-gray-600'}`} />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800">Credit / Debit Card</h3>
                <p className="text-sm text-gray-500">Visa, Mastercard, Rupay</p>
              </div>
              {selectedMethod === 'card' && <Check className="w-5 h-5 text-purple-500" />}
            </div>
            
            {selectedMethod === 'card' && (
              <div className="mt-4 space-y-3">
                <input
                  type="text"
                  placeholder="Card Number (e.g., 4111 1111 1111 1111)"
                  value={cardNumber}
                  onChange={(e) => setCardNumber(e.target.value)}
                  maxLength={19}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                />
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="MM/YY"
                    value={cardExpiry}
                    onChange={(e) => setCardExpiry(e.target.value)}
                    maxLength={5}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  <input
                    type="text"
                    placeholder="CVV"
                    value={cardCvv}
                    onChange={(e) => setCardCvv(e.target.value)}
                    maxLength={3}
                    className="w-24 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                </div>
                <button
                  onClick={() => handlePayment('card')}
                  disabled={processing}
                  className="w-full bg-gradient-to-r from-purple-500 to-blue-500 text-white px-6 py-3 rounded-lg font-semibold hover:from-purple-600 hover:to-blue-600 transition-all disabled:opacity-50"
                >
                  {processing ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Processing...
                    </span>
                  ) : (
                    `Pay ${formatAmount(amount)}`
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Wallets */}
          <div 
            className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
              selectedMethod === 'wallet' 
                ? 'border-purple-500 bg-purple-50' 
                : 'border-gray-200 hover:border-purple-300'
            }`}
            onClick={() => setSelectedMethod('wallet')}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${selectedMethod === 'wallet' ? 'bg-purple-500' : 'bg-gray-100'}`}>
                <Wallet className={`w-6 h-6 ${selectedMethod === 'wallet' ? 'text-white' : 'text-gray-600'}`} />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-800">Wallets</h3>
                <p className="text-sm text-gray-500">PayTM, PhonePe, Amazon Pay</p>
              </div>
              {selectedMethod === 'wallet' && <Check className="w-5 h-5 text-purple-500" />}
            </div>
            
            {selectedMethod === 'wallet' && (
              <div className="mt-4 grid grid-cols-2 gap-3">
                <button
                  onClick={() => handlePayment('paytm_wallet')}
                  disabled={processing}
                  className="bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                >
                  PayTM Wallet
                </button>
                <button
                  onClick={() => handlePayment('phonepe_wallet')}
                  disabled={processing}
                  className="bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                >
                  PhonePe Wallet
                </button>
                <button
                  onClick={() => handlePayment('amazonpay')}
                  disabled={processing}
                  className="bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                >
                  Amazon Pay
                </button>
                <button
                  onClick={() => handlePayment('mobikwik')}
                  disabled={processing}
                  className="bg-white border-2 border-gray-300 text-gray-700 px-4 py-3 rounded-lg font-semibold hover:border-purple-500 transition-colors disabled:opacity-50"
                >
                  MobiKwik
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="bg-white rounded-b-xl shadow-lg p-6 border-t border-gray-200">
          <div className="flex items-center justify-between">
            <button
              onClick={handleCancel}
              disabled={processing}
              className="flex items-center gap-2 text-gray-600 hover:text-red-600 transition-colors disabled:opacity-50"
            >
              <X className="w-5 h-5" />
              Cancel Payment
            </button>
            
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              Secure Payment
            </div>
          </div>
          
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-xs text-yellow-800">
              🎭 <strong>Demo Mode:</strong> This is a simulated payment gateway. No real money will be charged. 
              Click any payment method to test the flow!
            </p>
          </div>
        </div>
        
        {processing && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-8 text-center">
              <Loader2 className="w-16 h-16 text-purple-500 animate-spin mx-auto mb-4" />
              <p className="text-lg font-semibold text-gray-800">Processing Payment...</p>
              <p className="text-sm text-gray-500 mt-2">Please wait</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MockPaymentGateway;
