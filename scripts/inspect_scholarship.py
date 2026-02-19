
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import get_connection

def inspect_scholarship():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("--- Inspecting Scholarship 1 ---")
    cursor.execute("SELECT * FROM scholarships WHERE id = 1")
    row = cursor.fetchone()
    print(row)

    conn.close()

if __name__ == "__main__":
    inspect_scholarship()
