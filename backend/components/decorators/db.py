import functools
from utils.logger import setup_logger
from database import Database
from fastapi import HTTPException, status

logger = setup_logger(__name__)

def get_session(func, *, lazy=False):
    @functools.wraps(func)
    async def _wrapper(*args, **kwargs):
        db_session = Database.sessionmaker()() if lazy else await Database.get_session()
        try:
            kwargs['db_session'] = db_session
            response = await func(*args, **kwargs)
            await db_session.commit()  # Явный коммит успешной операции
            return response
        except HTTPException as http_exc:
            await db_session.rollback()
            logger.warning(f"HTTP exception: {http_exc.detail}")
            raise http_exc
        except Exception as e:
            await db_session.rollback()
            logger.error(f"Database error: {str(e)}")
            if "websocket" in kwargs:
                try:
                    await kwargs["websocket"].close(code=1011, reason="Internal error")
                except Exception as ws_err:
                    logger.error(f"WebSocket close error: {ws_err}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )
        finally:
            await db_session.close()
    return _wrapper


def get_realtime_session(func):
    """A WebSocket may live for hours; do not check out a connection on entry."""
    return get_session(func, lazy=True)


async def release_realtime_session(db_session):
    """Finish the previous frame before waiting for network input.

    AsyncSession.close returns its connection to the pool and resets the session;
    the same session object can acquire a connection for the next frame.
    """
    await db_session.commit()
    await db_session.close()
