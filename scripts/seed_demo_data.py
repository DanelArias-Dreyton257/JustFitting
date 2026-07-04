#!/usr/bin/env python3
"""Register admin_cut/admin_bulk (both adminadmin) and seed their Danel
(cut) and Sergio (bulk) reference series.

No-op per-account if already seeded. Usage: ``seed_demo_data.py [db_path]``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.src.data.db.AuditLogDAO import AuditLogDAO  # noqa: E402
from server.src.data.db.BodyLogDAO import BodyLogDAO  # noqa: E402
from server.src.data.db.DB import DB  # noqa: E402
from server.src.data.db.EngineSettingsDAO import EngineSettingsDAO  # noqa: E402
from server.src.data.db.GoalPlanDAO import GoalPlanDAO  # noqa: E402
from server.src.data.db.UserDAO import UserDAO  # noqa: E402
from server.src.services import DemoSeeder  # noqa: E402
from server.src.services.EngineSettingsManager import EngineSettingsManager  # noqa: E402
from server.src.services.GoalPlanManager import GoalPlanManager  # noqa: E402
from server.src.services.LogManager import LogManager  # noqa: E402
from server.src.services.UserManager import UserManager  # noqa: E402


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "justfitting.db"
    db = DB(db_path)
    audit_log_dao = AuditLogDAO(db)
    goal_plan_manager = GoalPlanManager(GoalPlanDAO(db), audit_log_dao=audit_log_dao)
    user_manager = UserManager(UserDAO(db), goal_plan_manager, audit_log_dao=audit_log_dao)
    log_manager = LogManager(BodyLogDAO(db), audit_log_dao=audit_log_dao)
    engine_settings_manager = EngineSettingsManager(
        EngineSettingsDAO(db), audit_log_dao=audit_log_dao
    )

    if DemoSeeder.seed_if_empty(user_manager, log_manager, engine_settings_manager):
        print(
            "Created admin_cut/admin_bulk (password adminadmin) and seeded "
            "their Danel (cut) and Sergio (bulk) reference series."
        )
    else:
        print("admin_cut and admin_bulk already exist, skipping.")


if __name__ == "__main__":
    main()
