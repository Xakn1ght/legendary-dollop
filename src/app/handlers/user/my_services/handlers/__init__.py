# Side-effect imports register handlers on the shared router from common.
from . import (
    charge_revoke,  # noqa: F401
    detail,  # noqa: F401
    links_usage,  # noqa: F401
    service_list,  # noqa: F401
    support_bridge,  # noqa: F401
)
from .common import ServiceManagementState, router

__all__ = ["router", "ServiceManagementState"]
