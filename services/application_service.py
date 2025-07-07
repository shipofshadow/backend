from datetime import datetime

def save_application(db, user_id, application):
    cursor = db.cursor()

    academic_year_id = int(application.academic_year_id or 0)

    # INSERT mode
    cursor.execute("""
        INSERT INTO applications (student_id, academic_year_id, submitted_at, status)
        VALUES (%s, %s, %s, 'pending')
    """, (user_id, academic_year_id, datetime.now()))

    cursor.execute("""
        INSERT INTO education_info (student_id, campus_id, department_id, course_id,
                                    academic_year_id, year_level, total_units, enrollment_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        user_id, application.campus, application.department, application.course,
                academic_year_id, application.year_level,
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
