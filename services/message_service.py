## 8. services/message_service.py - Message Buffer Management

import time

# Global message buffer
message_buffer = []


def add_message(role, content, character):
    """Add a message to the buffer with enhanced organization"""
    global message_buffer

    # Create the new message
    new_message = {
        "role": role,
        "content": content,
        "timestamp": time.time(),
        "character": character,
    }

    # Add the message to the buffer
    message_buffer.append(new_message)

    # Group messages by character
    character_messages = {}
    for msg in message_buffer:
        char = msg["character"]
        if char not in character_messages:
            character_messages[char] = []
        character_messages[char].append(msg)

    # Create a new buffer with only the last 30 messages per character
    updated_buffer = []
    for char, msgs in character_messages.items():
        # Sort by timestamp to ensure chronological order
        sorted_msgs = sorted(msgs, key=lambda x: x["timestamp"])
        # Keep only the most recent 30 messages for each character
        updated_buffer.extend(sorted_msgs[-30:])

    # Update the global buffer and sort by timestamp
    message_buffer = sorted(updated_buffer, key=lambda x: x["timestamp"])


def get_char_messages(character):
    """Return only messages for the specified character in the correct format for Claude API"""
    filtered_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in message_buffer
        if msg.get("character") == character
    ]

    # Always return messages in chronological order
    return filtered_messages


def get_message_buffer():
    """Return the entire message buffer (for debugging or analysis)"""
    return message_buffer


def flush_old_messages(character_name, max_age_hours=3):
    """
    Remove messages older than max_age_hours for a specific character
    to prevent confusion with very old context
    """
    global message_buffers
    if character_name in message_buffers:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        # Keep only messages newer than max_age_hours
        message_buffers[character_name] = [
            msg
            for msg in message_buffers[character_name]
            if (current_time - msg.get("timestamp", 0) < max_age_seconds)
            or msg.get("role") == "system"  # Always keep system messages
        ]

        return len(message_buffers[character_name])
    return 0
