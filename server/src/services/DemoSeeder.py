"""Seeds the verified "Danel" reference user and weekly logs.

Used both at server boot (``JUSTFITTING_SEED_DEMO=true``, see
``api/app.py``) and by ``scripts/seed_demo_data.py`` for manual seeding on
an existing database. No-op if the demo user already exists.
"""

from __future__ import annotations

from server.src.services.LogManager import LogManager, demo_profile_params
from server.src.services.UserManager import UserManager

DEMO_USERNAME = "admin"
DEMO_PASSWORD = "adminadmin"
DEMO_EMAIL = "admin@justfitting.local"


def seed_if_empty(user_manager: UserManager, log_manager: LogManager) -> bool:
    """Create the demo user and its reference logs if they don't exist yet.

    Returns True if data was seeded, False if the demo user already existed.
    """
    if user_manager.user_dao.get_by_username(DEMO_USERNAME):
        return False

    profile_params = demo_profile_params()
    profile = user_manager.register(
        username=DEMO_USERNAME,
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        height_cm=profile_params.height_cm,
        sex=profile_params.sex,
        birthdate=profile_params.birthdate,
        target_bf=profile_params.target_bf,
        weekly_rate=profile_params.weekly_rate,
    )
    log_manager.seed_reference_series(profile.user_id)
    return True
