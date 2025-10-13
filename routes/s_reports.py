import pymysql
from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from decimal import Decimal
import io

from pymysql import Error
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import json
from storage import get_connection

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')


def decimal_to_float(obj):
    """Convert Decimal objects to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


# Filter Options Endpoints
@reports_bp.route('/academic-years', methods=['GET'])
def get_academic_years():
    """Get all academic years for filter dropdown"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT id, year_start, year_end
                       FROM academic_years
                       WHERE deleted_at IS NULL
                       ORDER BY year_start DESC
                       """)
        years = cursor.fetchall()
        return jsonify(years), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/semesters', methods=['GET'])
def get_semesters():
    """Get all semesters for filter dropdown"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT s.id, s.name, ay.year_start, ay.year_end
                       FROM semesters s
                                JOIN academic_years ay ON s.academic_year_id = ay.id
                       WHERE s.deleted_at IS NULL
                       ORDER BY ay.year_start DESC, s.name
                       """)
        semesters = cursor.fetchall()
        return jsonify(semesters), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/campuses', methods=['GET'])
def get_campuses():
    """Get all campuses for filter dropdown"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT campus_id, name FROM campuses ORDER BY name")
        campuses = cursor.fetchall()
        return jsonify(campuses), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500

def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_dict_cursor(conn):
    """Helper to get dict cursor"""
    return conn.cursor(pymysql.cursors.DictCursor)

