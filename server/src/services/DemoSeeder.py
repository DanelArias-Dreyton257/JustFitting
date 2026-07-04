"""Seeds the verified "Danel" (cut) and "Sergio" (bulk) reference users and
their weekly logs -- see docs/composition_spec.md's worked examples.

Used both at server boot (``JUSTFITTING_SEED_DEMO=true``, see
``api/app.py``) and by ``scripts/seed_demo_data.py`` for manual seeding on
an existing database. Each account is seeded independently and is a no-op
if it already exists, so re-running is always safe.
"""

from __future__ import annotations

from typing import Optional

from server.src.services.EngineSettingsManager import EngineSettingsManager
from server.src.services.LogManager import LogManager, bulk_demo_profile_params, demo_profile_params
from server.src.services.UserManager import UserManager

CUT_USERNAME = "admin_cut"
BULK_USERNAME = "admin_bulk"
DEMO_PASSWORD = "adminadmin"
CUT_EMAIL = "admin_cut@justfitting.local"
BULK_EMAIL = "admin_bulk@justfitting.local"


def _seed_cut_account(user_manager: UserManager, log_manager: LogManager) -> bool:
    """Danel: a cut, default engine settings throughout -- the "no
    customization needed" contrast to the bulk account below."""
    if user_manager.user_dao.get_by_username(CUT_USERNAME):
        return False

    profile_params = demo_profile_params()
    profile = user_manager.register(
        username=CUT_USERNAME,
        email=CUT_EMAIL,
        password=DEMO_PASSWORD,
        height_cm=profile_params.height_cm,
        sex=profile_params.sex,
        birthdate=profile_params.birthdate,
        target_bf=profile_params.target_bf,
        weekly_rate=profile_params.weekly_rate,
    )
    log_manager.seed_reference_series(profile.user_id)
    return True


def _seed_bulk_account(
    user_manager: UserManager,
    log_manager: LogManager,
    engine_settings_manager: Optional[EngineSettingsManager],
) -> bool:
    """Sergio: a bulk, with Mifflin-St Jeor BMR and macro-based TEF turned
    on (Phase 3/3.4) -- the fully-customized counterpart to the cut
    account's defaults, and its most recent weeks log daily granularity
    with macros so there's real data for tef_mode="macros" to compute."""
    if user_manager.user_dao.get_by_username(BULK_USERNAME):
        return False

    profile_params = bulk_demo_profile_params()
    profile = user_manager.register(
        username=BULK_USERNAME,
        email=BULK_EMAIL,
        password=DEMO_PASSWORD,
        height_cm=profile_params.height_cm,
        sex=profile_params.sex,
        birthdate=profile_params.birthdate,
        target_bf=profile_params.target_bf,
        weekly_rate=profile_params.weekly_rate,
    )
    log_manager.seed_bulk_reference_series(profile.user_id)
    if engine_settings_manager is not None:
        engine_settings_manager.update_settings(
            profile.user_id, bmr_model="mifflin", tef_mode="macros"
        )
    return True


def seed_if_empty(
    user_manager: UserManager,
    log_manager: LogManager,
    engine_settings_manager: Optional[EngineSettingsManager] = None,
) -> bool:
    """Create the demo accounts and their reference logs if they don't
    exist yet. ``engine_settings_manager`` is optional so existing callers
    keep working unchanged; without it, the bulk account is still seeded,
    just with default (not Mifflin/macros) engine settings.

    Returns True if anything was seeded, False if both accounts already
    existed.
    """
    seeded_cut = _seed_cut_account(user_manager, log_manager)
    seeded_bulk = _seed_bulk_account(user_manager, log_manager, engine_settings_manager)
    return seeded_cut or seeded_bulk
