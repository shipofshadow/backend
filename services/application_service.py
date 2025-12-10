from datetime import datetime
import json


def insert_grades(db, application_id, grades_list):
    cursor = db.cursor()

    for grade in grades_list:
        cursor.execute("""
                       INSERT INTO application_grades (application_id, subject_name, grade, units)
                       VALUES (%s, %s, %s, %s)
                       """, (application_id, grade['subject'], grade['grade'], grade['units']))

    cursor.close()


def save_application(db, user_id, application):
    cursor = db.cursor()

    semester_id = int(application.semester_id or 0)

    # Check if student has an application for this semester
    cursor.execute("""
                   SELECT id
                   FROM applications
                   WHERE student_id = %s
                     AND semester_id = %s LIMIT 1
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
                   SELECT id
                   FROM addresses
                   WHERE student_id = %s
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

    # Update or insert family background (UPDATED TO INCLUDE EMERGENCY CONTACT)
    cursor.execute("""
                   SELECT id
                   FROM family_background
                   WHERE student_id = %s
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
                           emergency_contact_name=%s,
                           emergency_contact_number=%s,
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
                           application.emergency_contact_name, application.emergency_contact_number,
                           user_id
                       ))
    else:
        cursor.execute("""
                       INSERT INTO family_background (student_id, father_last_name, father_first_name,
                                                      father_middle_name, father_extension, father_occupation,
                                                      father_income,
                                                      mother_last_name, mother_first_name, mother_middle_name,
                                                      mother_occupation, mother_income,
                                                      household_number, ip_affiliation, is_4ps_member,
                                                      siblings, siblings_studying,
                                                      emergency_contact_name, emergency_contact_number)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, (
                           user_id, application.father_last_name, application.father_first_name,
                           application.father_middle_name, application.father_extension, application.father_occupation,
                           application.father_income, application.mother_last_name, application.mother_first_name,
                           application.mother_middle_name, application.mother_occupation, application.mother_income,
                           application.household_number, application.ip_affiliation,
                           1 if application.dswd_program else 0,
                           application.siblings, application.siblings_studying,
                           application.emergency_contact_name, application.emergency_contact_number
                       ))

    db.commit()
    cursor.close()
    return application_id


def base_applicant_query():
    return """
           SELECT applications.student_id, \
                  applications.id, \
                  applications.remarks, \
                  applications.status, \
                  students.*, \
                  education_info.year_level, \
                  education_info.total_units, \
                  education_info.enrollment_status, \
                  family_background.father_extension, \
                  family_background.father_first_name, \
                  family_background.father_last_name, \
                  family_background.father_middle_name, \
                  family_background.father_occupation, \
                  family_background.father_income, \
                  family_background.mother_first_name, \
                  family_background.mother_last_name, \
                  family_background.mother_middle_name, \
                  family_background.mother_occupation, \
                  family_background.mother_income, \
                  family_background.household_number, \
                  family_background.ip_affiliation, \
                  family_background.is_4ps_member, \
                  family_background.siblings, \
                  family_background.siblings_studying, \
                  family_background.emergency_contact_name, \
                  family_background.emergency_contact_number, \
                  addresses.*, \
                  campuses.*, \
                  campuses.name          as campus, \
                  departments.name       as department, \
                  courses.name           as course, \
                  departments.*, \
                  courses.*, \
                  students.student_id    AS uid, \
                  semesters.*, \
                  itr_files.file_paths   AS itr_files, \
                  grades_files.file_path AS grades_file, \
                  evaluations.*, \
                  students.user_id       AS uuid,
                  semesters.id           AS sem_id
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

               -- [MODIFIED] All ITR files per application, comma separated
                    LEFT JOIN (SELECT application_id, GROUP_CONCAT(file_path SEPARATOR ',') as file_paths \
                               FROM application_files \
                               WHERE file_type = 'itr' \
                               GROUP BY application_id) AS itr_files \
                              ON itr_files.application_id = applications.id

               -- Latest Grades file per application (Unchanged)
                    LEFT JOIN (SELECT application_id, file_path \
                               FROM application_files AS f1 \
                               WHERE file_type = 'grades' \
                                 AND id = (SELECT MAX(id) \
                                           FROM application_files f2 \
                                           WHERE f2.application_id = f1.application_id \
                                             AND f2.file_type = 'grades')) AS grades_files \
                              ON grades_files.application_id = applications.id

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


def update_application_data(db, user_id, application_id, application, raw_data):
    cursor = db.cursor()

    # 1. Verify ownership
    cursor.execute("SELECT id FROM applications WHERE id = %s AND student_id = %s", (application_id, user_id))
    if not cursor.fetchone():
        cursor.close()
        return False

    # 2. Update Education Info
    cursor.execute("""
                   UPDATE education_info
                   SET campus_id=%s,
                       department_id=%s,
                       course_id=%s,
                       year_level=%s,
                       total_units=%s,
                       enrollment_status=%s
                   WHERE student_id = %s
                     AND semester_id = %s
                   """, (
                       application.campus, application.department, application.course,
                       application.year_level, application.total_units, application.enrollment_status,
                       user_id, application.semester_id
                   ))

    # 3. Update Addresses
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

    # 4. Update Family Background (UPDATED TO INCLUDE EMERGENCY CONTACT)
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
                       emergency_contact_name=%s,
                       emergency_contact_number=%s,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE student_id = %s
                   """, (
                       application.father_last_name, application.father_first_name, application.father_middle_name,
                       application.father_extension,
                       application.father_occupation, application.father_income,
                       application.mother_last_name, application.mother_first_name, application.mother_middle_name,
                       application.mother_occupation, application.mother_income,
                       application.household_number, application.ip_affiliation, 1 if application.dswd_program else 0,
                       application.siblings, application.siblings_studying,
                       application.emergency_contact_name, application.emergency_contact_number,
                       user_id
                   ))

    # 5. Update Grades (Delete old, Insert new safely)
    if hasattr(application, 'grades_list') and application.grades_list:
        # Clear existing grades for this application
        cursor.execute("DELETE FROM application_grades WHERE application_id = %s", (application_id,))

        for grade in application.grades_list:
            # SAFETY CHECK: Skip rows with empty grades or subjects
            subject = grade.get('subject', '').strip()
            grade_val = str(grade.get('grade', '')).strip()
            units_val = str(grade.get('units', '')).strip()

            if not subject or not grade_val:
                continue  # Skip invalid row

            try:
                # Convert to ensure it's a valid number, otherwise catch error
                grade_num = float(grade_val)
                units_num = int(float(units_val)) if units_val else 0

                cursor.execute("""
                               INSERT INTO application_grades (application_id, subject_name, grade, units)
                               VALUES (%s, %s, %s, %s)
                               """, (application_id, subject, grade_num, units_num))
            except ValueError:
                continue  # Skip if grade is not a number

    # 6. Update Files (Only if new ones were uploaded)
    if "itr_paths" in raw_data and raw_data["itr_paths"]:
        # First, clear OLD files (Optional: dependent on if you want to Append or Replace)
        # Usually for an "Update", you replace the old set with the new set.
        # cursor.execute("DELETE FROM application_files WHERE application_id = %s AND file_type = 'itr'",
        #                (application_id,))

        # Loop through the list of paths and insert them one by one
        for path in raw_data["itr_paths"]:
            cursor.execute("""
                           INSERT INTO application_files (application_id, file_type, file_path)
                           VALUES (%s, 'itr', %s)
                           """, (application_id, path))

    if "grades" in raw_data and raw_data["grades"]:

        # cursor.execute("DELETE FROM application_files WHERE application_id = %s AND file_type = 'grades'",
        #                (application_id,))
        cursor.execute("""
                       INSERT INTO application_files (application_id, file_type, file_path)
                       VALUES (%s, 'grades', %s)
                       """, (application_id, raw_data["grades"]))

    # 7. Update Status (Optional: Set back to pending if needed)
    cursor.execute("UPDATE applications SET status = 'pending', submitted_at = NOW() WHERE id = %s", (application_id,))

    cursor.close()
    return True