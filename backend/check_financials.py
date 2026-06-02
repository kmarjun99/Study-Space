import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def check_data():
    async with async_session_maker() as db:
        # Check subscription plans
        result = await db.execute(text('SELECT id, name, price, duration_days FROM subscription_plans'))
        plans = result.fetchall()
        print('=== Subscription Plans ===')
        for plan in plans:
            print(f'ID: {plan[0]}, Name: {plan[1]}, Price: ₹{plan[2]}, Days: {plan[3]}')
        
        print('\n=== Accommodations with Payments ===')
        result = await db.execute(text(
            'SELECT id, name, type, subscription_plan_id, payment_id, owner_id '
            'FROM accommodations WHERE payment_id IS NOT NULL'
        ))
        accs = result.fetchall()
        for acc in accs:
            print(f'ID: {acc[0]}, Name: {acc[1]}, Type: {acc[2]}, Plan: {acc[3]}, Payment: {acc[4]}, Owner: {acc[5]}')
        
        print('\n=== Current User (kmarjun345@gmail.com) ===')
        result = await db.execute(text("SELECT id, email FROM users WHERE email = 'kmarjun345@gmail.com'"))
        user = result.fetchone()
        if user:
            print(f'User ID: {user[0]}')

asyncio.run(check_data())
