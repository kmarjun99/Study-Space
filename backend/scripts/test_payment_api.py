"""Test the /user/payment-modes endpoint directly"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_payment_modes():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, desc
    from app.models.payment_transaction import PaymentTransaction
    
    engine = create_async_engine("sqlite+aiosqlite:///study_space.db")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        try:
            # Test the query that the API uses
            result = await db.execute(
                select(PaymentTransaction)
                .order_by(desc(PaymentTransaction.created_at))
                .limit(1)
            )
            last_payment = result.scalar_one_or_none()
            
            print("Test Result:")
            print(f"  Last payment found: {last_payment}")
            if last_payment:
                print(f"  Payment ID: {last_payment.id}")
                print(f"  User ID: {last_payment.user_id}")
                print(f"  Method: {last_payment.method}")
                print(f"  Created at: {last_payment.created_at}")
            else:
                print("  No payments in database")
            
            print("\nAPI should return:")
            print({
                "supported_methods": ["UPI", "CARD", "NET_BANKING"],
                "last_used": None if not last_payment else {
                    "method": last_payment.method.value if last_payment.method else "UPI",
                    "gateway": last_payment.gateway.value if last_payment.gateway else "RAZORPAY",
                }
            })
            
        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_payment_modes())
