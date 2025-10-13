from storage import get_connection

def config(name, default=None):
    conn = get_connection()
    cursor = conn.cursor()  # ensures row is dict, if using MySQL connector
    cursor.execute("SELECT config_value FROM configs WHERE config_name = %s", (name,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return default

    value = row["config_value"]

    # Try to cast to int if it's numeric
    if value.isdigit():
        return int(value)

    # Try float if it looks like a decimal
    try:
        return float(value)
    except ValueError:
        return value

def email_activation_enabled():
    return bool(config("email_activation_enabled"))
