
import sys
import os

# Add parent directory to path to import storage
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage import get_connection

def run_migration():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        print("Checking if column 'selection_status' exists in 'recommended_scholarships'...")
        cursor.execute("SHOW COLUMNS FROM recommended_scholarships LIKE 'selection_status'")
        result = cursor.fetchone()

        if result:
            print("Column 'selection_status' already exists. Skipping migration.")
        else:
            print("Adding column 'selection_status' to 'recommended_scholarships'...")
            sql = "ALTER TABLE recommended_scholarships ADD COLUMN selection_status ENUM('selected', 'rejected') DEFAULT NULL"
            cursor.execute(sql)
            conn.commit()
            print("Migration completed successfully.")

    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
