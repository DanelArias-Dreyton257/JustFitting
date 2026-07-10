"""Registration, auth, profile and account-lifecycle routes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request

from server.src.api.auth import require_auth
from server.src.data.dto.AdherenceDTO import AdherenceDTO
from server.src.data.dto.AlertLogDTO import AlertLogDTO
from server.src.data.dto.AuditEntryDTO import AuditEntryDTO
from server.src.data.dto.BodyLogDTO import BodyLogDTO
from server.src.data.dto.BodyMeasurementDTO import BodyMeasurementDTO
from server.src.data.dto.EnergyReconciliationDTO import EnergyReconciliationDTO
from server.src.data.dto.GainQualityDTO import GainQualityDTO
from server.src.data.dto.GoalPlanDTO import GoalPlanDTO
from server.src.data.dto.IncrementAnalyticsDTO import IncrementAnalyticsDTO
from server.src.data.dto.MacroTargetsDTO import MacroTargetsDTO
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.data.dto.ProfileDTO import ProfileDTO
from server.src.data.dto.TefDTO import TefDTO
from server.src.services.AlertSyncService import sync_alerts
from server.src.services.BodyMeasurementManager import (
    MEASUREMENT_FIELDS,
    BodyMeasurementManagerError,
)
from server.src.services.composition import (
    CompositionEngine,
    EnergyReconciliation,
    GainQuality,
    IncrementAnalytics,
    MacroTargets,
    Tef,
)
from server.src.services.GoalPlanManager import GoalPlanManagerError
from server.src.services.MetricsSeriesService import compute_series_for_user
from server.src.services.UserManager import UserManagerError

user_bp = Blueprint("users", __name__, url_prefix="/api")


def _user_manager():
    return current_app.extensions["user_manager"]


def _auth_service():
    return current_app.extensions["auth_service"]


def _log_manager():
    return current_app.extensions["log_manager"]


def _measurement_manager():
    return current_app.extensions["body_measurement_manager"]


def _optional_float(value):
    """`None` (missing key or explicit JSON `null`) means "not logged", not
    `0.0` -- Phase 3.4's macro fields must stay unset, not zeroed."""
    return None if value is None else float(value)


def _goal_plan_manager():
    return current_app.extensions["goal_plan_manager"]


def _audit_log_dao():
    return current_app.extensions["audit_log_dao"]


def _profile_dto(user_id: int):
    profile = _user_manager().get_profile(user_id)
    if profile is None:
        return None
    goal = _goal_plan_manager().get_active(user_id)
    return ProfileDTO.from_domain(profile, goal=goal)


def _wave2_metrics(user_id: int, logs, results, goal) -> dict:
    """Phase 3/3.1/3.2/3.4's bulk-mode read-side views (gain quality, energy
    reconciliation, real-increment analytics, TEF breakdown, macro targets),
    shared by the Report and Export payloads -- previously only exposed via
    `GET /api/metrics/*`, so a trainer/nutritionist export or the printable
    Report was missing "is this bulk clean" / "is the energy model tracking
    reality" at a glance (see README's former "Future work" note)."""
    engine_settings_manager = current_app.extensions["engine_settings_manager"]
    ec = engine_settings_manager.to_engine_constants(
        engine_settings_manager.get_active(user_id)
    )
    weekly_rate = goal.weekly_rate if goal is not None else 0.0

    gain_quality = GainQuality.compute_gain_quality(results) if results else []
    energy_balance = (
        EnergyReconciliation.compute_energy_reconciliation(logs, results, ec)
        if results
        else []
    )
    increment_analytics = (
        IncrementAnalytics.compute_increment_analytics(results, weekly_rate)
        if results and goal is not None
        else []
    )
    tef = Tef.compute_tef_breakdown(logs, results, ec) if results else []
    macro_targets = MacroTargets.compute_macro_targets(logs, results, ec) if results else []

    return {
        "gain_quality": [
            asdict(GainQualityDTO.from_domain(row, ec.fat_ratio_ideal)) for row in gain_quality
        ],
        "energy_balance": [
            asdict(
                EnergyReconciliationDTO.from_domain(row, ec.reconciliation_error_threshold_kcal)
            )
            for row in energy_balance
        ],
        "increment_analytics": [
            asdict(IncrementAnalyticsDTO.from_domain(row, weekly_rate))
            for row in increment_analytics
        ],
        "tef": [asdict(TefDTO.from_domain(row)) for row in tef],
        "macro_targets": [asdict(MacroTargetsDTO.from_domain(row)) for row in macro_targets],
    }