# Main Scholarship Summary Report
@reports_bp.route('/scholarship-summary', methods=['GET'])
def get_scholarship_summary():
    """
    Generate comprehensive scholarship summary report
    Query params: academic_year_id, semester_id, campus_id (optional filters)
    """
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = get_dict_cursor(conn)
    try:
        academic_year_id = request.args.get('academic_year_id', type=int)
        semester_id = request.args.get('semester_id', type=int)
        campus_id = request.args.get('campus_id', type=int)

        filter_conditions = ["a.deleted_at IS NULL"]
        filter_params = []

        if academic_year_id:
            filter_conditions.append("s.academic_year_id = %s")
            filter_params.append(academic_year_id)

        if semester_id:
            filter_conditions.append("a.semester_id = %s")
            filter_params.append(semester_id)

        if campus_id:
            filter_conditions.append("ei.campus_id = %s")
            filter_params.append(campus_id)

        filter_where = " AND ".join(filter_conditions)

        # Overall summary
        overall_query = f"""
            SELECT 
                COUNT(DISTINCT sch.id) AS total_scholarships,
                COUNT(DISTINCT a.id) AS total_applications,
                COUNT(DISTINCT CASE WHEN a.status = 'approved' THEN a.id END) AS total_approved_applications,
                COUNT(DISTINCT CASE WHEN ss.status IN ('selected','awarded') THEN a.student_id END) AS total_awarded_students,
                COALESCE(SUM(CASE WHEN ss.status IN ('selected','awarded') THEN ss.awarded_amount ELSE 0 END),0) AS total_grant_released
            FROM scholarships sch
            LEFT JOIN scholarship_selections ss ON sch.id = ss.scholarship_id
            LEFT JOIN applications a ON ss.application_id = a.id
            LEFT JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
        """
        cursor.execute(overall_query, filter_params)
        overall_summary = cursor.fetchone() or {}

        # Per-scholarship summary
        scholarship_query = f"""
            SELECT 
                sch.id,
                sch.name,
                sch.description,
                COUNT(DISTINCT a.id) AS total_applications,
                COUNT(DISTINCT CASE WHEN ss.status IN ('selected','awarded') THEN ss.application_id END) AS total_awarded,
                COALESCE(AVG(e.gwa), 0) AS avg_gwa,
                COALESCE(AVG((fb.father_income + fb.mother_income)/2), 0) AS avg_income,
                COALESCE(SUM(ss.awarded_amount), 0) AS total_grant_amount
            FROM scholarships sch
            LEFT JOIN scholarship_selections ss ON sch.id = ss.scholarship_id
            LEFT JOIN applications a ON ss.application_id = a.id
            LEFT JOIN evaluations e ON a.id = e.application_id
            LEFT JOIN family_background fb ON a.student_id = fb.student_id
            LEFT JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
            GROUP BY sch.id
            ORDER BY total_awarded DESC
        """
        cursor.execute(scholarship_query, filter_params)
        scholarships_raw = cursor.fetchall()

        scholarships = []
        for sch in scholarships_raw:
            award_rate = (
                (sch['total_awarded'] / sch['total_applications']) * 100
                if sch['total_applications'] > 0 else 0
            )

            # top 3 campus breakdown
            campus_query = f"""
                SELECT c.name AS campus_name, COUNT(DISTINCT ss.application_id) AS count
                FROM scholarship_selections ss
                JOIN applications a ON ss.application_id = a.id
                JOIN education_info ei ON a.student_id = ei.student_id
                JOIN campuses c ON ei.campus_id = c.campus_id
                JOIN semesters s ON a.semester_id = s.id
                WHERE ss.scholarship_id = %s AND ss.status IN ('selected','awarded')
                    AND {filter_where}
                GROUP BY c.campus_id
                ORDER BY count DESC
                LIMIT 3
            """
            cursor.execute(campus_query, [sch['id']] + filter_params)
            top_campuses = cursor.fetchall()

            # top 3 departments
            dept_query = f"""
                SELECT d.name AS department_name, COUNT(DISTINCT ss.application_id) AS count
                FROM scholarship_selections ss
                JOIN applications a ON ss.application_id = a.id
                JOIN education_info ei ON a.student_id = ei.student_id
                JOIN departments d ON ei.department_id = d.department_id
                JOIN semesters s ON a.semester_id = s.id
                WHERE ss.scholarship_id = %s AND ss.status IN ('selected','awarded')
                    AND {filter_where}
                GROUP BY d.department_id
                ORDER BY count DESC
                LIMIT 3
            """
            cursor.execute(dept_query, [sch['id']] + filter_params)
            top_departments = cursor.fetchall()

            scholarships.append({
                'id': sch['id'],
                'name': sch['name'],
                'description': sch['description'],
                'total_awarded': sch['total_awarded'],
                'total_applications': sch['total_applications'],
                'award_rate': award_rate,
                'avg_gwa': float(sch['avg_gwa']),
                'avg_income': float(sch['avg_income']),
                'total_grant_amount': float(sch['total_grant_amount']),
                'top_campuses': top_campuses,
                'top_departments': top_departments
            })

        return jsonify({
            'overall_summary': overall_summary,
            'scholarships': scholarships
        }), 200

    except Error as e:
        print("Error in scholarship summary:", e)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# Trends Endpoint
