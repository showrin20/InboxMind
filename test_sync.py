"""Manual email sync test script"""
import asyncio
from app.db.session import get_async_db
from app.models.user import User
from app.services.email_sync_service import get_email_sync_service
from sqlalchemy import select


async def manual_sync():
    print("=" * 50)
    print("MANUAL EMAIL SYNC TEST")
    print("=" * 50)
    
    async for db in get_async_db():
        # Get user
        result = await db.execute(
            select(User).where(User.email == "showrin.ontiktechnology@gmail.com")
        )
        user = result.scalar_one_or_none()
        
        if not user:
            print("ERROR: User not found!")
            return
        
        print(f"User: {user.email}")
        print(f"Has access token: {bool(user.encrypted_access_token)}")
        print(f"Has refresh token: {bool(user.encrypted_refresh_token)}")
        print(f"Token expires: {user.token_expires_at}")
        print(f"Last sync: {user.last_email_sync}")
        print("-" * 50)
        
        # Try to sync
        sync_service = get_email_sync_service()
        
        try:
            synced, skipped, errors = await sync_service.sync_emails_for_user(
                db=db,
                user=user,
                max_emails=50,
                since_days=30
            )
            
            print(f"\nRESULTS:")
            print(f"  Synced: {synced}")
            print(f"  Skipped: {skipped}")
            print(f"  Errors: {len(errors)}")
            
            if errors:
                print("\nERRORS:")
                for err in errors:
                    print(f"  - {err}")
                    
        except Exception as e:
            print(f"\nSYNC FAILED: {e}")
            import traceback
            traceback.print_exc()
        
        break


if __name__ == "__main__":
    asyncio.run(manual_sync())