@user_bp.post("/users")
def register():
    payload = request.get_json(force=True) or {}
    try:
        profile = _user_manager().register(
            username=payload["username"],
            email=payload["email"],
            password=payload["password"],
            height_cm=float(payload["height_cm"]),
            sex=int(payload["sex"]),
            birthdate=date.fromisoformat(payload["birthdate"]),
            target_bf=float(payload["target_bf"]) if "target_bf" in payload else None,
            weekly_rate=float(payload["weekly_rate"]) if "weekly_rate" in payload else None,
            units=payload.get("units", "metric"),
        )
    except (UserManagerError, GoalPlanManagerError) as exc:
        return jsonify({"error": str(exc)}), 400
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"invalid payload: {exc}"}), 400

    token = _auth_service().issue_token(profile.user_id)
    return (
        jsonify({"token": token, "profile": asdict(_profile_dto(profile.user_id))}),
        201,
    )


@user_bp.post("/auth/login")
def login():
    payload = request.get_json(force=True) or {}
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    profile = _user_manager().authenticate(username, password)
    if profile is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = _auth_service().issue_token(profile.user_id)
    return jsonify(
        {"token": token, "profile": asdict(_profile_dto(profile.user_id))}
    )


@user_bp.post("/auth/logout")
@require_auth
def logout():
    _auth_service().revoke_token(g.token)
    return "", 204


@user_bp.post("/auth/reset-password")
def reset_password():
    """Directly resets a password given a matching username/email -- no
    email verification (see README's "Known limitations"/"Future work")."""
    payload = request.get_json(force=True) or {}
    identifier = payload.get("identifier")
    new_password = payload.get("new_password")
    if not identifier or not new_password:
        return jsonify({"error": "identifier and new_password are required"}), 400
    ok = current_app.extensions["password_reset_service"].reset_password(
        identifier, new_password
    )
    if not ok:
        return jsonify({"error": "no account found for that username or email"}), 404
    return jsonify({"message": "Password updated. You can log in with your new password."})


@user_bp.get("/users/me")
@require_auth
def me():
    dto = _profile_dto(g.user_id)
    if dto is None:
        return jsonify({"error": "user not found"}), 404
    return jsonify(asdict(dto))


@user_bp.put("/users/me")
@require_auth
def update_me():
    payload = request.get_json(force=True) or {}
    fields = {}
    for key in ("height_cm", "sex", "target_bf", "weekly_rate", "units", "email"):
        if key in payload:
            fields[key] = payload[key]
    if "birthdate" in payload:
        fields["birthdate"] = date.fromisoformat(payload["birthdate"])

    # Phase 8.2: a goal change needs the account's current (real, computed)
    # body fat to sign-check the candidate target_bf/weekly_rate against --
    # `None` (no computable log yet) skips GoalPlanManager's coherence check
    # entirely, same as a brand-new default goal at registration.
    current_bf = None
    if "target_bf" in fields or "weekly_rate" in fields:
        _, results = compute_series_for_user(current_app, g.user_id)
        if results:
            current_bf = results[-1].body_fat

    try:
        _user_manager().update_profile(g.user_id, current_bf=current_bf, **fields)
    except (UserManagerError, GoalPlanManagerError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(_profile_dto(g.user_id)))


@user_bp.post("/users/me/password")
@require_auth
def change_password():
    payload = request.get_json(force=True) or {}
    try:
        _user_manager().change_password(
            g.user_id, payload["old_password"], payload["new_password"]
        )
    except UserManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError as exc:
        return jsonify({"error": f"missing field: {exc}"}), 400
    return "", 204


@user_bp.delete("/users/me")
@require_auth
def delete_me():
    _auth_service().revoke_all_for_user(g.user_id)
    _user_manager().delete_user(g.user_id)
    return "", 204


@user_bp.get("/users/me/goals")
@require_auth
def list_goals():
    goals = _goal_plan_manager().list_history(g.user_id)
    return jsonify([asdict(GoalPlanDTO.from_domain(goal)) for goal in goals])


