from .admin import router as admin_router
from .auth import router as auth_router
from .user import router as user_router
from .gameplay import router as gameplay_router
from .admin_ops import router as admin_ops_router


__all__ = (
    "auth_router",
    "admin_router",
    "user_router",
    "gameplay_router",
    "admin_ops_router",
)
