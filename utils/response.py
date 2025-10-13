def success(message, data=None):
    return {"status": "success", "message": message, "data": data}

def error(message, data=None):
    return {"status": "error", "message": message, "data": data}