@reports_bp.route('/trends', methods=['GET'])
def get_trends():
    """Get application vs award trends over semesters"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        academic_year_id = request.args.get('academic_year_id', type=int)
        campus_id = request.args.get('campus_id', type=int)

        filter_conditions = ["a.deleted_at IS NULL"]
        filter_params = []

        if academic_year_id:
            filter_conditions.append("s.academic_year_id = %s")
            filter_params.append(academic_year_id)

        if campus_id:
            filter_conditions.append("ei.campus_id = %s")
            filter_params.append(campus_id)

        filter_where = " AND ".join(filter_conditions)

        query = f"""
            SELECT 
                CONCAT(s.name, ' ', ay.year_start, '-', ay.year_end) as semester,
                COUNT(DISTINCT a.id) as applications,
                COUNT(DISTINCT CASE WHEN ss.status IN ('selected', 'awarded') THEN ss.application_id END) as awards
            FROM applications a
            JOIN semesters s ON a.semester_id = s.id
            JOIN academic_years ay ON s.academic_year_id = ay.id
            LEFT JOIN scholarship_selections ss ON a.id = ss.application_id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
            GROUP BY s.id
            ORDER BY ay.year_start, s.name
        """

        cursor.execute(query, filter_params)
        trends = cursor.fetchall()

        return jsonify(trends), 200

    except Error as e:
        return jsonify({'error': str(e)}), 500


# Demographics Endpoint
@reports_bp.route('/demographics', methods=['GET'])
def get_demographics():
    """Get demographic breakdown of awarded students"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        academic_year_id = request.args.get('academic_year_id', type=int)
        semester_id = request.args.get('semester_id', type=int)
        campus_id = request.args.get('campus_id', type=int)

        filter_conditions = ["a.deleted_at IS NULL", "ss.status IN ('selected', 'awarded')"]
        filter_params = []

        if academic_year_id:
            filter_conditions.append("s.academic_year_id = %s")
            filter_params.append(academic_year_id)

        if semester_id:
            filter_conditions.append("a.semester_id = %s")
            filter_params.append(semester_id)

        if campus_id:
            filter_conditions.append("ei.campus_id = %s")
            filter_params.append(campus_id)

        filter_where = " AND ".join(filter_conditions)

        # Gender breakdown
        gender_query = f"""
            SELECT 
                st.gender as name,
                COUNT(DISTINCT a.student_id) as count
            FROM scholarship_selections ss
            JOIN applications a ON ss.application_id = a.id
            JOIN students st ON a.student_id = st.user_id
            JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
            GROUP BY st.gender
        """
        cursor.execute(gender_query, filter_params)
        by_gender = cursor.fetchall()

        # Average age
        age_query = f"""
            SELECT 
                AVG(YEAR(CURDATE()) - YEAR(st.birth_date)) as avg_age
            FROM scholarship_selections ss
            JOIN applications a ON ss.application_id = a.id
            JOIN students st ON a.student_id = st.user_id
            JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
        """
        cursor.execute(age_query, filter_params)
        age_result = cursor.fetchone()

        # 4Ps members
        fourps_query = f"""
            SELECT 
                COUNT(DISTINCT a.student_id) as fourps_count
            FROM scholarship_selections ss
            JOIN applications a ON ss.application_id = a.id
            JOIN family_background fb ON a.student_id = fb.student_id
            JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where} AND fb.is_4ps_member = 1
        """
        cursor.execute(fourps_query, filter_params)
        fourps_result = cursor.fetchone()

        # Indigenous Peoples
        ip_query = f"""
            SELECT 
                COUNT(DISTINCT a.student_id) as ip_count
            FROM scholarship_selections ss
            JOIN applications a ON ss.application_id = a.id
            JOIN family_background fb ON a.student_id = fb.student_id
            JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where} 
                AND fb.ip_affiliation IS NOT NULL 
                AND fb.ip_affiliation != ''
        """
        cursor.execute(ip_query, filter_params)
        ip_result = cursor.fetchone()

        # OFW dependents
        ofw_query = f"""
            SELECT 
                COUNT(DISTINCT a.student_id) as ofw_count
            FROM scholarship_selections ss
            JOIN applications a ON ss.application_id = a.id
            JOIN family_background fb ON a.student_id = fb.student_id
            JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where} 
                AND (LOWER(fb.father_occupation) LIKE '%ofw%' 
                     OR LOWER(fb.mother_occupation) LIKE '%ofw%')
        """
        cursor.execute(ofw_query, filter_params)
        ofw_result = cursor.fetchone()

        demographics = {
            'by_gender': by_gender,
            'avg_age': float(age_result['avg_age']) if age_result['avg_age'] else 0,
            'fourps_count': fourps_result['fourps_count'],
            'ip_count': ip_result['ip_count'],
            'ofw_count': ofw_result['ofw_count']
        }

        return jsonify(demographics), 200

    except Error as e:
        return jsonify({'error': str(e)}), 500


