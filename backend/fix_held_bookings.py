"""
Fix HELD bookings that should be ACTIVE
This script processes any bookings stuck in HELD status and:
1. Updates booking status to ACTIVE
2. Updates payment status to PAID
3. Creates PaymentTransaction records
4. Updates cabin status to OCCUPIED
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.payment_transaction import PaymentTransaction, PaymentMethod, PaymentGateway, PaymentType
from app.models.reading_room import Cabin, CabinStatus
from sqlalchemy.future import select


async def fix_held_bookings():
    """Fix bookings stuck in HELD status"""
    async with AsyncSessionLocal() as db:
        # Find all HELD bookings
        result = await db.execute(
            select(Booking).where(Booking.status == BookingStatus.HELD)
        )
        held_bookings = result.scalars().all()
        
        if not held_bookings:
            print("✓ No HELD bookings found. All bookings are properly processed!")
            return
        
        print(f"Found {len(held_bookings)} HELD booking(s) to process...")
        
        fixed_count = 0
        for booking in held_bookings:
            print(f"\n📝 Processing booking {booking.id}:")
            print(f"   User: {booking.user_id}")
            print(f"   Cabin: {booking.cabin_id}")
            print(f"   Amount: ₹{booking.amount}")
            
            # Update booking status
            booking.status = BookingStatus.ACTIVE
            booking.payment_status = PaymentStatus.PAID
            if not booking.transaction_id:
                booking.transaction_id = f"manual_fix_{booking.id[:8]}"
            
            # Check if PaymentTransaction already exists
            tx_result = await db.execute(
                select(PaymentTransaction).where(
                    PaymentTransaction.booking_id == booking.id
                )
            )
            existing_tx = tx_result.scalar_one_or_none()
            
            if not existing_tx:
                # Create PaymentTransaction record
                payment_tx = PaymentTransaction(
                    booking_id=booking.id,
                    user_id=booking.user_id,
                    payment_type=PaymentType.INITIAL,
                    method=PaymentMethod.UPI,
                    gateway=PaymentGateway.RAZORPAY,
                    amount=booking.amount,
                    gateway_transaction_id=booking.transaction_id,
                    description="Migrated from HELD booking"
                )
                db.add(payment_tx)
                print("   ✓ Created PaymentTransaction record")
            else:
                print("   ℹ️  PaymentTransaction already exists")
            
            # Update cabin status
            if booking.cabin_id:
                cabin_result = await db.execute(
                    select(Cabin).where(Cabin.id == booking.cabin_id)
                )
                cabin = cabin_result.scalar_one_or_none()
                
                if cabin:
                    cabin.status = CabinStatus.OCCUPIED
                    cabin.current_occupant_id = booking.user_id
                    print(f"   ✓ Updated cabin {cabin.number} to OCCUPIED")
            
            fixed_count += 1
        
        # Commit all changes
        await db.commit()
        
        print(f"\n✅ Successfully processed {fixed_count} booking(s)!")
        print("\n📊 Summary:")
        print(f"   - Bookings updated: {fixed_count}")
        print(f"   - Status changed: HELD → ACTIVE")
        print(f"   - Payment status: PENDING → PAID")
        print(f"   - Cabins updated: RESERVED → OCCUPIED")
        print("\n💡 Your financial reports should now show the revenue from these bookings.")


if __name__ == "__main__":
    print("🔧 Fixing HELD bookings...\n")
    asyncio.run(fix_held_bookings())
    print("\n✨ Done! Please refresh your financial reports page.")
