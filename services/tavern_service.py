## 9. services/tavern_service.py - Tavern-Specific Service

def cleanup_tavern_events(tim_character, threshold_hours=24):
    """Cleanup old tavern events to prevent memory bloat"""
    tim_character.cleanup_tavern_state()