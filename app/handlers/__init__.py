from app.handlers.admin import build_admin_handlers
from app.handlers.common import build_unknown_handler
from app.handlers.user import build_user_handlers


def build_handlers(service, admin_ids, is_open_signup):
    common_handlers = build_unknown_handler()
    user_handlers = build_user_handlers(service, is_open_signup)
    admin_handlers = build_admin_handlers(service, admin_ids, common_handlers["unknown"])

    return {
        **user_handlers,
        **admin_handlers,
        **common_handlers,
    }
