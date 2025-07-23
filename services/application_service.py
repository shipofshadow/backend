from datetime import datetime

def insert_grades(db, application_id, grades_list):
    cursor = db.cursor()

    for grade in grades_list:
        cursor.execute("""
            INSERT INTO application_grades (application_id, subject_name, grade)
            VALUES (%s, %s, %s)
        """, (application_id, grade['subject'], grade['grade']))

    cursor.close()

def save_application(db, user_id, application):
    cursor = db.cursor()

    semester_id = int(application.semester_id or 0)

    # Check if student has any application before
    cursor.execute("""
        SELECT id FROM applications 
        WHERE student_id = %s
        LIMIT 1
    """, (user_id,))

    existing = cursor.fetchone()

    if existing:
        # Check if application for this semester exists
        cursor.execute("""
            SELECT id FROM applications
            WHERE student_id = %s AND semester_id = %s
            LIMIT 1
        """, (user_id, semester_id))

        semester_existing = cursor.fetchone()

        application_id =  semester_existing['id']
        if not semester_existing:
            # New semester -> insert new application
            cursor.execute("""
                INSERT INTO applications (student_id, semester_id, submitted_at, status)
                VALUES (%s, %s, %s, 'pending')
            """, (user_id, semester_id, datetime.now()))

            application_id = cursor.lastrowid

            # Insert new education_info for new semester
            cursor.execute("""
                INSERT INTO education_info (student_id, campus_id, department_id, course_id,
                                            semester_id, year_level, total_units, enrollment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id, application.campus, application.department, application.course,
                semester_id, application.year_level,
                application.total_units, application.enrollment_status
            ))
        else:
            # Existing semester -> update education_info
            cursor.execute("""
                UPDATE education_info
                SET campus_id=%s, department_id=%s, course_id=%s,
                    year_level=%s, total_units=%s, enrollment_status=%s
                WHERE student_id=%s AND semester_id=%s
            """, (
                application.campus, application.department, application.course,
                application.year_level, application.total_units, application.enrollment_status,
                user_id, semester_id
            ))

    else:
        # First application ever -> insert everything
        cursor.execute("""
            INSERT INTO applications (student_id, semester_id, submitted_at, status)
            VALUES (%s, %s, %s, 'pending')
        """, (user_id, semester_id, datetime.now()))

        application_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO education_info (student_id, campus_id, department_id, course_id,
                                        semester_id, year_level, total_units, enrollment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.campus, application.department, application.course,
            semester_id, application.year_level,
            application.total_units, application.enrollment_status
        ))

    # Addresses (upsert)
    cursor.execute("""
        INSERT INTO addresses (student_id, street, region_code, region_name,
                               province_code, province_name, municipality_code, municipality_name,
                               barangay_code, barangay_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            street=VALUES(street),
            region_code=VALUES(region_code),
            region_name=VALUES(region_name),
            province_code=VALUES(province_code),
            province_name=VALUES(province_name),
            municipality_code=VALUES(municipality_code),
            municipality_name=VALUES(municipality_name),
            barangay_code=VALUES(barangay_code),
            barangay_name=VALUES(barangay_name)
    """, (
        user_id, application.street, application.region_code, application.region_name,
        application.province_code, application.province_name,
        application.municipality_code, application.municipality_name,
        application.barangay_code, application.barangay_name
    ))

    # Family background (upsert)
    cursor.execute("""
        INSERT INTO family_background (student_id, father_last_name, father_first_name, father_middle_name,
                                       father_extension, father_occupation, father_income,
                                       mother_last_name, mother_first_name, mother_middle_name,
                                       mother_occupation, mother_income,
                                       household_number, ip_affiliation, is_4ps_member,
                                       siblings, siblings_studying)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            father_last_name=VALUES(father_last_name),
            father_first_name=VALUES(father_first_name),
            father_middle_name=VALUES(father_middle_name),
            father_extension=VALUES(father_extension),
            father_occupation=VALUES(father_occupation),
            father_income=VALUES(father_income),
            mother_last_name=VALUES(mother_last_name),
            mother_first_name=VALUES(mother_first_name),
            mother_middle_name=VALUES(mother_middle_name),
            mother_occupation=VALUES(mother_occupation),
            mother_income=VALUES(mother_income),
            household_number=VALUES(household_number),
            ip_affiliation=VALUES(ip_affiliation),
            is_4ps_member=VALUES(is_4ps_member),
            siblings=VALUES(siblings),
            siblings_studying=VALUES(siblings_studying)
    """, (
        user_id, application.father_last_name, application.father_first_name, application.father_middle_name,
        application.father_extension, application.father_occupation, application.father_income,
        application.mother_last_name, application.mother_first_name, application.mother_middle_name,
        application.mother_occupation, application.mother_income,
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
            applications.*,
            students.*,
            education_info.*,
            family_background.*,
            addresses.*,
            campuses.name as campus,
            departments.name as department,
            courses.name as course,
            students.student_id as uid,
            semesters.*,
            itr_files.file_path AS itr_file,
            grades_files.file_path AS grades_file


        FROM applications
        INNER JOIN students ON students.user_id = applications.student_id
        INNER JOIN addresses ON addresses.student_id = students.user_id
        INNER JOIN education_info ON education_info.student_id = students.user_id
        INNER JOIN family_background ON family_background.student_id = students.user_id
        INNER JOIN semesters ON semesters.id = applications.semester_id
        INNER JOIN academic_years ON academic_years.id = semesters.academic_year_id
            
        -- Files JOIN
        LEFT JOIN application_files AS itr_files 
            ON itr_files.application_id = applications.id AND itr_files.file_type = 'itr'
        
        LEFT JOIN application_files AS grades_files 
            ON grades_files.application_id = applications.id AND grades_files.file_type = 'grades'
            
        LEFT JOIN campuses ON education_info.campus_id = campuses.campus_id
        LEFT JOIN departments ON education_info.department_id = departments.department_id
        LEFT JOIN courses ON education_info.course_id = courses.course_id
    """
