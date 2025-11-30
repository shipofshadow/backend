
def insert_grades(db, application_id, grades_list):
    cursor = db.cursor()

    for grade in grades_list:
        cursor.execute("""
            INSERT INTO application_grades (application_id, subject_name, grade, units)
            VALUES (%s, %s, %s, %s)
        """, (application_id, grade['subject'], grade['grade'], grade['units']))

    cursor.close()


from datetime import datetime

def save_application(db, user_id, application):
    cursor = db.cursor()

    semester_id = int(application.semester_id or 0)

    # Check if student has an application for this semester
    cursor.execute("""
        SELECT id FROM applications
        WHERE student_id = %s AND semester_id = %s
        LIMIT 1
    """, (user_id, semester_id))

    existing_application = cursor.fetchone()

    if existing_application:
        # Semester application exists -> only update addresses and family_background
        application_id = existing_application['id']
    else:
        # Insert new application for this semester
        cursor.execute("""
            INSERT INTO applications (student_id, semester_id, submitted_at, status)
            VALUES (%s, %s, %s, 'pending')
        """, (user_id, semester_id, datetime.now()))
        application_id = cursor.lastrowid

        # Insert education_info for new semester
        cursor.execute("""
            INSERT INTO education_info (student_id, campus_id, department_id, course_id,
                                        semester_id, year_level, total_units, enrollment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.campus, application.department, application.course,
            semester_id, application.year_level, application.total_units,
            application.enrollment_status
        ))

    # Update or insert addresses
    cursor.execute("""
        SELECT id FROM addresses WHERE student_id = %s
    """, (user_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE addresses
            SET street=%s,
                region_code=%s,
                region_name=%s,
                province_code=%s,
                province_name=%s,
                municipality_code=%s,
                municipality_name=%s,
                barangay_code=%s,
                barangay_name=%s,
                zip_code=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE student_id = %s
        """, (
            application.street, application.region_code, application.region_name,
            application.province_code, application.province_name,
            application.municipality_code, application.municipality_name,
            application.barangay_code, application.barangay_name, application.zip_code,
            user_id
        ))
    else:
        cursor.execute("""
            INSERT INTO addresses (student_id, street, region_code, region_name,
                                   province_code, province_name, municipality_code, municipality_name,
                                   barangay_code, barangay_name, zip_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.street, application.region_code, application.region_name,
            application.province_code, application.province_name,
            application.municipality_code, application.municipality_name,
            application.barangay_code, application.barangay_name, application.zip_code
        ))

    # Update or insert family background
    cursor.execute("""
        SELECT id FROM family_background WHERE student_id = %s
    """, (user_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE family_background
            SET father_last_name=%s,
                father_first_name=%s,
                father_middle_name=%s,
                father_extension=%s,
                father_occupation=%s,
                father_income=%s,
                mother_last_name=%s,
                mother_first_name=%s,
                mother_middle_name=%s,
                mother_occupation=%s,
                mother_income=%s,
                household_number=%s,
                ip_affiliation=%s,
                is_4ps_member=%s,
                siblings=%s,
                siblings_studying=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE student_id = %s
        """, (
            application.father_last_name, application.father_first_name, application.father_middle_name,
            application.father_extension, application.father_occupation, application.father_income,
            application.mother_last_name, application.mother_first_name, application.mother_middle_name,
            application.mother_occupation, application.mother_income,
            application.household_number, application.ip_affiliation,
            1 if application.dswd_program else 0,
            application.siblings, application.siblings_studying,
            user_id
        ))
    else:
        cursor.execute("""
            INSERT INTO family_background (student_id, father_last_name, father_first_name,
                                           father_middle_name, father_extension, father_occupation, father_income,
                                           mother_last_name, mother_first_name, mother_middle_name,
                                           mother_occupation, mother_income,
                                           household_number, ip_affiliation, is_4ps_member,
                                           siblings, siblings_studying)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.father_last_name, application.father_first_name,
            application.father_middle_name, application.father_extension, application.father_occupation,
            application.father_income, application.mother_last_name, application.mother_first_name,
            application.mother_middle_name, application.mother_occupation, application.mother_income,
            application.household_number, application.ip_affiliation,
            1 if application.dswd_program else 0,
            application.siblings, application.siblings_studying
        ))

    db.commit()
    cursor.close()
    return application_id


def base_applicant_query():
    return """
SELECT 
            applications.student_id,
            applications.id,
            applications.remarks,
            applications.status,
            students.*,
            education_info.year_level,
            education_info.total_units,
            education_info.enrollment_status,
            family_background.father_extension,
            family_background.father_first_name,
            family_background.father_last_name,
            family_background.father_middle_name,
            family_background.father_last_name,
            family_background.father_occupation,
            family_background.father_income,
            family_background.mother_first_name,
            family_background.mother_last_name,
            family_background.mother_middle_name,
            family_background.mother_last_name,
            family_background.mother_occupation,
            family_background.mother_income,
            family_background.household_number,
            family_background.ip_affiliation,
            family_background.is_4ps_member,
            family_background.siblings,
            family_background.siblings_studying,
            addresses.*,
            campuses.*,
            campuses.name as campus,
            departments.name as department,
            courses.name as course,
            departments.*,
            courses.*,
            students.student_id AS uid,
            semesters.*,
            itr_files.file_path AS itr_file,
            grades_files.file_path AS grades_file,
            evaluations.*,
            students.user_id AS uuid
FROM applications
INNER JOIN students ON students.user_id = applications.student_id
LEFT JOIN addresses ON addresses.student_id = students.user_id
LEFT JOIN education_info 
    ON education_info.student_id = students.user_id
    AND education_info.semester_id = applications.semester_id
LEFT JOIN family_background ON family_background.student_id = students.user_id
INNER JOIN semesters ON semesters.id = applications.semester_id
INNER JOIN academic_years ON academic_years.id = semesters.academic_year_id
LEFT JOIN evaluations ON evaluations.application_id = applications.id
        -- Files JOIN
        -- Latest ITR file per application
        LEFT JOIN (
            SELECT application_id, file_path
            FROM application_files AS f1
            WHERE file_type = 'itr'
              AND id = (SELECT MAX(id) 
                        FROM application_files f2 
                        WHERE f2.application_id = f1.application_id 
                          AND f2.file_type = 'itr')
        ) AS itr_files ON itr_files.application_id = applications.id
        
        -- Latest Grades file per application
        LEFT JOIN (
            SELECT application_id, file_path
            FROM application_files AS f1
            WHERE file_type = 'grades'
              AND id = (SELECT MAX(id) 
                        FROM application_files f2 
                        WHERE f2.application_id = f1.application_id 
                          AND f2.file_type = 'grades')
        ) AS grades_files ON grades_files.application_id = applications.id
            
        LEFT JOIN campuses ON education_info.campus_id = campuses.campus_id
        LEFT JOIN departments ON education_info.department_id = departments.department_id
        LEFT JOIN courses ON education_info.course_id = courses.course_id
           """

def fetch_grades_by_application_ids(cursor, application_ids):
    if not application_ids:
        return {}

    placeholders = ",".join(["%s"] * len(application_ids))
    cursor.execute(f"""
        SELECT application_id, subject_name, grade, units
        FROM application_grades
        WHERE application_id IN ({placeholders})
    """, application_ids)

    grades_raw = cursor.fetchall()

    grades_map = {}
    for g in grades_raw:
        app_id = g["application_id"]
        grades_map.setdefault(app_id, []).append({
            "subject_name": g["subject_name"],
            "grade": float(g["grade"]),
            "units": int(g["units"])
        })

    return grades_map

def fetch_grades_by_application_id(cursor, application_id):
    cursor.execute("""
        SELECT subject_name, grade, units
        FROM application_grades
        WHERE application_id = %s
    """, (application_id,))

    grades_raw = cursor.fetchall()

    return [
        {
            "subject_name": g["subject_name"],
            "grade": float(g["grade"]),
            "units": int(g["units"])
        }
        for g in grades_raw
    ]
