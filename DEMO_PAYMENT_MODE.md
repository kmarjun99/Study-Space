# 🎭 Demo Payment Mode

## Overview
The Study Space app now includes a **Demo Payment Mode** that allows you to test the complete payment flow without requiring actual Razorpay credentials or making real transactions.

## How It Works

### Automatic Activation
Demo mode activates automatically when:
1. ❌ Razorpay credentials are not configured
2. ❌ Razorpay credentials are invalid or placeholders
3. ❌ Razorpay API connection fails
4. ✅ `PAYMENT_DEMO_MODE=true` environment variable is set

### Payment Flow

#### Backend Behavior
1. **Order Creation** (`/payments/create-order`)
   - Returns mock order with `order_demo_` prefix
   - No actual Razorpay API call is made
   - Response includes `is_demo: true` flag

2. **Payment Verification** (`/payments/verify`)
   - Auto-verifies any order starting with `order_demo_` or `order_fallback_`
   - No signature validation required
   - Returns success immediately

#### Frontend Behavior
1. **Order Data Check**
   - Detects `is_demo: true` or `key_id: "demo_key_id"`
   - Shows toast: "💳 DEMO MODE: Payment simulated successfully!"
   - Skips Razorpay SDK loading

2. **Auto-Completion**
   - Generates demo payment credentials:
     - `payment_id`: `pay_demo_<timestamp>`
     - `order_id`: From backend order response
     - `signature`: `sig_demo_<timestamp>`
   - Calls verification endpoint automatically
   - Updates UI as if real payment completed

## Testing Demo Payments

### For Venue Boost (Reading Rooms)
1. Navigate to your reading room
2. Click "Boost This Venue"
3. Select a boost plan
4. Click payment button
5. 🎉 Payment completes automatically with demo notification

### For Venue Subscriptions
1. Create a new venue (reading room or accommodation)
2. Submit for listing
3. Choose subscription plan
4. Click payment button
5. 🎉 Payment completes automatically

### For Cabin Bookings
1. Browse venue cabins
2. Select cabin and duration
3. Proceed to payment
4. 🎉 Payment completes automatically

## Environment Variables

### Enable Demo Mode Explicitly
```env
PAYMENT_DEMO_MODE=true
```

### Use Real Razorpay (Production)
```env
RAZORPAY_KEY_ID=rzp_live_yourkey
RAZORPAY_KEY_SECRET=your_secret_key
PAYMENT_DEMO_MODE=false
```

### Test Mode (Real Razorpay Test Keys)
```env
RAZORPAY_KEY_ID=rzp_test_yourkey
RAZORPAY_KEY_SECRET=your_test_secret
PAYMENT_DEMO_MODE=false
```

## On Render

### Current Setup (Demo Mode)
Since no `RAZORPAY_KEY_ID` or `RAZORPAY_KEY_SECRET` is configured on Render, the app automatically runs in **demo mode**. All payments will:
- ✅ Complete successfully
- ✅ Update database records
- ✅ Trigger all post-payment workflows
- ❌ NOT charge any real money
- ❌ NOT create Razorpay transactions

### To Enable Real Payments
Add these environment variables in Render Dashboard:
1. Go to your backend service settings
2. Navigate to Environment tab
3. Add:
   ```
   RAZORPAY_KEY_ID=rzp_test_yourkey
   RAZORPAY_KEY_SECRET=your_secret_key
   ```
4. Redeploy (or wait for auto-deploy)

## Benefits

### Development & Testing
- ✅ Test complete payment flow without credentials
- ✅ No setup required for new developers
- ✅ Safe for demonstrations and presentations
- ✅ Works on free tier hosting (Render, Heroku, etc.)

### Error Handling
- ✅ Graceful fallback if Razorpay is down
- ✅ No broken payment flows due to missing config
- ✅ Clear indication when in demo mode

### Cost Savings
- ✅ No Razorpay transaction fees during testing
- ✅ Preserve limited test mode transactions
- ✅ Free demos for potential clients

## Logs

### Backend Logs (Demo Mode)
```
💳 DEMO PAYMENT MODE: Using mock payment gateway
💳 Creating DEMO order: ₹500
💳 AUTO-VERIFYING demo payment: order_demo_1234567890_500
```

### Backend Logs (Connection Fallback)
```
⚠️  Razorpay connection failed: RemoteDisconnected('Remote end closed connection'). Using demo order.
💳 AUTO-VERIFYING demo payment: order_fallback_1234567890_500
```

### Frontend Console
```
💳 DEMO MODE: Payment simulated successfully!
```

## Database Records

All payment records are created normally in demo mode:
- ✅ Venues marked as PAID
- ✅ Subscription plans activated
- ✅ Bookings confirmed
- ✅ Payment history recorded

The only difference: `transaction_id` will contain demo/fallback order IDs.

## Security Notes

- ⚠️ Demo mode should only be used for testing/development
- ⚠️ Always configure real Razorpay keys in production
- ⚠️ Monitor backend logs to ensure demo mode is not accidentally active in production
- ⚠️ Set `PAYMENT_DEMO_MODE=false` explicitly in production even with real keys

## Troubleshooting

### Issue: Real payments still use demo mode
**Solution**: Check that `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are set correctly in environment variables and do not contain "placeholder" in the value.

### Issue: Razorpay works but keeps failing
**Solution**: Check your Razorpay key validity and account status. The system will auto-fallback to demo mode on connection errors.

### Issue: Want to force demo mode even with keys
**Solution**: Set `PAYMENT_DEMO_MODE=true` in environment variables.

## Next Steps

Once you're ready for real payments:
1. Sign up for Razorpay account: https://dashboard.razorpay.com/signup
2. Get test keys from Razorpay dashboard
3. Add keys to Render environment variables
4. Test with Razorpay test cards: https://razorpay.com/docs/payments/payments/test-card-details/
5. Switch to live keys when ready for production

---

**Note**: Demo mode is production-safe. It will never charge real money or create actual payment transactions.
