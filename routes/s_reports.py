from flask import Blueprint, jsonify, request
from datetime import datetime
from pymysql import Error
from storage import get_connection

reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')



def execute_query(query, params=None, fetch_one=False):
    """Execute a query and return results"""
    conn = get_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(query, params or ())

        if fetch_one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()

        cursor.close()
        conn.close()
        return result
    except Error as e:
        print(f"Error executing query: {e}")
        if conn:
            conn.close()
        return None


# ============================================================================
# FILTER HELPER
# ============================================================================
def build_filter_conditions(filters):
    """Build SQL WHERE conditions based on filters"""
    conditions = []
    params = []

    # Academic Year filter
    if filters.get('academicYear') and filters['academicYear'] != 'All':
        year_parts = filters['academicYear'].split('-')
        conditions.append("ay.year_start = %s AND ay.year_end = %s")
        params.extend([int(year_parts[0]), int(year_parts[1])])

    # Semester filter
    if filters.get('semester') and filters['semester'] != 'All':
        conditions.append("sem.name = %s")
        params.append(filters['semester'])

    # Campus filter
    if filters.get('campus') and filters['campus'] != 'All':
        conditions.append("c.name = %s")
        params.append(filters['campus'])

    # Department filter
    if filters.get('department') and filters['department'] != 'All':
        conditions.append("d.name = %s")
        params.append(filters['department'])

    # Course filter
    if filters.get('course') and filters['course'] != 'All':
        conditions.append("co.name LIKE %s")
        params.append(f"%{filters['course']}%")

    # Scholarship filter
    if filters.get('scholarship') and filters['scholarship'] != 'All':
        conditions.append("sch.name LIKE %s")
        params.append(f"%{filters['scholarship']}%")

    # Status filter
    if filters.get('status') and filters['status'] != 'All':
        status_map = {
            'Pending': 'pending',
            'Approved': 'approved',
            'Denied': 'denied',
            'Evaluated': 'evaluated'
        }
        conditions.append("app.status = %s")
        params.append(status_map.get(filters['status'], filters['status'].lower()))

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    return where_clause, params