@user_bp.put("/users/me/goals/active/start-date")
@require_auth
def update_active_goal_start_date():
    """Phase 8.1: corrects when the *currently active* goal actually began,
    in place -- not a new historized goal-plan row -- so already-logged
    history (e.g. imported from before the account existed) counts toward
    that goal's own scoped series/trajectory (`active_period_start`)."""
    payload = request.get_json(force=True) or {}
    try:
        new_start_date = date.fromisoformat(payload["start_date"])
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"invalid start_date: {exc}"}), 400
    try:
        goal = _goal_plan_manager().update_start_date(g.user_id, new_start_date)
    except GoalPlanManagerError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(asdict(GoalPlanDTO.from_domain(goal)))


@user_bp.get("/users/me/audit-log")
@require_auth
def audit_log():
    entries = _audit_log_dao().list_for_user(g.user_id)
    return jsonify([asdict(AuditEntryDTO.from_domain(entry)) for entry in entries])


@user_bp.get("/users/me/export")
@require_auth
def export_data():
    profile_dto = _profile_dto(g.user_id)
    logs = _log_manager().list_logs(g.user_id)
    measurements = _measurement_manager().list_for_user(g.user_id)
    goal_history = _goal_plan_manager().list_history(g.user_id)
    audit_entries = _audit_log_dao().list_for_user(g.user_id)

    # Wave 2's read-side views, computed from the (possibly resampled)
    # weekly series -- informational only, not part of the import contract
    # below, which only ever reads back "logs"/"body_measurements" raw rows.
    computed_logs, results = compute_series_for_user(current_app, g.user_id)
    active_goal = _goal_plan_manager().get_active(g.user_id)

    return jsonify(
        {
            "profile": asdict(profile_dto),
            "logs": [asdict(BodyLogDTO.from_domain(log)) for log in logs],
            # Phase 9.1: perimeters' own sporadic history, alongside the
            # weekly logs above.
            "body_measurements": [
                asdict(BodyMeasurementDTO.from_domain(m)) for m in measurements
            ],
            "goal_history": [
                asdict(GoalPlanDTO.from_domain(goal)) for goal in goal_history
            ],
            "audit_log": [
                asdict(AuditEntryDTO.from_domain(entry)) for entry in audit_entries
            ],
            **_wave2_metrics(g.user_id, computed_logs, results, active_goal),
        }
    )


