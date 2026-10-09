import json

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
from .extensions import db
from .models import User, Meal, Type, MealField
import os
from uuid import UUID, uuid4
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

bp = Blueprint("api", __name__)


def normalize_datetime(value):
    if isinstance(value, str):
        value = value.replace("Z", "+00:00")
        value = datetime.fromisoformat(value)

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_meal_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_meal_fields(payload):
    description = normalize_meal_text(payload.get("description"))
    raw_entries = (
        payload.get("entries") if isinstance(payload.get("entries"), dict) else {}
    )
    compact_entries = {}
    for key, value in raw_entries.items():
        cleaned = normalize_meal_text(value)
        if cleaned is not None:
            compact_entries[str(key)] = cleaned

    if compact_entries:
        description = json.dumps(compact_entries, ensure_ascii=False)
    elif description is not None:
        description = description

    return {
        "description": description,
        "entries": compact_entries,
    }


def meal_table_columns():
    try:
        inspector = inspect(db.engine)
        return {column["name"] for column in inspector.get_columns("meals")}
    except Exception:
        return set()


def meal_supports_split_fields():
    columns = meal_table_columns()
    return {"antonio", "annalisa"}.issubset(columns)


def serialize_meal_row(row):
    values = row._mapping if hasattr(row, "_mapping") else row
    description = values.get("description")
    parsed_entries = {}
    try:
        if isinstance(description, str) and description.strip():
            parsed = json.loads(description)
            if isinstance(parsed, dict):
                parsed_entries = {
                    str(key): normalize_meal_text(value) or ""
                    for key, value in parsed.items()
                }
    except Exception:
        parsed_entries = {}

    if parsed_entries:
        return {
            "id": str(values["id"]),
            "datetime": values["datetime"].isoformat(),
            "description": json.dumps(parsed_entries, ensure_ascii=False),
            "antonio": None,
            "annalisa": None,
            "type_id": str(values["type_id"]),
            "user_id": str(values["user_id"]),
            "entries": parsed_entries,
        }

    legacy_description = normalize_meal_text(description)
    return {
        "id": str(values["id"]),
        "datetime": values["datetime"].isoformat(),
        "description": legacy_description,
        "antonio": None,
        "annalisa": None,
        "type_id": str(values["type_id"]),
        "user_id": str(values["user_id"]),
        "entries": {},
    }


def serialize_meal(meal):
    description = normalize_meal_text(getattr(meal, "description", None))
    return {
        "id": str(meal.id),
        "datetime": meal.datetime.isoformat(),
        "description": description,
        "antonio": None,
        "annalisa": None,
        "type_id": str(meal.type_id),
        "user_id": str(meal.user_id),
    }


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


@bp.route("/meal-fields", methods=["GET"])
@jwt_required(optional=True)
def get_meal_fields():
    rows = MealField.query.order_by(MealField.idx.asc(), MealField.name.asc()).all()
    if not rows:
        from seed_default_data import parse_configured_meal_names

        return jsonify(
            [
                {"id": str(i), "name": name, "idx": i + 1}
                for i, name in enumerate(parse_configured_meal_names())
            ]
        )

    return jsonify(
        [{"id": str(field.id), "name": field.name, "idx": field.idx} for field in rows]
    )


@bp.route("/types", methods=["GET"])
def get_types():
    types = Type.query.order_by(Type.idx.asc()).all()
    return jsonify([{"id": str(t.id), "name": t.name, "idx": t.idx} for t in types])


@bp.route("/types", methods=["DELETE"])
@jwt_required()
def delete_type():
    tid = request.args.get("id")
    if not tid:
        return jsonify({"msg": "id required"}), 400
    try:
        t = Type.query.get(tid)
    except Exception:
        t = None
    if not t:
        return jsonify({"msg": "not found"}), 404
    try:
        db.session.delete(t)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"msg": "type in use"}), 409
    return jsonify({"msg": "deleted"}), 200