# ============================================================================
# DASHBOARD SUMMARY ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/summary', methods=['GET'])
def get_dashboard_summary():
    """Get key metrics for the dashboard"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Active Scholarships
    active_scholarships_query = """
                                SELECT COUNT(*) as count
                                FROM scholarships
                                WHERE is_active = 1 AND deleted_at IS NULL \
                                """
    active_scholarships = execute_query(active_scholarships_query, fetch_one=True)

    # Total Applications
    total_applications_query = f"""
        SELECT COUNT(DISTINCT app.id) as count
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    total_applications = execute_query(total_applications_query, params, fetch_one=True)

    # Approved Applications
    approved_applications_query = f"""
        SELECT COUNT(DISTINCT app.id) as count
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND app.status = 'approved' AND {where_clause}
    """
    approved_applications = execute_query(approved_applications_query, params, fetch_one=True)

    # Average GWA
    avg_gwa_query = f"""
        SELECT AVG(e.gwa) as avg_gwa
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND app.status = 'approved' AND {where_clause}
    """
    avg_gwa = execute_query(avg_gwa_query, params, fetch_one=True)

    # Average Income
    avg_income_query = f"""
        SELECT AVG(e.income) as avg_income
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    avg_income = execute_query(avg_income_query, params, fetch_one=True)

    # Top Campus
    top_campus_query = f"""
        SELECT c.name, 
               COUNT(app.id) as total_apps,
               SUM(CASE WHEN app.status = 'approved' THEN 1 ELSE 0 END) as approved,
               ROUND((SUM(CASE WHEN app.status = 'approved' THEN 1 ELSE 0 END) * 100.0 / COUNT(app.id)), 2) as approval_rate
        FROM applications app
        JOIN education_info ei ON app.student_id = ei.student_id
        JOIN campuses c ON ei.campus_id = c.campus_id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY c.name
        ORDER BY approved DESC, approval_rate DESC
        LIMIT 1
    """
    top_campus = execute_query(top_campus_query, params, fetch_one=True)

    return jsonify({
        'metrics': {
            'activeScholarships': active_scholarships['count'] if active_scholarships else 0,
            'totalApplications': total_applications['count'] if total_applications else 0,
            'approvedApplications': approved_applications['count'] if approved_applications else 0,
            'avgGWA': round(avg_gwa['avg_gwa'], 2) if avg_gwa and avg_gwa['avg_gwa'] else 0,
            'avgIncome': round(avg_income['avg_income'], 2) if avg_income and avg_income['avg_income'] else 0,
            'topCampus': top_campus['name'] if top_campus else 'N/A',
            'topCampusRate': round(top_campus['approval_rate'], 2) if top_campus else 0
        }
    })


# ============================================================================
# SCHOLARSHIPS DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/scholarships', methods=['GET'])
def get_scholarships_data():
    """Get scholarship-related data for charts"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Scholarship Distribution (Active vs Inactive)
    distribution_query = """
                         SELECT SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active, \
                                SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
                         FROM scholarships
                         WHERE deleted_at IS NULL \
                         """
    distribution = execute_query(distribution_query, fetch_one=True)

    # Applications per Scholarship
    applications_per_scholarship_query = f"""
        SELECT 
            sch.name,
            COUNT(DISTINCT rs.application_id) as applications
        FROM scholarships sch
        LEFT JOIN recommended_scholarships rs ON sch.id = rs.scholarship_id
        LEFT JOIN applications app ON rs.application_id = app.id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        WHERE sch.deleted_at IS NULL 
        AND (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY sch.id, sch.name
        ORDER BY applications DESC
        LIMIT 10
    """
    applications_per_scholarship = execute_query(applications_per_scholarship_query, params)

    # Status Distribution per Scholarship
    status_distribution_query = f"""
        SELECT 
            sch.name,
            SUM(CASE WHEN app.status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN app.status = 'denied' THEN 1 ELSE 0 END) as denied,
            SUM(CASE WHEN app.status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM scholarships sch
        LEFT JOIN recommended_scholarships rs ON sch.id = rs.scholarship_id
        LEFT JOIN applications app ON rs.application_id = app.id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        WHERE sch.deleted_at IS NULL 
        AND (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY sch.id, sch.name
        HAVING (approved + denied + pending) > 0
        ORDER BY (approved + denied + pending) DESC
        LIMIT 10
    """
    status_distribution = execute_query(status_distribution_query, params)

    # Top Scholarships with Details
    top_scholarships_query = f"""
        SELECT 
            sch.name,
            COUNT(DISTINCT rs.application_id) as applications,
            AVG(e.gwa) as avg_gwa,
            AVG(e.income) as avg_income,
            ROUND((SUM(CASE WHEN app.status = 'approved' THEN 1 ELSE 0 END) * 100.0 / 
                   NULLIF(COUNT(DISTINCT rs.application_id), 0)), 2) as approval_rate,
            SUM(COALESCE(ss.awarded_amount, 0)) as total_awarded
        FROM scholarships sch
        LEFT JOIN recommended_scholarships rs ON sch.id = rs.scholarship_id
        LEFT JOIN applications app ON rs.application_id = app.id
        LEFT JOIN evaluations e ON app.id = e.application_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id AND sch.id = ss.scholarship_id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        WHERE sch.deleted_at IS NULL 
        AND (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY sch.id, sch.name
        HAVING applications > 0
        ORDER BY applications DESC, approval_rate DESC
        LIMIT 10
    """
    top_scholarships = execute_query(top_scholarships_query, params)

    # Least Utilized Scholarships
    least_utilized_query = f"""
        SELECT 
            sch.name,
            COUNT(DISTINCT rs.application_id) as applications,
            AVG(e.gwa) as avg_gwa,
            AVG(e.income) as avg_income
        FROM scholarships sch
        LEFT JOIN recommended_scholarships rs ON sch.id = rs.scholarship_id
        LEFT JOIN applications app ON rs.application_id = app.id
        LEFT JOIN evaluations e ON app.id = e.application_id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        WHERE sch.is_active = 1 
        AND sch.deleted_at IS NULL
        AND (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY sch.id, sch.name
        ORDER BY applications ASC
        LIMIT 10
    """
    least_utilized = execute_query(least_utilized_query, params)

    return jsonify({
        'distribution': {
            'active': distribution['active'] if distribution else 0,
            'inactive': distribution['inactive'] if distribution else 0
        },
        'applicationsPerScholarship': applications_per_scholarship or [],
        'statusDistribution': status_distribution or [],
        'topScholarships': top_scholarships or [],
        'leastUtilized': least_utilized or []
    })


