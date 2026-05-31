from app.handlers.super_admin import build_super_admin_handlers
from app.handlers.group_admin import build_group_admin_handlers
from app.handlers.common import build_unknown_handler
from app.handlers.user import build_user_handlers


def build_handlers(service, admin_ids, is_open_signup):
    common_handlers = build_unknown_handler()
    user_handlers = build_user_handlers(service, is_open_signup)
    super_admin_handlers = build_super_admin_handlers(service, common_handlers["unknown"])
    group_admin_handlers = build_group_admin_handlers(service)

    return {
        **user_handlers,
        **group_admin_handlers,
        **super_admin_handlers,
        **common_handlers,
    }
