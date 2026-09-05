from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from .extensions import db
from .models import User, Meal, Type
import os
from uuid import UUID

bp = Blueprint("api", __name__)


def normalize_datetime(value):
    if isinstance(value, str):
        value = value.replace("Z", "+00:00")
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"msg": "username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"msg": "bad credentials"}), 401

    expires_days = int(os.environ.get("JWT_ACCESS_EXPIRES_DAYS", "365"))
    access_token = create_access_token(
        identity=str(user.id), expires_delta=timedelta(days=expires_days)
    )
    return jsonify({"access_token": access_token}), 200


@bp.route("/types", methods=["GET"])
def get_types():
    types = Type.query.all()
    return jsonify([{"id": str(t.id), "name": t.name} for t in types])


@bp.route("/meal", methods=["POST"])
@jwt_required()
def post_meal():
    data = request.get_json() or {}
    # expected fields: id (optional), datetime, description, type_id
    mid = data.get("id")
    dt = data.get("datetime")
    description = data.get("description")
    type_id = data.get("type_id")
    user_id = get_jwt_identity()

    if not dt or not type_id:
        return jsonify({"msg": "datetime and type_id are required"}), 400

    try:
        parsed = normalize_datetime(dt)
    except Exception:
        return jsonify({"msg": "invalid datetime format, use ISO format"}), 400

    if mid:
        meal = Meal.query.get(mid)
        if meal:
            meal.datetime = parsed
            meal.description = description
            meal.type_id = UUID(type_id)
        else:
            meal = Meal(
                id=UUID(mid),
                datetime=parsed,
                description=description,
                type_id=UUID(type_id),
                user_id=UUID(user_id),
            )
            db.session.add(meal)
    else:
        meal = Meal(
            datetime=parsed,
            description=description,
            type_id=UUID(type_id),
            user_id=UUID(user_id),
        )
        db.session.add(meal)

    db.session.commit()
    return jsonify({"id": str(meal.id)}), 201


@bp.route("/meal", methods=["DELETE"])
@jwt_required()
def delete_meal():
    mid = request.args.get("id")
    if not mid:
        return jsonify({"msg": "id required"}), 400
    meal = Meal.query.get(mid)
    if not meal:
        return jsonify({"msg": "not found"}), 404
    db.session.delete(meal)
    db.session.commit()
    return jsonify({"msg": "deleted"}), 200


@bp.route("/meal", methods=["GET"])
def get_meal():
    mid = request.args.get("id")
    if not mid:
        return jsonify({"msg": "id required"}), 400
    meal = Meal.query.get(mid)
    if not meal:
        return jsonify({"msg": "not found"}), 404
    return jsonify(
        {
            "id": str(meal.id),
            "datetime": meal.datetime.isoformat(),
            "description": meal.description,
            "type_id": str(meal.type_id),
            "user_id": str(meal.user_id),
        }
    )


@bp.route("/meals", methods=["GET"])
def list_meals():
    frm = request.args.get("from")
    to = request.args.get("to")
    type_id = request.args.get("type")

    q = Meal.query
    if frm:
        try:
            frm_dt = normalize_datetime(frm)
            q = q.filter(Meal.datetime >= frm_dt)
        except Exception:
            return jsonify({"msg": "invalid from datetime"}), 400
    if to:
        try:
            to_dt = normalize_datetime(to)
            q = q.filter(Meal.datetime <= to_dt)
        except Exception:
            return jsonify({"msg": "invalid to datetime"}), 400
    if type_id:
        try:
            q = q.filter(Meal.type_id == UUID(type_id))
        except Exception:
            return jsonify({"msg": "invalid type id"}), 400

    meals = q.order_by(Meal.datetime).all()
    return jsonify(
        [
            {
                "id": str(m.id),
                "datetime": m.datetime.isoformat(),
                "description": m.description,
                "type_id": str(m.type_id),
                "user_id": str(m.user_id),
            }
            for m in meals
        ]
    )


@bp.route("/copy_meals", methods=["POST"])
@jwt_required()
def copy_meals():
    # query params: source_from, source_to, dest_from, dest_to
    sf = request.args.get("source_from")
    st = request.args.get("source_to")
    df = request.args.get("dest_from")
    dt = request.args.get("dest_to")
    user_id = get_jwt_identity()

    if not all([sf, st, df, dt]):
        return jsonify({"msg": "all four range params required"}), 400

    try:
        s_from = normalize_datetime(sf)
        s_to = normalize_datetime(st)
        d_from = normalize_datetime(df)
        d_to = normalize_datetime(dt)
    except Exception:
        return jsonify({"msg": "invalid datetime format, use ISO format"}), 400

    # load source meals for this user
    src_meals = Meal.query.filter(
        Meal.user_id == UUID(user_id), Meal.datetime >= s_from, Meal.datetime <= s_to
    ).all()
    if not src_meals:
        return jsonify({"copied": 0}), 200

    # compute day offset between source range starts
    delta = d_from - s_from
    copied = 0
    for m in src_meals:
        new_dt = m.datetime + delta
        if new_dt < d_from or new_dt > d_to:
            continue
        new_meal = Meal(
            datetime=new_dt,
            description=m.description,
            type_id=m.type_id,
            user_id=UUID(user_id),
        )
        db.session.add(new_meal)
        copied += 1

    db.session.commit()
    return jsonify({"copied": copied}), 201
