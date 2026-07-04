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
from server.src.data.dto.GoalPlanDTO import GoalPlanDTO
from server.src.data.dto.MetricsDTO import MetricsDTO
from server.src.data.dto.ProfileDTO import ProfileDTO
from server.src.services.AlertSyncService import sync_alerts
from server.src.services.composition import CompositionEngine
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
            target_bf=float(payload["target_bf"]),
            weekly_rate=float(payload["weekly_rate"]),
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
    try:
        _user_manager().update_profile(g.user_id, **fields)
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
    goal_history = _goal_plan_manager().list_history(g.user_id)
    audit_entries = _audit_log_dao().list_for_user(g.user_id)
    return jsonify(
        {
            "profile": asdict(profile_dto),
            "logs": [asdict(BodyLogDTO.from_domain(log)) for log in logs],
            "goal_history": [
                asdict(GoalPlanDTO.from_domain(goal)) for goal in goal_history
            ],
            "audit_log": [
                asdict(AuditEntryDTO.from_domain(entry)) for entry in audit_entries
            ],
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


@user_bp.post("/users/me/import")
@require_auth
def import_data():
    payload = request.get_json(force=True) or {}
    created = []
    for entry in payload.get("logs", []):
        try:
            created.append(
                _log_manager().create_log(
                    user_id=g.user_id,
                    log_date=date.fromisoformat(entry["date"]),
                    weight_kg=float(entry["weight_kg"]),
                    waist_cm=float(entry["waist_cm"]),
                    neck_cm=float(entry["neck_cm"]),
                    intake_kcal=float(entry["intake_kcal"]),
                    steps=float(entry["steps"]),
                    intake_is_real=bool(entry.get("intake_is_real", True)),
                    cardio_kcal=float(entry.get("cardio_kcal", 0.0)),
                    source=entry.get("source", "real"),
                )
            )
        except (KeyError, ValueError):
            continue
    return (
        jsonify(
            {
                "imported": len(created),
                "logs": [asdict(BodyLogDTO.from_domain(log)) for log in created],
            }
        ),
        201,
    )
