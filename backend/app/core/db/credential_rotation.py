"""Re-encrypt stored configuration with the active external credential key."""

import asyncio

from sqlalchemy import column, select, table, update

from backend.app.core.credentials import (
    credential_cipher,
    decrypt_config,
    encrypt_config,
)

configs = table(
    "user_configs",
    column("id"),
    column("user_id"),
    column("config_type"),
    column("config_data"),
)


def reencrypt_configs(connection) -> int:
    """Encrypt legacy rows or rotate existing rows; caller owns atomic transaction."""
    credential_cipher()
    count = 0
    for row in connection.execute(select(configs).with_for_update()).mappings():
        data = decrypt_config(row["config_data"], row["user_id"], row["config_type"])
        connection.execute(
            update(configs)
            .where(configs.c.id == row["id"])
            .values(
                config_data=encrypt_config(data, row["user_id"], row["config_type"])
            )
        )
        count += 1
    return count


async def main() -> None:
    """Rotate every config transactionally without printing keys or credentials."""
    from backend.app.core.db.session import engine

    try:
        async with engine.begin() as connection:
            count = await connection.run_sync(reencrypt_configs)
        print(f"Re-encrypted {count} user configurations.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
