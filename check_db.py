"""Quick script to check database contents"""
import asyncio
from app.db.session import get_async_db
from sqlalchemy import text


async def check():
    async for db in get_async_db():
        # Check users
        result = await db.execute(text('SELECT id, email, org_id, oauth_provider FROM users LIMIT 5'))
        rows = result.fetchall()
        print("=" * 50)
        print("USERS IN DATABASE:")
        print("=" * 50)
        if rows:
            for row in rows:
                print(f"  ID: {row[0]}")
                print(f"  Email: {row[1]}")
                print(f"  Org: {row[2]}")
                print(f"  OAuth: {row[3]}")
                print("-" * 30)
        else:
            print("  No users found")
        
        # Check emails
        result2 = await db.execute(text('SELECT COUNT(*) FROM emails'))
        count = result2.scalar()
        print(f"\nTOTAL EMAILS: {count}")
        
        if count > 0:
            result3 = await db.execute(text('SELECT id, subject, sender, user_id, org_id FROM emails LIMIT 5'))
            emails = result3.fetchall()
            print("\nSAMPLE EMAILS:")
            for e in emails:
                print(f"  Subject: {e[1]}")
                print(f"  From: {e[2]}")
                print(f"  user_id: {e[3]}, org_id: {e[4]}")
                print("-" * 30)
        
        break


if __name__ == "__main__":
    asyncio.run(check())
