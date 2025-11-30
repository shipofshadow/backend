import json


class Application:
    def __init__(self, data):
        # Personal Info
        self.first_name = data.get("firstName")
        self.middle_name = data.get("middleName")
        self.last_name = data.get("lastName")
        self.name_extension = data.get("nameExtension")
        self.email = data.get("email")
        self.phone = data.get("phone")
        self.birth_date = data.get("birthDate")

        # Address Info
        self.street = data.get("street")
        self.region_code = data.get("regionCode")
        self.region_name = data.get("regionName")
        self.province_code = data.get("provinceCode")
        self.province_name = data.get("provinceName")
        self.municipality_code = data.get("municipalityCode")
        self.municipality_name = data.get("municipalityName")
        self.barangay_code = data.get("barangayCode")
        self.barangay_name = data.get("barangayName")
        self.zip_code = data.get("zipCode")

        # Parental Info
        self.father_last_name = data.get("father", {}).get("lastName")
        self.father_first_name = data.get("father", {}).get("firstName")
        self.father_middle_name = data.get("father", {}).get("middleName")
        self.father_extension = data.get("father", {}).get("extension")
        self.father_occupation = data.get("father", {}).get("occupation")
        self.father_income = data.get("father", {}).get("income")

        self.mother_last_name = data.get("mother", {}).get("lastName")
        self.mother_first_name = data.get("mother", {}).get("firstName")
        self.mother_middle_name = data.get("mother", {}).get("middleName")
        self.mother_occupation = data.get("mother", {}).get("occupation")
        self.mother_income = data.get("mother", {}).get("income")

        # Emergency Contact
        self.emergency_contact_name = data.get("emergencyContactName")
        self.emergency_contact_number = data.get("emergencyContactNumber")

        # Household Info
        self.household_number = data.get("householdNumber")
        self.siblings = data.get("siblings")
        self.siblings_studying = data.get("siblingsStudying")
        value = data.get("ipAffiliation")
        self.ip_affiliation = None if value in (None, "", "N/A") else value
        self.dswd_program = data.get("dswdProgram")

        # Academic Info
        self.student_id = data.get("studentId")
        self.year_level = data.get("year_level")
        self.campus = data.get("campus")
        self.department = data.get("department")
        self.course = data.get("course")
        self.academic_year_id = data.get("academicYearId")
        self.semester_id = data.get("semesterId")
        self.enrollment_status = data.get("enrollmentStatus")
        self.total_units = data.get("total_units")

        self.scholarship_name = data.get("scholarshipName")
        self.other_scholarship = data.get("otherScholarship")
        self.scholarship_amount = data.get("scholarshipAmount")

        grades_raw = data.get("gradesList", "[]")
        try:
            self.grades_list = json.loads(grades_raw)
        except Exception:
            self.grades_list = []

    def to_dict(self):
        return {
            # Personal
            "first_name": self.first_name,
            "middle_name": self.middle_name,
            "last_name": self.last_name,
            "name_extension": self.name_extension,
            "email": self.email,
            "phone": self.phone,
            "birth_date": self.birth_date,

            # Address
            "street": self.street,
            "region_code": self.region_code,
            "region_name": self.region_name,
            "province_code": self.province_code,
            "province_name": self.province_name,
            "municipality_code": self.municipality_code,
            "municipality_name": self.municipality_name,
            "barangay_code": self.barangay_code,
            "barangay_name": self.barangay_name,

            # Father
            "father_last_name": self.father_last_name,
            "father_first_name": self.father_first_name,
            "father_middle_name": self.father_middle_name,
            "father_extension": self.father_extension,
            "father_occupation": self.father_occupation,
            "father_income": self.father_income,

            # Mother
            "mother_last_name": self.mother_last_name,
            "mother_first_name": self.mother_first_name,
            "mother_middle_name": self.mother_middle_name,
            "mother_occupation": self.mother_occupation,
            "mother_income": self.mother_income,

            # Emergency
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_number": self.emergency_contact_number,

            # Household
            "household_number": self.household_number,
            "siblings": self.siblings,
            "siblings_studying": self.siblings_studying,
            "ip_affiliation": self.ip_affiliation,
            "dswd_program": self.dswd_program,

            # Academic
            "student_id": self.student_id,
            "year_level": self.year_level,
            "campus": self.campus,
            "department": self.department,
            "course": self.course,
            "academic_year_id": self.academic_year_id,
            "semester_id": self.semester_id,
            "enrollment_status": self.enrollment_status,
            "total_units": self.total_units,

            # Scholarship
            "scholarship_name": self.scholarship_name,
            "other_scholarship": self.other_scholarship,
            "scholarship_amount": self.scholarship_amount
        }