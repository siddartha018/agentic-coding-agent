def get_status_message(status_code):
    """Return a status message for the given code."""
    messages = {
        200: "Sucess",
        404: "Not Found",
        500: "Server Error"
    }
    return messages.get(status_code, "Unknown")
