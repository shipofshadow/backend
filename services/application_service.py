from datetime import datetime

def save_application(db, user_id, application):
    cursor = db.cursor()

    # Check if there's an existing application
    cursor.execute("SELECT id FROM applications WHERE student_id = %s", (user_id,))
    row = cursor.fetchone()

    if row:
        # UPDATE mode
        application_id = row[0]

        # Update applications
        cursor.execute("""
            UPDATE applications
            SET academic_year_id = %s, submitted_at = %s, status = 'pending', is_archived = 0
            WHERE id = %s
        """, (application.academic_year_id, datetime.now(), application_id))

        # Update education_info
        cursor.execute("""
            UPDATE education_info SET
                campus_id = %s, department_id = %s, course_id = %s,
                academic_year_id = %s, year_level = %s, total_units = %s,
                enrollment_status = %s
            WHERE student_id = %s
        """, (
            application.campus, application.department, application.course,
            application.academic_year_id, application.enrollment_status,
            application.total_units, application.enrollment_status,
            user_id
        ))

        # Update address
        cursor.execute("""
            UPDATE addresses SET
                street = %s, region_code = %s, region_name = %s,
                province_code = %s, province_name = %s,
                municipality_code = %s, municipality_name = %s,
                barangay_code = %s, barangay_name = %s
            WHERE student_id = %s
        """, (
            application.street, application.region_code, application.region_name,
            application.province_code, application.province_name,
            application.municipality_code, application.municipality_name,
            application.barangay_code, application.barangay_name,
            user_id
        ))

        # Update family background
        cursor.execute("""
            UPDATE family_background SET
                father_last_name = %s, father_first_name = %s, father_middle_name = %s,
                father_extension = %s, father_occupation = %s, father_income = %s,
                mother_last_name = %s, mother_first_name = %s, mother_middle_name = %s,
                mother_occupation = %s, mother_income = %s, household_number = %s,
                ip_affiliation = %s, is_4ps_member = %s, siblings = %s, sublings_studying = %s
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
        # INSERT mode
        cursor.execute("""
            INSERT INTO applications (student_id, academic_year_id, submitted_at, status)
            VALUES (%s, %s, %s, 'pending')
        """, (user_id, application.academic_year_id, datetime.now()))

        cursor.execute("""
            INSERT INTO education_info (student_id, campus_id, department_id, course_id,
                                        academic_year_id, year_level, total_units, enrollment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.campus, application.department, application.course,
            application.academic_year_id, application.enrollment_status,
            application.total_units, application.enrollment_status
        ))

        cursor.execute("""
            INSERT INTO addresses (student_id, street, region_code, region_name,
                                   province_code, province_name, municipality_code, municipality_name,
                                   barangay_code, barangay_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, application.street, application.region_code, application.region_name,
            application.province_code, application.province_name,
            application.municipality_code, application.municipality_name,
            application.barangay_code, application.barangay_name
        ))

        cursor.execute("""
            INSERT INTO family_background (student_id, father_last_name, father_first_name, father_middle_name,
                                           father_extension, father_occupation, father_income,
                                           mother_last_name, mother_first_name, mother_middle_name,
                                           mother_occupation, mother_income,
                                           household_number, ip_affiliation, is_4ps_member,
                                           siblings, sublings_studying)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
