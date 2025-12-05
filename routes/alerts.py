"""
Scholarship Alerts Routes

Endpoints for managing scholarship match alerts:
- POST /api/scholarships/{id}/trigger-matching - Admin: trigger matching for a scholarship
- GET /api/alerts/my-scholarship-matches - Student: get their scholarship match alerts
- PATCH /api/alerts/{id}/mark-read - Student: mark an alert as read
"""

import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from services.scholarship_alert_service import (
    trigger_scholarship_matching,
    get_student_scholarship_alerts,
    mark_alert_read
)
from utils.decorator import admin_required

logger = logging.getLogger(__name__)

alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')


@alerts_bp.route('/my-scholarship-matches', methods=['GET'])
@jwt_required()
def get_my_scholarship_matches():
    """
    Get scholarship match alerts for the authenticated student.
    ---
    tags:
      - Alerts
    security:
      - jwt: []
    parameters:
      - name: unread_only
        in: query
        type: boolean
        required: false
        description: If true, only return unread alerts
      - name: page
        in: query
        type: integer
        required: false
        description: Page number for pagination
      - name: limit
        in: query
        type: integer
        required: false
        description: Results per page
    responses:
      200:
        description: List of scholarship match alerts
        schema:
          type: object
          properties:
            unread_count:
              type: integer
            alerts:
              type: array
              items:
                type: object
            pagination:
              type: object
      500:
        description: Internal server error
    """
    try:
        student_id = int(get_jwt_identity())
        
        # Parse query parameters
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        page = max(1, int(request.args.get('page', 1)))
        limit = min(100, max(1, int(request.args.get('limit', 20))))
        
        result = get_student_scholarship_alerts(
            student_id=student_id,
            unread_only=unread_only,
            page=page,
            limit=limit
        )
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({"error": "Invalid parameters"}), 400
    except Exception as e:
        logger.error(f"Error getting scholarship alerts: {e}")
        return jsonify({"error": "Internal server error"}), 500


@alerts_bp.route('/<int:alert_id>/mark-read', methods=['PATCH'])
@jwt_required()
def mark_alert_as_read(alert_id):
    """
    Mark a specific scholarship alert as read.
    ---
    tags:
      - Alerts
    security:
      - jwt: []
    parameters:
      - name: alert_id
        in: path
        type: integer
        required: true
        description: The alert ID to mark as read
    responses:
      200:
        description: Alert marked as read
      404:
        description: Alert not found
      500:
        description: Internal server error
    """
    try:
        student_id = int(get_jwt_identity())
        
        success = mark_alert_read(alert_id, student_id)
        
        if success:
            return jsonify({"message": "Alert marked as read"}), 200
        else:
            return jsonify({"error": "Alert not found or already read"}), 404
            
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        return jsonify({"error": "Internal server error"}), 500
