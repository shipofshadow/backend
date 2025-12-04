from storage import redis_client, get_connection
from config import DEFAULT_SYSTEM_SETTINGS
import json

SETTINGS_CACHE_PREFIX = "system_setting:"
ALL_SETTINGS_CACHE_KEY = "system_settings:all"


def cast_setting_value(key, value):
    """Helper to cast string values from DB back to their correct types based on DEFAULTS"""
    default_val = DEFAULT_SYSTEM_SETTINGS.get(key)

    if isinstance(default_val, bool):
        return str(value).lower() in ('true', '1', 'yes')
    if isinstance(default_val, int):
        try:
            return int(value)
        except:
            return default_val
    return value


def get_all_system_settings():
    """
    Fetch ALL settings as a dictionary.
    """
    # 1. Try Redis for full object
    try:
        cached_all = redis_client.get(ALL_SETTINGS_CACHE_KEY)
        if cached_all:
            return json.loads(cached_all)
    except Exception:
        pass

    # 2. DB Fetch
    db = get_connection()
    cursor = db.cursor()
    settings = DEFAULT_SYSTEM_SETTINGS.copy()  # Start with defaults

    try:
        cursor.execute("SELECT config_name, config_value FROM configs")
        rows = cursor.fetchall()

        for row in rows:
            key = row['config_name']
            val = row['config_value']
            # Cast type
            settings[key] = cast_setting_value(key, val)

        # 3. Cache Result
        redis_client.setex(ALL_SETTINGS_CACHE_KEY, 3600, json.dumps(settings))

        return settings
    except Exception as e:
        print(f"Error fetching all settings: {e}")
        return settings
    finally:
        cursor.close()
        db.close()


def get_system_setting(key):
    """
    Single setting fetch (Enhanced to use the bulk cache if available)
    """
    # Optimization: Check if we have the full object cached first
    try:
        cached_all = redis_client.get(ALL_SETTINGS_CACHE_KEY)
        if cached_all:
            all_settings = json.loads(cached_all)
            return all_settings.get(key, DEFAULT_SYSTEM_SETTINGS.get(key))
    except:
        pass

    # Fallback to individual fetch logic (existing code...)
    # For now, let's just use get_all_system_settings logic to keep it simple/consistent
    all_settings = get_all_system_settings()
    return all_settings.get(key)


def bulk_update_system_settings(settings_dict):
    """
    Update multiple settings at once.
    """
    db = get_connection()
    cursor = db.cursor()
    try:
        # Prepare SQL for bulk insert/update
        sql = """
              INSERT INTO configs (config_name, config_value, created_at, updated_at)
              VALUES (%s, %s, NOW(), NOW()) ON DUPLICATE KEY \
              UPDATE config_value = \
              VALUES (config_value), updated_at = NOW() \
              """

        params = []
        for key, value in settings_dict.items():
            # Convert booleans to 1/0 for DB storage consistency
            if isinstance(value, bool):
                db_value = '1' if value else '0'
            else:
                db_value = str(value)

            params.append((key, db_value))

        cursor.executemany(sql, params)
        db.commit()

        # Invalidate/Update Cache
        redis_client.delete(ALL_SETTINGS_CACHE_KEY)
        # Also could update the cached value directly to avoid a read, but delete is safer

        return True
    except Exception as e:
        print(f"Error bulk updating settings: {e}")
        db.rollback()
        return False
    finally:
        cursor.close()
        db.close()