@user_bp.get("/users/me/report")
@require_auth
def report():
    profile_dto = _profile_dto(g.user_id)
    if profile_dto is None:
        return jsonify({"error": "user not found"}), 404

    logs, results = compute_series_for_user(current_app, g.user_id)
    series = [
        asdict(
            MetricsDTO.from_domain(
                result, log_id=log.log_id, engine_version=CompositionEngine.ENGINE_VERSION
            )
        )
        for log, result in zip(logs, results)
    ]
    latest_metrics = series[-1] if series else None

    mean_intake_diff_kcal = _log_manager().compute_adherence(logs, results) if logs else None
    real_log_count = sum(1 for log in logs if log.intake_is_real)
    adherence_dto = AdherenceDTO.from_values(mean_intake_diff_kcal, real_log_count)

    goal_history = _goal_plan_manager().list_history(g.user_id)
    active_goal = _goal_plan_manager().get_active(g.user_id)
    open_alerts = sync_alerts(current_app, g.user_id, include_acknowledged=False)

    return jsonify(
        {
            "profile": asdict(profile_dto),
            "latest_metrics": latest_metrics,
            "adherence": asdict(adherence_dto),
            "goal_history": [
                asdict(GoalPlanDTO.from_domain(goal)) for goal in goal_history
            ],
            "series": series,
            "alerts": [asdict(AlertLogDTO.from_domain(alert)) for alert in open_alerts],
            **_wave2_metrics(g.user_id, logs, results, active_goal),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _fields_from_measurement_entry(entry: dict) -> dict:
    return {key: _optional_float(entry[key]) for key in MEASUREMENT_FIELDS if key in entry}


def _import_measurement_from_inline_perimeters(measurement_manager, log_date, entry) -> None:
    """Phase 9.1 backward compatibility: a pre-Phase-9 export still carries
    `waist_cm`/`neck_cm` inline on each `logs[]` row -- rather than silently
    discarding them (they're no longer valid `body_logs` fields), synthesize
    a `body_measurements` row at that log's own date from them. Best-effort
    and silent: a date collision or invalid value just means this
    particular row's perimeters aren't recovered, it never fails the log
    import itself."""
    waist_cm = _optional_float(entry.get("waist_cm"))
    neck_cm = _optional_float(entry.get("neck_cm"))
    if waist_cm is None and neck_cm is None:
        return
    if measurement_manager.get_by_date(g.user_id, log_date) is not None:
        return
    try:
        measurement_manager.create(g.user_id, log_date, waist_cm=waist_cm, neck_cm=neck_cm)
    except BodyMeasurementManagerError:
        pass


@user_bp.post("/users/me/import")
@require_auth
def import_data():
    """Bulk-import log rows (and, Phase 9.1, body-measurement rows) from the
    same shape `GET /api/users/me/export` produces (JSON) or, client-side, a
    CSV file translated into it (Phase 7.2, README) -- see the README's
    "Import JSON format reference" for the full field-by-field contract this
    route implements."""
    payload = request.get_json(force=True) or {}
    log_manager = _log_manager()
    measurement_manager = _measurement_manager()
    created = []
    skipped = []
    for index, entry in enumerate(payload.get("logs", [])):
        try:
            log_date = date.fromisoformat(entry["date"])
        except (KeyError, ValueError) as exc:
            skipped.append({"row": index, "reason": f"invalid date: {exc}"})
            continue

        if log_manager.get_by_date(g.user_id, log_date) is not None:
            skipped.append({"row": index, "reason": "duplicate date"})
            continue

        try:
            created.append(
                log_manager.create_log(
                    user_id=g.user_id,
                    log_date=log_date,
                    # Phase 7.4 (partial logs, see README): optional, not
                    # required -- an imported row can be partial too, not
                    # just a synced one.
                    weight_kg=_optional_float(entry.get("weight_kg")),
                    intake_kcal=_optional_float(entry.get("intake_kcal")),
                    steps=_optional_float(entry.get("steps")),
                    intake_is_real=bool(entry.get("intake_is_real", True)),
                    cardio_kcal=float(entry.get("cardio_kcal", 0.0)),
                    granularity=entry.get("granularity", "weekly"),
                    carbs_g=_optional_float(entry.get("carbs_g")),
                    fat_g=_optional_float(entry.get("fat_g")),
                    protein_g=_optional_float(entry.get("protein_g")),
                    # Imports are always real, logged data -- "projected" rows
                    # only ever come from the engine's own forecast, never a
                    # hand-written or re-imported file (whatever the entry's
                    # own `source` field says, if any, is ignored).
                    source="real",
                )
            )
        except (KeyError, ValueError) as exc:
            skipped.append({"row": index, "reason": str(exc)})
            continue

        _import_measurement_from_inline_perimeters(measurement_manager, log_date, entry)

    measurements_created = []
    measurements_skipped = []
    for index, entry in enumerate(payload.get("body_measurements", [])):
        try:
            measurement_date = date.fromisoformat(entry["date"])
        except (KeyError, ValueError) as exc:
            measurements_skipped.append({"row": index, "reason": f"invalid date: {exc}"})
            continue
        if measurement_manager.get_by_date(g.user_id, measurement_date) is not None:
            measurements_skipped.append({"row": index, "reason": "duplicate date"})
            continue
        fields = _fields_from_measurement_entry(entry)
        try:
            measurements_created.append(
                measurement_manager.create(g.user_id, measurement_date, **fields)
            )
        except BodyMeasurementManagerError as exc:
            measurements_skipped.append({"row": index, "reason": str(exc)})

    return (
        jsonify(
            {
                "imported": len(created),
                "skipped": skipped,
                "logs": [asdict(BodyLogDTO.from_domain(log)) for log in created],
                "measurements_imported": len(measurements_created),
                "measurements_skipped": measurements_skipped,
                "body_measurements": [
                    asdict(BodyMeasurementDTO.from_domain(m)) for m in measurements_created
                ],
            }
        ),
        201,
    )
