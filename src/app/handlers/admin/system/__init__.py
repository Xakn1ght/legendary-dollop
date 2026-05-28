# Register order: menu & callbacks
from . import (
    admin_screens,  # noqa: F401, E402
    backup,  # noqa: F401, E402
    commands,  # noqa: F401, E402
    logs,  # noqa: F401, E402
    menu,  # noqa: F401, E402
)
from .common import router

__all__ = ["router"]