# ============================================================================
# CAMPUSES DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/campuses', methods=['GET'])
def get_campuses_data():
    """Get campus and department data"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Applications by Campus
    campus_query = f"""
        SELECT 
            c.name,
            COUNT(DISTINCT app.id) as applications
        FROM campuses c
        LEFT JOIN education_info ei ON c.campus_id = ei.campus_id
        LEFT JOIN applications app ON ei.student_id = app.student_id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY c.campus_id, c.name
        ORDER BY applications DESC
    """
    campuses = execute_query(campus_query, params)

    # Applications by Department
    department_query = f"""
        SELECT 
            d.name,
            COUNT(DISTINCT app.id) as applications
        FROM departments d
        LEFT JOIN education_info ei ON d.department_id = ei.department_id
        LEFT JOIN applications app ON ei.student_id = app.student_id
        LEFT JOIN semesters sem ON app.semester_id = sem.id
        LEFT JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE (app.id IS NULL OR (app.deleted_at IS NULL AND {where_clause}))
        GROUP BY d.department_id, d.name
        ORDER BY applications DESC
    """
    departments = execute_query(department_query, params)

    return jsonify({
        'campuses': campuses or [],
        'departments': departments or []
    })


# ============================================================================
# FUZZY EVALUATION DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/fuzzy', methods=['GET'])
def get_fuzzy_data():
    """Get fuzzy logic evaluation data"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Classification Distribution
    classification_query = f"""
        SELECT 
            e.classification,
            COUNT(*) as count
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY e.classification
    """
    classifications = execute_query(classification_query, params)

    # GWA vs Income Scatter Data
    scatter_query = f"""
        SELECT 
            e.gwa,
            e.income,
            e.score,
            e.classification
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    scatter_data = execute_query(scatter_query, params)

    # Average Score Trend (by semester)
    trend_query = f"""
        SELECT 
            CONCAT(ay.year_start, '-', ay.year_end) as academic_year,
            sem.name as semester,
            AVG(e.score) as avg_score
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY ay.year_start, ay.year_end, sem.name
        ORDER BY ay.year_start, 
                 CASE sem.name 
                     WHEN '1st Semester' THEN 1 
                     WHEN '2nd Semester' THEN 2 
                     ELSE 3 
                 END
    """
    score_trend = execute_query(trend_query, params)

    return jsonify({
        'classifications': classifications or [],
        'scatterData': scatter_data or [],
        'scoreTrend': score_trend or []
    })


# ============================================================================
# TIME SERIES DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/timeseries', methods=['GET'])
def get_timeseries_data():
    """Get time series analysis data"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Monthly Applications Trend
    monthly_query = f"""
        SELECT 
            MONTH(app.submitted_at) as month,
            YEAR(app.submitted_at) as year,
            COUNT(*) as applications
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY YEAR(app.submitted_at), MONTH(app.submitted_at)
        ORDER BY year, month
    """
    monthly_data = execute_query(monthly_query, params)

    # Yearly Scholarships Awarded
    yearly_query = f"""
        SELECT 
            CONCAT(ay.year_start, '-', ay.year_end) as academic_year,
            COUNT(DISTINCT app.id) as total_applications,
            COUNT(DISTINCT ss.id) as awarded
        FROM academic_years ay
        LEFT JOIN semesters sem ON ay.id = sem.academic_year_id
        LEFT JOIN applications app ON sem.id = app.semester_id AND app.deleted_at IS NULL
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE (app.id IS NULL OR {where_clause})
        GROUP BY ay.year_start, ay.year_end
        ORDER BY ay.year_start
    """
    yearly_data = execute_query(yearly_query, params)

    # Application Status Over Time
    status_timeline_query = f"""
        SELECT 
            DATE_FORMAT(app.submitted_at, '%%Y-%%m') as month,
            SUM(CASE WHEN app.status = 'pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN app.status = 'approved' THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN app.status = 'evaluated' THEN 1 ELSE 0 END) as evaluated,
            SUM(CASE WHEN app.status = 'denied' THEN 1 ELSE 0 END) as denied
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY DATE_FORMAT(app.submitted_at, '%%Y-%%m')
        ORDER BY month
    """
    status_timeline = execute_query(status_timeline_query, params)

    return jsonify({
        'monthly': monthly_data or [],
        'yearly': yearly_data or [],
        'statusTimeline': status_timeline or []
    })