@bp.route("/types", methods=["POST"])
@jwt_required()
def post_type():
    data = request.get_json() or {}
    tid = data.get("id")
    name = data.get("name")

    if not name:
        return jsonify({"msg": "name is required"}), 400

    if tid:
        # try update existing
        try:
            t = Type.query.get(tid)
        except Exception:
            t = None
        if t:
            t.name = name
        else:
            try:
                t = Type(id=UUID(tid), name=name)
                db.session.add(t)
            except Exception:
                return jsonify({"msg": "invalid id format"}), 400
    else:
        t = Type(name=name)
        db.session.add(t)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"msg": "type name already exists"}), 409

    return jsonify({"id": str(t.id), "name": t.name, "idx": t.idx}), 201


@bp.route("/meal", methods=["POST"])
@jwt_required()
def post_meal():
    data = request.get_json() or {}
    mid = data.get("id")
    dt = data.get("datetime")
    type_id = data.get("type_id")
    user_id = get_jwt_identity()
    fields = build_meal_fields(data)
    description = fields["description"]

    if not dt or not type_id:
        return jsonify({"msg": "datetime and type_id are required"}), 400

    try:
        parsed = normalize_datetime(dt)
    except Exception:
        return jsonify({"msg": "invalid datetime format, use ISO format"}), 400

    meal_id = UUID(mid) if mid else uuid4()

    if mid:
        existing = db.session.execute(
            text(
                "SELECT id, user_id, datetime, description, type_id FROM meals WHERE id = :meal_id"
            ),
            {"meal_id": str(mid)},
        ).fetchone()
        if existing and str(existing.user_id) != str(user_id):
            return jsonify({"msg": "forbidden"}), 403
        if existing:
            db.session.execute(
                text(
                    "UPDATE meals SET datetime = :dt, description = :description, type_id = :type_id WHERE id = :meal_id"
                ),
                {
                    "dt": parsed,
                    "description": description,
                    "type_id": str(type_id),
                    "meal_id": str(mid),
                },
            )
            db.session.commit()
            return jsonify({"id": str(mid)}), 201

    db.session.execute(
        text(
            "INSERT INTO meals (id, datetime, description, type_id, user_id) VALUES (:id, :dt, :description, :type_id, :user_id)"
        ),
        {
            "id": str(meal_id),
            "dt": parsed,
            "description": description,
            "type_id": str(type_id),
            "user_id": str(user_id),
        },
    )

    db.session.commit()
    return jsonify({"id": str(meal_id)}), 201


@bp.route("/meal", methods=["DELETE"])
@jwt_required()
def delete_meal():
    mid = request.args.get("id")
    user_id = get_jwt_identity()
    if not mid:
        return jsonify({"msg": "id required"}), 400

    result = db.session.execute(
        text("SELECT id, user_id FROM meals WHERE id = :meal_id"),
        {"meal_id": str(mid)},
    ).fetchone()
    if not result:
        return jsonify({"msg": "not found"}), 404
    if str(result.user_id) != str(user_id):
        return jsonify({"msg": "forbidden"}), 403

    db.session.execute(
        text("DELETE FROM meals WHERE id = :meal_id"), {"meal_id": str(mid)}
    )
    db.session.commit()
    return jsonify({"msg": "deleted"}), 200


@bp.route("/meal", methods=["GET"])
def get_meal():
    mid = request.args.get("id")
    if not mid:
        return jsonify({"msg": "id required"}), 400

    selected_columns = ["id", "datetime", "description", "type_id", "user_id"]
    if meal_supports_split_fields():
        selected_columns.extend(["antonio", "annalisa"])
    row = db.session.execute(
        text(f"SELECT {', '.join(selected_columns)} FROM meals WHERE id = :meal_id"),
        {"meal_id": str(mid)},
    ).fetchone()
    if not row:
        return jsonify({"msg": "not found"}), 404
    return jsonify(serialize_meal_row(row))


