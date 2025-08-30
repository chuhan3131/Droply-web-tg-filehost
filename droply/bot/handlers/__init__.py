from .user_handlers import router as user_router
from .admin_handlers import router as admin_router

__all__ = ["user_router", "admin_router"]