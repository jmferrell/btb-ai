from flask import Flask, request, jsonify
import time
import os
import random
import json
import logging
from logging.handlers import RotatingFileHandler
import logging
logger = logging.getLogger(__name__)
import os

# Set up logging
log_dir = "/home/pennboy/tech/claudeai/logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "claudeai.log")

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))

# Instead of app.logger.addHandler, use root logger:
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

# Log startup
logger.info('ClaudeAI MUSH Integration Server starting up')


# Import configuration
from config import BASE_DIR, CHARACTERS_DIR, AUTH_KEY, VALID_CHARACTERS, MAX_MESSAGE_LENGTH

# Import character factory
from characters.character_factory import CharacterFactory

app = Flask(__name__)

# Initialize character instances
character_instances = {}
for char_name in VALID_CHARACTERS:
    character = CharacterFactory.create_character(char_name)
    if character:
        character_instances[char_name] = character
        logger.info(f"Loaded character: {char_name}")
    else:
        logger.error(f"Failed to load character: {char_name}")

@app.route('/', methods=['POST'])
def index():
    try:
        # Check for POST parameters
        json_data = request.get_json()
        if not json_data:
            return jsonify({"message": "Failed: No JSON data provided"}), 400
        
        # Required fields with defaults for missing ones
        required_fields = {
            'text': '',
            'auth': '',
            'char': '',
            'speaker': 'Anonymous',
            'season': 'Spring',
            'weather': 'clear',
            'forecast': 'sunny',
            'time': 'afternoon',
            'visited': 'You have not visited before',
            'occupants': 'No one else is here',
            'type': 'event'  # Default type is now "event"
        }
        
        # Fill in missing fields with defaults
        for field, default in required_fields.items():
            if field not in json_data or not json_data[field]:
                json_data[field] = default

        # Extract and validate fields
        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()
        speaker = json_data['speaker'].strip()
        season = json_data['season'].strip()
        weather = json_data['weather'].strip()
        forecast = json_data['forecast'].strip()
        time_info = json_data['time'].strip()
        visited = json_data['visited'].strip()
        occupants = json_data['occupants'].strip()
        message_type = json_data.get('type', 'event')

        # Authentication check
        if len(auth) > 100 or auth != AUTH_KEY:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        if len(text) > MAX_MESSAGE_LENGTH:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(char) > 100 or char not in VALID_CHARACTERS:
            return jsonify({"message": "Failed: Invalid character reference"}), 400
            
        # Create context dict for passing to character methods
        context = {
            'season': season,
            'weather': weather, 
            'forecast': forecast,
            'time_info': time_info,
            'visited': visited,
            'occupants': occupants
        }

        # Check if character instance exists
        if char not in character_instances:
            return jsonify({"message": "Failed: Character not implemented"}), 400
            
        # Get character instance
        character = character_instances[char]
        
        # Special handling for Tim and tavern events
        if char == "tim":
            # Extract occupants and sync with Tim's memory on each request
            if "occupants" in json_data and json_data["occupants"]:
                character.sync_occupants_with_mush(json_data["occupants"])
                
            # Process tavern events differently
            response_text = character.process_tavern_event(speaker, text, message_type, context)
            
            # Run cleanup periodically (about every 10 requests)
            if random.random() < 0.1:  # 10% chance
                character.cleanup_tavern_state()
                
            # If Tim decided to respond, return the response
            if response_text:
                return jsonify({"message": response_text})
            else:
                # No response needed
                return jsonify({"message": ""})
        else:
            # For other characters, use the standard processing method
            response_text = character.process_message(speaker, text, context)
            
            if response_text:
                return jsonify({"message": response_text})
            else:
                return jsonify({"message": ""})

    except Exception as e:
        logger.error(f"General Error: {str(e)}")  # Enhanced error logging
        return jsonify({"message": f"Failed: Error - {str(e)}"}), 500

# Use port 5000 but allow it to be overridden
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Using the standard port 5000
    app.run(host='0.0.0.0', port=port)