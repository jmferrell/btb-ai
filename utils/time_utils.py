## 5. utils/time_utils.py - Time Utilities

import time
import datetime

def format_time_since(timestamp):
    """Convert a timestamp difference to human-readable time description"""
    now = time.time()
    diff_seconds = now - timestamp
    
    # Convert to minutes, hours, days
    minutes = diff_seconds / 60
    hours = minutes / 60
    days = hours / 24
    
    if minutes < 1:
        return "just moments ago"
    elif minutes < 60:
        return f"about {int(minutes)} minute{'s' if int(minutes) != 1 else ''} ago"
    elif hours < 24:
        return f"about {int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    elif days < 7:
        return f"about {int(days)} day{'s' if int(days) != 1 else ''} ago"
    else:
        weeks = days / 7
        if weeks < 4:
            return f"about {int(weeks)} week{'s' if int(weeks) != 1 else ''} ago"
        else:
            return "several weeks ago"

def get_time_context(timestamp):
    """Return context about when something happened in terms of time of day"""
    dt = datetime.datetime.fromtimestamp(timestamp)
    hour = dt.hour
    
    if hour >= 5 and hour < 12:
        return "morning"
    elif hour >= 12 and hour < 17:
        return "afternoon"
    elif hour >= 17 and hour < 21:
        return "evening"
    else:
        return "night"