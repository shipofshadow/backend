from flask import jsonify, request, Blueprint
from db import get_connection
from services.admin.manage_periods import get_active_period

scholarships_bp = Blueprint('scholarships', __name__, url_prefix='/api/scholarships')

@scholarships_bp.route('/', methods=['GET'])
def get_scholarships():
    db = get_connection()
    cursor = db.cursor()
    try:
        cursor.execute("""
                       SELECT *
                       FROM scholarships
                        INNER JOIN scholarship_rules ON scholarships.id = scholarship_rules.scholarship_id
                       WHERE scholarships.is_active = 1;
                       """)
        rows = cursor.fetchall()

        scholarships = []
        for row in rows:
            scholarships.append({
                "scholarship_id": row["scholarship_id"],
                "name": row["name"],
                "description": row["description"],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                "rules": {
                    "rule_id": row["id"],
                    "min_gwa": row["min_gwa"],
                    "max_income": row["max_income"],
                    "ip_required": bool(row["ip_required"]) if row["ip_required"] is not None else None
                } if row["rule_id"] else None
            })

        return jsonify(scholarships), 200

    except Exception as e:
        print(f"[ERROR] get_scholarships: {e}")
        return jsonify({"error": "Failed to fetch scholarships"}), 500

    finally:
        cursor.close()
        db.close()

