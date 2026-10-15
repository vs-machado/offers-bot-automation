from importlib import import_module


def load_models() -> None:
    """Register all ORM tables before Alembic reads Base.metadata."""
    for module_name in ("better_auth", "user", "worker", "whatsapp_policy"):
        import_module(f"{__name__}.{module_name}")
