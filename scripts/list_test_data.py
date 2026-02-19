
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import get_connection

def list_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("--- Test Data ---")
    
    try:
        cursor.execute("SELECT id, username FROM users WHERE role = 'student' LIMIT 1")
        student = cursor.fetchone()
        print(f"Student: {student}")
        
        cursor.execute("SELECT id, username FROM users WHERE role = 'admin' LIMIT 1")
        admin = cursor.fetchone()
        print(f"Admin: {admin}")

        cursor.execute("SELECT id, name FROM scholarships WHERE is_active = 1 LIMIT 1")
        scholarship = cursor.fetchone()
        print(f"Scholarship: {scholarship}")

    except Exception as e:
        print(f"Error: {e}")
        
    conn.close()

if __name__ == "__main__":
    list_data()
