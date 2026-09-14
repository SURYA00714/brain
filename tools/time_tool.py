import time
from datetime import datetime


def get_current_time():
    """
    Returns the current local time in a user-friendly natural format.
    Uses standard library datetime only.
    """
    now = datetime.now()
    # Format e.g. "11:42 PM"
    formatted_time = now.strftime("%I:%M %p").lstrip("0")
    return f"It is {formatted_time}."