# PDF Export Endpoint
@reports_bp.route('/export-pdf', methods=['GET'])
def export_pdf():
    """Generate and download PDF report"""
    conn = get_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Create PDF in memory
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                                topMargin=72, bottomMargin=18)

        # Container for PDF elements
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=12
        )

        # Add title
        title = Paragraph("Scholarship Summary Report", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Add generation date
        date_text = Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal'])
        elements.append(date_text)
        elements.append(Spacer(1, 20))

        # Fetch data (reuse logic from scholarship-summary endpoint)
        cursor = conn.cursor()

        # Get filters
        academic_year_id = request.args.get('academic_year_id', type=int)
        semester_id = request.args.get('semester_id', type=int)
        campus_id = request.args.get('campus_id', type=int)

        filter_conditions = ["a.deleted_at IS NULL"]
        filter_params = []

        if academic_year_id:
            filter_conditions.append("s.academic_year_id = %s")
            filter_params.append(academic_year_id)

        if semester_id:
            filter_conditions.append("a.semester_id = %s")
            filter_params.append(semester_id)

        if campus_id:
            filter_conditions.append("ei.campus_id = %s")
            filter_params.append(campus_id)

        filter_where = " AND ".join(filter_conditions)

        # Get overall summary
        overall_query = f"""
            SELECT 
                COUNT(DISTINCT sch.id) as total_scholarships,
                COUNT(DISTINCT a.id) as total_applications,
                COUNT(DISTINCT CASE WHEN ss.status IN ('selected', 'awarded') THEN a.student_id END) as total_awarded_students,
                COALESCE(SUM(CASE WHEN ss.status IN ('selected', 'awarded') THEN ss.awarded_amount ELSE 0 END), 0) as total_grant_released
            FROM scholarships sch
            LEFT JOIN scholarship_selections ss ON sch.id = ss.scholarship_id
            LEFT JOIN applications a ON ss.application_id = a.id
            LEFT JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
        """

        cursor.execute(overall_query, filter_params)
        overall = cursor.fetchone()

        # Overall Summary Section
        elements.append(Paragraph("Overall Summary", heading_style))
        summary_data = [
            ['Metric', 'Value'],
            ['Total Scholarships', str(overall['total_scholarships'])],
            ['Total Applications', str(overall['total_applications'])],
            ['Total Awarded Students', str(overall['total_awarded_students'])],
            ['Total Grant Released', f"₱{float(overall['total_grant_released']):,.2f}"]
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # Get scholarship details
        scholarship_query = f"""
            SELECT 
                sch.name,
                COUNT(DISTINCT CASE WHEN ss.status IN ('selected', 'awarded') THEN ss.application_id END) as total_awarded,
                COALESCE(AVG(CASE WHEN ss.status IN ('selected', 'awarded') THEN e.gwa END), 0) as avg_gwa,
                COALESCE(SUM(CASE WHEN ss.status IN ('selected', 'awarded') THEN ss.awarded_amount ELSE 0 END), 0) as total_grant
            FROM scholarships sch
            LEFT JOIN scholarship_selections ss ON sch.id = ss.scholarship_id
            LEFT JOIN applications a ON ss.application_id = a.id
            LEFT JOIN evaluations e ON a.id = e.application_id
            LEFT JOIN semesters s ON a.semester_id = s.id
            LEFT JOIN education_info ei ON a.student_id = ei.student_id
            WHERE {filter_where}
            GROUP BY sch.id
            HAVING total_awarded > 0
            ORDER BY total_awarded DESC
        """

        cursor.execute(scholarship_query, filter_params)
        scholarships = cursor.fetchall()

        # Scholarships Section
        elements.append(PageBreak())
        elements.append(Paragraph("Scholarship Details", heading_style))

        if scholarships:
            sch_data = [['Scholarship Name', 'Awarded', 'Avg GWA', 'Total Grant']]
            for sch in scholarships:
                sch_data.append([
                    sch['name'][:40] + '...' if len(sch['name']) > 40 else sch['name'],
                    str(sch['total_awarded']),
                    f"{float(sch['avg_gwa']):.2f}",
                    f"₱{float(sch['total_grant']):,.2f}"
                ])

            sch_table = Table(sch_data, colWidths=[3 * inch, 1 * inch, 1 * inch, 1.5 * inch])
            sch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 9)
            ]))

            elements.append(sch_table)

        # Build PDF
        doc.build(elements)

        # Prepare response
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'scholarship_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        )

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()