import razorpay
import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import HTTPException
import os

class PaymentService:
    def __init__(self):
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
        
        if not self.razorpay_key_id or not self.razorpay_key_secret:
            print("WARNING: Razorpay credentials not configured. Payment gateway will not work.")
            self.client = None
        else:
            self.client = razorpay.Client(auth=(self.razorpay_key_id, self.razorpay_key_secret))
    
    def create_order(self, amount: float, currency: str = "INR", receipt: str = None, notes: Dict = None) -> Dict[str, Any]:
        """
        Create a Razorpay order
        
        Args:
            amount: Amount in rupees (will be converted to paise)
            currency: Currency code (default: INR)
            receipt: Receipt/booking ID
            notes: Additional notes/metadata
        
        Returns:
            Order details including order_id
        """
        if not self.client:
            raise HTTPException(status_code=500, detail="Payment gateway not configured")
        
        try:
            # Convert rupees to paise (Razorpay uses smallest currency unit)
            amount_in_paise = int(amount * 100)
            
            order_data = {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt or f"receipt_{int(amount)}",
                "notes": notes or {}
            }
            
            order = self.client.order.create(data=order_data)
            return order
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create payment order: {str(e)}")
    
    def verify_payment_signature(self, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verify Razorpay payment signature
        
        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            razorpay_signature: Signature from Razorpay
        
        Returns:
            True if signature is valid, False otherwise
        """
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
