"""Create payment_transactions table"""
import asyncio
from app.database import engine, Base
from app.models.payment_transaction import PaymentTransaction

async def create_tables():
    async with engine.begin() as conn:
        # Create only the payment_transactions table
        await conn.run_sync(Base.metadata.create_all, tables=[PaymentTransaction.__table__])
    print("payment_transactions table created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())
