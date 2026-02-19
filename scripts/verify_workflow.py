
import sys
import os
import json
import unittest

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from storage import get_connection
from flask_jwt_extended import create_access_token

class TestScholarshipSelection(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        
        self.conn = get_connection()
        self.cursor = self.conn.cursor()

        # Test Data
        self.student_id = 46  # Retrieved from previous step
        self.admin_id = 1     # Assuming admin ID 1 exists
        self.scholarship_id = 1 # Retrieved from previous step
        
        # Setup DB State
        self._clean_db()
        self._setup_data()

    def tearDown(self):
        self._clean_db()
        self.conn.close()
        self.ctx.pop()

    def _clean_db(self):
        # Remove related data for this student/scholarship to start fresh
        try:
            self.cursor.execute("DELETE FROM scholarship_selections WHERE scholarship_id = %s", (self.scholarship_id,))
            self.cursor.execute("DELETE FROM recommended_scholarships WHERE scholarship_id = %s", (self.scholarship_id,))
            self.cursor.execute("DELETE FROM applications WHERE student_id = %s", (self.student_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Cleanup error: {e}")
            self.conn.rollback()

    def _setup_data(self):
        # 1. Ensure Active Semester (Mocking or fetching existing)
        self.cursor.execute("SELECT id FROM semesters WHERE is_active = 1 LIMIT 1")
        res = self.cursor.fetchone()
        if not res:
            # Create a dummy active semester if none
            self.cursor.execute("INSERT INTO academic_years (name, start_year, end_year, is_active) VALUES ('Test Year', 2025, 2026, 1)")
            ay_id = self.cursor.lastrowid
            self.cursor.execute("INSERT INTO semesters (academic_year_id, name, order_index, is_active) VALUES (%s, 'Test Sem', 1, 1)", (ay_id,))
            self.semester_id = self.cursor.lastrowid
        else:
            self.semester_id = res['id']

        # 2. Create Application
        self.cursor.execute("""
            INSERT INTO applications (student_id, semester_id, status) 
            VALUES (%s, %s, 'pending')
        """, (self.student_id, self.semester_id))
        self.application_id = self.cursor.lastrowid

        # 3. Ensure Scholarship is Active and Not Deleted
        self.cursor.execute("""
            UPDATE scholarships 
            SET is_active = 1, deleted_at = NULL 
            WHERE id = %s
        """, (self.scholarship_id,))
        self.conn.commit()

        # 4. Create Recommendation
        self.cursor.execute("""
            INSERT INTO recommended_scholarships (application_id, scholarship_id, score, classification)
            VALUES (%s, %s, 95.5, 'High Priority')
        """, (self.application_id, self.scholarship_id))
        
        self.conn.commit()

    def test_workflow(self):
        # --- Step 1: Student Selects Scholarship ---
        print("\n[Step 1] Student selecting scholarship...")
        student_token = create_access_token(identity=str(self.student_id), additional_claims={"role": "student"})
        
        res = self.client.post('/api/application/select-scholarship', 
                               json={
                                   "application_id": self.application_id, 
                                   "scholarship_id": self.scholarship_id
                               },
                               headers={'Authorization': f'Bearer {student_token}'})
        
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json}")
        self.assertEqual(res.status_code, 200)
        
        # Verify DB Updates
        self.cursor.execute("SELECT status FROM applications WHERE id = %s", (self.application_id,))
        app_status = self.cursor.fetchone()['status']
        self.assertEqual(app_status, 'awaiting_approval')
        
        self.cursor.execute("SELECT selection_status FROM recommended_scholarships WHERE application_id = %s AND scholarship_id = %s", 
                            (self.application_id, self.scholarship_id))
        sel_status = self.cursor.fetchone()['selection_status']
        self.assertEqual(sel_status, 'selected')
        print("-> Student selection verified.")

        # --- Step 2: Admin Views Recommendations ---
        print("\n[Step 2] Admin fetching recommendations...")
        admin_token = create_access_token(identity=str(self.admin_id), additional_claims={"role": "admin"})
        
        # Note: The endpoint is /api/evaluations/recommendations (POST) based on user request/code
        res = self.client.post('/api/evaluations/recommendations', 
                               json={"application_id": self.application_id},
                               headers={'Authorization': f'Bearer {admin_token}'})
        
        print(f"Status: {res.status_code}")
        data = res.json
        self.assertEqual(res.status_code, 200)
        
        # Verify 'selection_status' is in response
        recs = data.get('recommendations', [])
        self.assertTrue(len(recs) > 0)
        target_rec = next((r for r in recs if r['scholarship_id'] == self.scholarship_id), None)
        self.assertIsNotNone(target_rec)
        self.assertEqual(target_rec.get('selection_status'), 'selected')
        print("-> Admin view verified.")

        # --- Step 3: Admin Awards Scholarship (Approval) ---
        print("\n[Step 3] Admin awarding scholarship...")
        res = self.client.post(f'/api/evaluations/{self.application_id}/select',
                               json={
                                   "scholarship_id": self.scholarship_id,
                                   "awarded_amount": 1000.00,
                                   "selection_reason": "Approved"
                               },
                               headers={'Authorization': f'Bearer {admin_token}'})
        
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json}")
        self.assertEqual(res.status_code, 201)
        
        # Verify final status
        self.cursor.execute("SELECT status FROM applications WHERE id = %s", (self.application_id,))
        final_status = self.cursor.fetchone()['status']
        self.assertEqual(final_status, 'approved')
        print("-> Admin award verified.")

if __name__ == '__main__':
    unittest.main()
