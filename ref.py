import uuid

def generate_reference_number():
    uuid_str = str(uuid.uuid4()).replace("-", "").upper()  # Remove any dashes and make uppercase
    first_segment = uuid_str[:8]
    second_segment = uuid_str[8:11]
    return f"REF-{first_segment}{second_segment}"

# Example usage:
print(generate_reference_number())
