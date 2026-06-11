import asyncio
from sqlalchemy.exc import OperationalError, ProgrammingError

from sqlalchemy import select

from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models import User


MIGRATION_REQUIRED_MESSAGE = (
    'Database schema is managed by Alembic. Run `alembic upgrade head` '
    'before executing init_demo.py.'
)


async def main() -> None:
    for _ in range(20):
        try:
            async with AsyncSessionLocal() as db:
                admin_result = await db.execute(select(User).where(User.email == 'admin@corpassist.local'))
                admin = admin_result.scalar_one_or_none()
                if not admin:
                    db.add(User(email='admin@corpassist.local', password_hash=hash_password('AdminPass123!'), role='admin'))

                worker_result = await db.execute(select(User).where(User.email == 'worker@corpassist.local'))
                worker = worker_result.scalar_one_or_none()
                if not worker:
                    db.add(User(email='worker@corpassist.local', password_hash=hash_password('WorkerPass123!'), role='worker'))

                result = await db.execute(select(User).where(User.email == 'demo@corpassist.local'))
                user = result.scalar_one_or_none()
                if user:
                    await db.commit()
                    return
                db.add(User(email='demo@corpassist.local', password_hash=hash_password('DemoPass123!'), role='client'))
                await db.commit()
                return
        except OperationalError:
            await asyncio.sleep(2)
        except ProgrammingError:
            print(MIGRATION_REQUIRED_MESSAGE)
            raise


if __name__ == '__main__':
    asyncio.run(main())