@bp.route("/meals", methods=["GET"])
@jwt_required(optional=True)
def list_meals():
    frm = request.args.get("from")
    to = request.args.get("to")
    type_id = request.args.get("type")
    current_user_id = get_jwt_identity()
    explicit_user_id = request.args.get("user_id")
    scope = request.args.get("scope", "all")

    columns = ["id", "datetime", "description", "type_id", "user_id"]
    if meal_supports_split_fields():
        columns.extend(["antonio", "annalisa"])

    sql = "SELECT " + ", ".join(f"meals.{column}" for column in columns) + " FROM meals"
    params = {}
    clauses = []

    if explicit_user_id:
        clauses.append("meals.user_id = :user_id")
        params["user_id"] = str(explicit_user_id)
    elif current_user_id and scope == "mine":
        clauses.append("meals.user_id = :user_id")
        params["user_id"] = str(current_user_id)

    if frm:
        try:
            frm_dt = normalize_datetime(frm)
            clauses.append("meals.datetime >= :from_dt")
            params["from_dt"] = frm_dt
        except Exception:
            return jsonify({"msg": "invalid from datetime"}), 400
    if to:
        try:
            to_dt = normalize_datetime(to)
            clauses.append("meals.datetime <= :to_dt")
            params["to_dt"] = to_dt
        except Exception:
            return jsonify({"msg": "invalid to datetime"}), 400
    if type_id:
        try:
            clauses.append("meals.type_id = :type_id")
            params["type_id"] = str(type_id)
        except Exception:
            return jsonify({"msg": "invalid type id"}), 400

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY meals.datetime"

    rows = db.session.execute(text(sql), params).fetchall()
    return jsonify([serialize_meal_row(row) for row in rows])


@bp.route("/copy_meals", methods=["POST"])
@jwt_required()
def copy_meals():
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

    selected_columns = ["id", "datetime", "description", "type_id", "user_id"]
    if meal_supports_split_fields():
        selected_columns.extend(["antonio", "annalisa"])
    rows = db.session.execute(
        text(
            f"SELECT {', '.join(selected_columns)} FROM meals WHERE user_id = :user_id AND datetime >= :s_from AND datetime <= :s_to"
        ),
        {"user_id": str(user_id), "s_from": s_from, "s_to": s_to},
    ).fetchall()
    if not rows:
        return jsonify({"copied": 0}), 200

    delta = d_from - s_from
    copied = 0
    for row in rows:
        record = row._mapping if hasattr(row, "_mapping") else row
        new_dt = record["datetime"] + delta
        if new_dt < d_from or new_dt > d_to:
            continue

        fields = {
            "description": normalize_meal_text(record.get("description")),
            "antonio": normalize_meal_text(record.get("antonio")),
            "annalisa": normalize_meal_text(record.get("annalisa")),
        }

        if meal_supports_split_fields():
            db.session.execute(
                text(
                    "INSERT INTO meals (id, datetime, description, antonio, annalisa, type_id, user_id) VALUES (:id, :dt, :description, :antonio, :annalisa, :type_id, :user_id)"
                ),
                {
                    "id": str(uuid4()),
                    "dt": new_dt,
                    "description": fields["description"],
                    "antonio": fields["antonio"],
                    "annalisa": fields["annalisa"],
                    "type_id": str(record["type_id"]),
                    "user_id": str(user_id),
                },
            )
        else:
            db.session.execute(
                text(
                    "INSERT INTO meals (id, datetime, description, type_id, user_id) VALUES (:id, :dt, :description, :type_id, :user_id)"
                ),
                {
                    "id": str(uuid4()),
                    "dt": new_dt,
                    "description": fields["description"],
                    "type_id": str(record["type_id"]),
                    "user_id": str(user_id),
                },
            )
        copied += 1

    db.session.commit()
    return jsonify({"copied": copied}), 201
