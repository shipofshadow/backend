
import sys
import os

# Add parent directory to path to import storage
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import get_connection

def inspect_schema():
    conn = get_connection()
    cursor = conn.cursor()

    tables = ['applications', 'recommended_scholarships', 'scholarships']

    for table in tables:
        print(f"--- Schema for {table} ---")
        try:
            cursor.execute(f"SHOW CREATE TABLE {table}")
            result = cursor.fetchone()
            print(result['Create Table'])
        except Exception as e:
            print(f"Error inspecting {table}: {e}")
        print("\n")

    conn.close()

if __name__ == "__main__":
    inspect_schema()
