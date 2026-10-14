from .manager import ConnectionManager

# Global process-local socket registries. Fan-out still goes through realtime_service
# so user delivery works across multiple Uvicorn workers.
private_manager = ConnectionManager()
room_manager = ConnectionManager()
call_manager = ConnectionManager()

# Account-level suspension must disconnect sockets across every Uvicorn worker.
from .account_control import install_account_control  # noqa: E402

install_account_control(private_manager, room_manager, call_manager)

__all__ = ['ConnectionManager', 'private_manager', 'room_manager', 'call_manager']
