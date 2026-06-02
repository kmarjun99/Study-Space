"""Test extension functionality directly"""
import asyncio
import sys
sys.path.insert(0, '.')

from datetime import datetime
from sqlalchemy.future import select

async def test_extension():
    from app.database import AsyncSessionLocal
    from app.models.booking import Booking
    from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentType, PaymentGateway
    
    async with AsyncSessionLocal() as db:
        try:
            # Get first booking
            result = await db.execute(select(Booking).limit(1))
            booking = result.scalars().first()
            
            if not booking:
                print("❌ No bookings found")
                return
            
            print(f"Found booking: {booking.id}")
            print(f"Current end_date: {booking.end_date}")
            print(f"Current amount: {booking.amount}")
            print(f"User ID: {booking.user_id}")
            
            # Create a test PaymentTransaction
            print("\nAttempting to create PaymentTransaction...")
            test_payment = PaymentTransaction(
                booking_id=booking.id,
                user_id=booking.user_id,
                payment_type=PaymentType.EXTENSION,
                method=PaymentMethod.UPI,
                gateway=PaymentGateway.RAZORPAY,
                amount=100.0,
                gateway_transaction_id=f"TEST_{datetime.utcnow().timestamp()}",
                description="Test extension"
            )
            
            db.add(test_payment)
            await db.commit()
            await db.refresh(test_payment)
            
            print(f"✅ PaymentTransaction created successfully!")
            print(f"Payment ID: {test_payment.id}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(test_extension())
