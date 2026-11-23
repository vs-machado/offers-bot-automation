import importlib
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


class DeliveryCategoryMigrationTests(unittest.TestCase):
    def test_upgrade_keeps_legacy_category_unknown_and_downgrade_preserves_row(self):
        migration = importlib.import_module(
            "backend.alembic.versions.0024_delivery_category"
        )
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE promotion_deliveries (id TEXT)")
            connection.exec_driver_sql(
                "INSERT INTO promotion_deliveries VALUES ('old')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                self.assertEqual(
                    connection.exec_driver_sql(
                        "SELECT id, category FROM promotion_deliveries"
                    ).all(),
                    [("old", None)],
                )
                migration.downgrade()
            self.assertEqual(
                [
                    c["name"]
                    for c in inspect(connection).get_columns("promotion_deliveries")
                ],
                ["id"],
            )
            self.assertEqual(
                connection.exec_driver_sql("SELECT id FROM promotion_deliveries").all(),
                [("old",)],
            )