# ============================================================================
# DEMOGRAPHICS DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/demographics', methods=['GET'])
def get_demographics_data():
    """Get applicant demographics data"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Gender Distribution
    gender_query = f"""
        SELECT 
            s.gender,
            COUNT(DISTINCT app.id) as count
        FROM students s
        JOIN applications app ON s.user_id = app.student_id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY s.gender
    """
    gender_data = execute_query(gender_query, params)

    # Year Level Distribution
    year_level_query = f"""
        SELECT 
            ei.year_level,
            COUNT(DISTINCT app.id) as count
        FROM education_info ei
        JOIN applications app ON ei.student_id = app.student_id
        JOIN semesters sem ON app.semester_id = sem.id AND ei.semester_id = app.semester_id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY ei.year_level
        ORDER BY ei.year_level
    """
    year_level_data = execute_query(year_level_query, params)

    # Income Bracket Distribution
    income_query = f"""
        SELECT 
            CASE 
                WHEN e.income <= 10000 THEN '₱0-10k'
                WHEN e.income <= 20000 THEN '₱10k-20k'
                WHEN e.income <= 30000 THEN '₱20k-30k'
                WHEN e.income <= 40000 THEN '₱30k-40k'
                ELSE '₱40k+'
            END as income_bracket,
            COUNT(DISTINCT app.id) as count
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id
        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
        GROUP BY income_bracket
        ORDER BY MIN(e.income)
    """
    income_data = execute_query(income_query, params)

    # Qualification Factors (for radar chart)
    qualification_query = f"""
        SELECT 
            SUM(CASE WHEN e.gwa <= 1.5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as high_gwa,
            SUM(CASE WHEN e.income <= 15000 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as low_income,
            SUM(CASE WHEN fb.is_4ps_member = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as fourps,
            SUM(CASE WHEN fb.ip_affiliation IS NOT NULL AND fb.ip_affiliation != '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as ip,
            SUM(CASE WHEN fb.father_occupation = 'ofw' OR fb.mother_occupation = 'ofw' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as ofw
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN family_background fb ON app.student_id = fb.student_id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    qualification_data = execute_query(qualification_query, params, fetch_one=True)

    return jsonify({
        'gender': gender_data or [],
        'yearLevel': year_level_data or [],
        'income': income_data or [],
        'qualificationFactors': qualification_data or {}
    })


# ============================================================================
# INCOME VS GWA BUBBLE DATA
# ============================================================================
@reports_bp.route('/dashboard/income-gwa-bubble', methods=['GET'])
def get_income_gwa_bubble():
    """Get income vs GWA bubble chart data"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    bubble_query = f"""
        SELECT 
            e.income,
            e.gwa,
            e.score,
            CONCAT(s.first_name, ' ', s.last_name) as student_name
        FROM evaluations e
        JOIN applications app ON e.application_id = app.id
        JOIN students s ON app.student_id = s.user_id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    bubble_data = execute_query(bubble_query, params)

    return jsonify({
        'bubbleData': bubble_data or []
    })


# ============================================================================
# EXPORT DATA ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/export', methods=['GET'])
def export_dashboard_data():
    """Export all dashboard data for reporting"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Comprehensive export query
    export_query = f"""
        SELECT 
            app.id as application_id,
            app.reference_number,
            s.student_id,
            CONCAT(s.first_name, ' ', s.last_name) as student_name,
            s.email,
            s.contact_number,
            s.gender,
            DATE_FORMAT(s.birth_date, '%%Y-%%m-%%d') as birth_date,
            c.name as campus,
            d.name as department,
            co.name as course,
            ei.year_level,
            ei.enrollment_status,
            CONCAT(ay.year_start, '-', ay.year_end) as academic_year,
            sem.name as semester,
            DATE_FORMAT(app.submitted_at, '%%Y-%%m-%%d %%H:%%i:%%s') as submitted_at,
            app.status,
            e.gwa,
            e.income,
            e.score,
            e.classification,
            sch.name as scholarship_name,
            ss.awarded_amount,
            ss.status as scholarship_status,
            fb.father_occupation,
            fb.mother_occupation,
            fb.household_number,
            fb.is_4ps_member,
            fb.ip_affiliation
        FROM applications app
        JOIN students s ON app.student_id = s.user_id
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN evaluations e ON app.id = e.application_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        LEFT JOIN family_background fb ON app.student_id = fb.student_id
        WHERE app.deleted_at IS NULL AND {where_clause}
        ORDER BY app.submitted_at DESC
    """
    export_data = execute_query(export_query, params)

    return jsonify({
        'data': export_data or [],
        'filters': filters,
        'exportedAt': datetime.now().isoformat()
    })


# ============================================================================
# FILTER OPTIONS ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/filter-options', methods=['GET'])
def get_filter_options():
    """Get available filter options dynamically"""

    # Academic Years
    academic_years_query = """
                           SELECT DISTINCT CONCAT(year_start, '-', year_end) as value
                           FROM academic_years
                           WHERE deleted_at IS NULL
                           ORDER BY year_start DESC \
                           """
    academic_years = execute_query(academic_years_query)

    # Semesters
    semesters_query = """
                      SELECT DISTINCT name as value
                      FROM semesters
                      WHERE deleted_at IS NULL
                      ORDER BY
                          CASE name
                          WHEN '1st Semester' THEN 1
                          WHEN '2nd Semester' THEN 2
                          ELSE 3
                      END \
                      """
    semesters = execute_query(semesters_query)

    # Campuses
    campuses_query = """
                     SELECT name as value
                     FROM campuses
                     ORDER BY name \
                     """
    campuses = execute_query(campuses_query)

    # Departments
    departments_query = """
                        SELECT DISTINCT name as value
                        FROM departments
                        ORDER BY name \
                        """
    departments = execute_query(departments_query)

    # Courses
    courses_query = """
                    SELECT DISTINCT name as value
                    FROM courses
                    ORDER BY name \
                    """
    courses = execute_query(courses_query)

    # Scholarships
    scholarships_query = """
                         SELECT name as value
                         FROM scholarships
                         WHERE deleted_at IS NULL AND is_active = 1
                         ORDER BY name \
                         """
    scholarships = execute_query(scholarships_query)

    # Get active period info
    active_period_query = """
        SELECT 
            CONCAT(ay.year_start, '-', ay.year_end) as academic_year,
            sem.name as semester
        FROM semesters sem
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        WHERE sem.is_active = 1
        LIMIT 1
    """
    active_period = execute_query(active_period_query, fetch_one=True)

    return jsonify({
        'academicYears': [ay['value'] for ay in (academic_years or [])],
        'semesters': [s['value'] for s in (semesters or [])],
        'campuses': [c['value'] for c in (campuses or [])],
        'departments': [d['value'] for d in (departments or [])],
        'courses': [c['value'] for c in (courses or [])],
        'scholarships': [s['value'] for s in (scholarships or [])],
        'statuses': ['All', 'Pending', 'Approved', 'Denied', 'Evaluated'],
        'activePeriod': {
            'academicYear': active_period['academic_year'] if active_period else None,
            'semester': active_period['semester'] if active_period else None
        }
    })


# ============================================================================
# STATISTICS SUMMARY ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/statistics', methods=['GET'])
def get_statistics():
    """Get statistical analysis of applications"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
        'campus': request.args.get('campus'),
        'department': request.args.get('department'),
        'course': request.args.get('course'),
        'scholarship': request.args.get('scholarship'),
        'status': request.args.get('status')
    }

    where_clause, params = build_filter_conditions(filters)

    # Statistical analysis
    stats_query = f"""
        SELECT 
            COUNT(DISTINCT app.id) as total_applications,
            COUNT(DISTINCT CASE WHEN app.status = 'approved' THEN app.id END) as approved_count,
            COUNT(DISTINCT CASE WHEN app.status = 'denied' THEN app.id END) as denied_count,
            COUNT(DISTINCT CASE WHEN app.status = 'pending' THEN app.id END) as pending_count,
            AVG(e.gwa) as avg_gwa,
            MIN(e.gwa) as min_gwa,
            MAX(e.gwa) as max_gwa,
            STDDEV(e.gwa) as stddev_gwa,
            AVG(e.income) as avg_income,
            MIN(e.income) as min_income,
            MAX(e.income) as max_income,
            STDDEV(e.income) as stddev_income,
            AVG(e.score) as avg_score,
            MIN(e.score) as min_score,
            MAX(e.score) as max_score,
            STDDEV(e.score) as stddev_score,
            SUM(ss.awarded_amount) as total_awarded_amount,
            AVG(ss.awarded_amount) as avg_awarded_amount
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN education_info ei ON app.student_id = ei.student_id AND ei.semester_id = app.semester_id

        LEFT JOIN campuses c ON ei.campus_id = c.campus_id
        LEFT JOIN departments d ON ei.department_id = d.department_id
        LEFT JOIN courses co ON ei.course_id = co.course_id
        LEFT JOIN evaluations e ON app.id = e.application_id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        LEFT JOIN scholarships sch ON ss.scholarship_id = sch.id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """
    stats = execute_query(stats_query, params, fetch_one=True)

    # Format statistics
    if stats:
        return jsonify({
            'applications': {
                'total': stats['total_applications'] or 0,
                'approved': stats['approved_count'] or 0,
                'denied': stats['denied_count'] or 0,
                'pending': stats['pending_count'] or 0,
                'approvalRate': round((stats['approved_count'] or 0) * 100.0 / max(stats['total_applications'] or 1, 1),
                                      2)
            },
            'gwa': {
                'average': round(stats['avg_gwa'] or 0, 2),
                'minimum': round(stats['min_gwa'] or 0, 2),
                'maximum': round(stats['max_gwa'] or 0, 2),
                'standardDeviation': round(stats['stddev_gwa'] or 0, 2)
            },
            'income': {
                'average': round(stats['avg_income'] or 0, 2),
                'minimum': round(stats['min_income'] or 0, 2),
                'maximum': round(stats['max_income'] or 0, 2),
                'standardDeviation': round(stats['stddev_income'] or 0, 2)
            },
            'fuzzyScore': {
                'average': round(stats['avg_score'] or 0, 4),
                'minimum': round(stats['min_score'] or 0, 4),
                'maximum': round(stats['max_score'] or 0, 4),
                'standardDeviation': round(stats['stddev_score'] or 0, 4)
            },
            'awards': {
                'totalAmount': round(stats['total_awarded_amount'] or 0, 2),
                'averageAmount': round(stats['avg_awarded_amount'] or 0, 2)
            }
        })
    else:
        return jsonify({
            'applications': {'total': 0, 'approved': 0, 'denied': 0, 'pending': 0, 'approvalRate': 0},
            'gwa': {'average': 0, 'minimum': 0, 'maximum': 0, 'standardDeviation': 0},
            'income': {'average': 0, 'minimum': 0, 'maximum': 0, 'standardDeviation': 0},
            'fuzzyScore': {'average': 0, 'minimum': 0, 'maximum': 0, 'standardDeviation': 0},
            'awards': {'totalAmount': 0, 'averageAmount': 0}
        })


# ============================================================================
# HELPER FUNCTION FOR PREVIOUS PERIOD
# ============================================================================
def get_previous_semester(current_semester_id):
    """Get the previous semester ID based on current semester"""
    query = """
        SELECT sem.id
        FROM semesters sem
        WHERE sem.id < %s AND sem.deleted_at IS NULL
        ORDER BY sem.id DESC
        LIMIT 1
    """
    result = execute_query(query, (current_semester_id,), fetch_one=True)
    return result['id'] if result else None


# ============================================================================
# ACTIVE PERIOD ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/active-period', methods=['GET'])
def get_active_period():
    """Get the currently active semester and academic year"""
    query = """
        SELECT 
            CONCAT(ay.year_start, '-', ay.year_end) as academic_year,
            ay.id as academic_year_id,
            ay.year_start,
            ay.year_end,
            sem.name as semester_name,
            sem.id as semester_id,
            sem.start_date,
            sem.end_date,
            sem.is_active
        FROM semesters sem
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        WHERE sem.is_active = 1
        LIMIT 1
    """
    result = execute_query(query, fetch_one=True)

    if not result:
        return jsonify({"error": "No active period found"}), 404

    return jsonify({
        "academicYear": result['academic_year'],
        "academicYearId": result['academic_year_id'],
        "yearStart": result['year_start'],
        "yearEnd": result['year_end'],
        "semester": result['semester_name'],
        "semesterId": result['semester_id'],
        "semesterName": result['semester_name'],
        "startDate": result['start_date'].isoformat() if result['start_date'] else None,
        "endDate": result['end_date'].isoformat() if result['end_date'] else None,
        "isActive": bool(result['is_active'])
    })


# ============================================================================
# PERIOD COMPARISON ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/comparison', methods=['GET'])
def get_period_comparison():
    """Get comparison data between current and previous period"""
    current_semester_id = request.args.get('currentSemesterId', type=int)
    previous_semester_id = request.args.get('previousSemesterId', type=int)

    # If currentSemesterId not provided, get active semester
    if not current_semester_id:
        active_query = """
            SELECT id FROM semesters WHERE is_active = 1 LIMIT 1
        """
        active_result = execute_query(active_query, fetch_one=True)
        if not active_result:
            return jsonify({"error": "No active semester found"}), 404
        current_semester_id = active_result['id']

    # If previousSemesterId not provided, get the previous semester
    if not previous_semester_id:
        previous_semester_id = get_previous_semester(current_semester_id)

    def get_period_data(semester_id):
        """Helper function to get statistics for a specific semester"""
        if not semester_id:
            return None

        query = """
            SELECT 
                CONCAT(sem.name, ' ', ay.year_start, '-', ay.year_end) as period,
                sem.id as semester_id,
                COUNT(DISTINCT app.id) as total_applications,
                COUNT(DISTINCT CASE WHEN app.status = 'approved' THEN app.id END) as approved_applications,
                COUNT(DISTINCT CASE WHEN app.status = 'denied' THEN app.id END) as denied_applications,
                COUNT(DISTINCT CASE WHEN app.status = 'pending' THEN app.id END) as pending_applications,
                AVG(e.gwa) as average_gwa,
                AVG(e.income) as average_income,
                COALESCE(SUM(ss.awarded_amount), 0) as total_awarded,
                COUNT(DISTINCT CASE WHEN ss.status = 'selected' THEN ss.id END) as number_of_scholars
            FROM semesters sem
            JOIN academic_years ay ON sem.academic_year_id = ay.id
            LEFT JOIN applications app ON app.semester_id = sem.id AND app.deleted_at IS NULL
            LEFT JOIN evaluations e ON e.application_id = app.id
            LEFT JOIN scholarship_selections ss ON ss.application_id = app.id AND ss.status = 'selected'
            WHERE sem.id = %s
            GROUP BY sem.id, sem.name, ay.year_start, ay.year_end
        """
        result = execute_query(query, (semester_id,), fetch_one=True)
        if not result:
            return None

        total = result['total_applications'] or 0
        approved = result['approved_applications'] or 0
        approval_rate = round((approved * 100.0 / total), 2) if total > 0 else 0.0

        return {
            "period": result['period'],
            "semesterId": result['semester_id'],
            "totalApplications": total,
            "approvedApplications": approved,
            "deniedApplications": result['denied_applications'] or 0,
            "pendingApplications": result['pending_applications'] or 0,
            "approvalRate": approval_rate,
            "averageGWA": round(result['average_gwa'], 2) if result['average_gwa'] else 0,
            "averageIncome": round(result['average_income'], 2) if result['average_income'] else 0,
            "totalAwarded": float(result['total_awarded'] or 0),
            "numberOfScholars": result['number_of_scholars'] or 0
        }

    current_data = get_period_data(current_semester_id)
    previous_data = get_period_data(previous_semester_id)

    if not current_data:
        return jsonify({"error": "No data found for current period"}), 404

    # Calculate changes
    changes = {}
    if previous_data and previous_data['totalApplications'] > 0:
        changes['applicationsChange'] = round(
            ((current_data['totalApplications'] - previous_data['totalApplications']) * 100.0 /
             previous_data['totalApplications']), 2
        )
        changes['approvalRateChange'] = round(
            current_data['approvalRate'] - previous_data['approvalRate'], 2
        )
        changes['gwaChange'] = round(
            current_data['averageGWA'] - previous_data['averageGWA'], 2
        )
        changes['incomeChange'] = round(
            ((current_data['averageIncome'] - previous_data['averageIncome']) * 100.0 /
             previous_data['averageIncome']), 2
        ) if previous_data['averageIncome'] > 0 else 0
        changes['awardedChange'] = round(
            ((current_data['totalAwarded'] - previous_data['totalAwarded']) * 100.0 /
             previous_data['totalAwarded']), 2
        ) if previous_data['totalAwarded'] > 0 else 0
        changes['scholarsChange'] = round(
            ((current_data['numberOfScholars'] - previous_data['numberOfScholars']) * 100.0 /
             previous_data['numberOfScholars']), 2
        ) if previous_data['numberOfScholars'] > 0 else 0
    else:
        changes = {
            'applicationsChange': 0,
            'approvalRateChange': 0,
            'gwaChange': 0,
            'incomeChange': 0,
            'awardedChange': 0,
            'scholarsChange': 0
        }

    return jsonify({
        "current": current_data,
        "previous": previous_data,
        "changes": changes
    })


# ============================================================================
# SUMMARY TOTALS ENDPOINT
# ============================================================================
@reports_bp.route('/dashboard/summary-totals', methods=['GET'])
def get_summary_totals():
    """Get high-level summary totals for dashboard header"""
    filters = {
        'academicYear': request.args.get('academicYear'),
        'semester': request.args.get('semester'),
    }

    where_clause, params = build_filter_conditions(filters)

    query = f"""
        SELECT 
            COALESCE(SUM(CASE WHEN ss.status = 'selected' THEN ss.awarded_amount ELSE 0 END), 0) as total_awarded,
            COUNT(DISTINCT CASE WHEN ss.status = 'selected' THEN app.id END) as scholars_count,
            AVG(CASE WHEN ss.status = 'selected' THEN ss.awarded_amount END) as avg_award,
            COUNT(DISTINCT CASE WHEN app.status = 'pending' THEN app.id END) as pending_count,
            COUNT(DISTINCT CASE WHEN app.status = 'evaluated' THEN app.id END) as evaluated_count
        FROM applications app
        JOIN semesters sem ON app.semester_id = sem.id
        JOIN academic_years ay ON sem.academic_year_id = ay.id
        LEFT JOIN scholarship_selections ss ON app.id = ss.application_id
        WHERE app.deleted_at IS NULL AND {where_clause}
    """

    result = execute_query(query, params, fetch_one=True)

    # Get active scholarships count
    active_scholarships_query = """
        SELECT COUNT(*) as count
        FROM scholarships
        WHERE is_active = 1 AND deleted_at IS NULL
    """
    active_scholarships = execute_query(active_scholarships_query, fetch_one=True)

    if result:
        return jsonify({
            "totalAmountAwarded": float(result['total_awarded'] or 0),
            "numberOfScholars": result['scholars_count'] or 0,
            "averageAwardAmount": round(result['avg_award'], 2) if result['avg_award'] else 0,
            "pendingApplications": result['pending_count'] or 0,
            "evaluatedNotAwarded": result['evaluated_count'] or 0,
            "activeScholarships": active_scholarships['count'] if active_scholarships else 0
        })
    else:
        return jsonify({
            "totalAmountAwarded": 0,
            "numberOfScholars": 0,
            "averageAwardAmount": 0,
            "pendingApplications": 0,
            "evaluatedNotAwarded": 0,
            "activeScholarships": active_scholarships['count'] if active_scholarships else 0
        })


# ============================================================================
# ERROR HANDLERS
# ============================================================================
@reports_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@reports_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


@reports_bp.errorhandler(Exception)
def handle_exception(error):
    return jsonify({'error': str(error)}), 500