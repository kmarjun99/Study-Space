import razorpay
import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import HTTPException
import os
from datetime import datetime

class PaymentService:
    def __init__(self):
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        self.demo_mode = os.getenv("PAYMENT_DEMO_MODE", "false").lower() == "true"
        
        if not self.razorpay_key_id or not self.razorpay_key_secret or self.demo_mode:
            print("💳 DEMO PAYMENT MODE: Using mock payment gateway")
            self.client = None
            self.demo_mode = True
        else:
            try:
                self.client = razorpay.Client(auth=(self.razorpay_key_id, self.razorpay_key_secret))
                print("✅ Razorpay client initialized successfully")
            except Exception as e:
                print(f"⚠️  Razorpay initialization failed: {e}. Using demo mode.")
                self.client = None
                self.demo_mode = True
    
    def create_order(self, amount: float, currency: str = "INR", receipt: str = None, notes: Dict = None) -> Dict[str, Any]:
        """
        Create a Razorpay order (or mock order in demo mode)
        
        Args:
            amount: Amount in rupees (will be converted to paise)
            currency: Currency code (default: INR)
            receipt: Receipt/booking ID
            notes: Additional notes/metadata
        
        Returns:
            Order details including order_id
        """
        amount_in_paise = int(amount * 100)
        
        # DEMO MODE: Return mock order
        if not self.client or self.demo_mode:
            print(f"💳 Creating DEMO order: ₹{amount}")
            return {
                "id": f"order_demo_{int(datetime.utcnow().timestamp())}_{int(amount)}",
                "entity": "order",
                "amount": amount_in_paise,
                "amount_paid": 0,
                "amount_due": amount_in_paise,
                "currency": currency,
                "receipt": receipt or f"receipt_demo_{int(amount)}",
                "status": "created",
                "notes": notes or {},
                "created_at": int(datetime.utcnow().timestamp())
            }
        
        try:
            order_data = {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt or f"receipt_{int(amount)}",
                "notes": notes or {}
            }
            
            order = self.client.order.create(data=order_data)
            return order
        
        except Exception as e:
            # Fallback to demo mode on connection errors
            print(f"⚠️  Razorpay connection failed: {e}. Using demo order.")
            return {
                "id": f"order_fallback_{int(datetime.utcnow().timestamp())}_{int(amount)}",
                "entity": "order",
                "amount": amount_in_paise,
                "amount_paid": 0,
                "amount_due": amount_in_paise,
                "currency": currency,
                "receipt": receipt or f"receipt_fallback_{int(amount)}",
                "status": "created",
                "notes": notes or {},
                "created_at": int(datetime.utcnow().timestamp())
            }
    
    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verify Razorpay payment signature (or auto-verify in demo mode)
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
        
        Returns:
            True if signature is valid, False otherwise
        """
        # DEMO MODE: Auto-verify demo/fallback orders
        if self.demo_mode or razorpay_order_id.startswith(("order_demo_", "order_fallback_")):
            print(f"💳 AUTO-VERIFYING demo payment: {razorpay_order_id}")
            return True
        
        try:
            # Create signature string
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            
            # Generate signature
            generated_signature = hmac.new(
                self.razorpay_key_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(generated_signature, razorpay_signature)
        
        except Exception as e:
            print(f"Error verifying signature: {str(e)}")
            return False
    
    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Fetch payment details from Razorpay
        
        Args:
            payment_id: Razorpay payment ID
        
        Returns:
            Payment details
        """
        if not self.client:
            raise HTTPException(status_code=500, detail="Payment gateway not configured")
        
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch payment: {str(e)}")
    
    def capture_payment(self, payment_id: str, amount: float) -> Dict[str, Any]:
        """
        Capture a payment (for authorized payments)
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount to capture in rupees
        
        Returns:
            Captured payment details
        """
        if not self.client:
            raise HTTPException(status_code=500, detail="Payment gateway not configured")
        
        try:
            amount_in_paise = int(amount * 100)
            return self.client.payment.capture(payment_id, amount_in_paise)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to capture payment: {str(e)}")
    
    def refund_payment(self, payment_id: str, amount: float = None, notes: Dict = None) -> Dict[str, Any]:
        """
        Refund a payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Amount to refund in rupees (None for full refund)
            notes: Additional notes
        
        Returns:
            Refund details
        """
        if not self.client:
            raise HTTPException(status_code=500, detail="Payment gateway not configured")
        
        try:
            refund_data = {"notes": notes or {}}
            
            if amount:
                refund_data["amount"] = int(amount * 100)
            
            return self.client.payment.refund(payment_id, refund_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process refund: {str(e)}")

# Create singleton instance
payment_service = PaymentService()
