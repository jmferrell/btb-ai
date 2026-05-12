import os
import json
import time
import logging
import datetime
from abc import ABC, abstractmethod

from utils.time_utils import format_time_since, get_time_context
from utils.sentiment_utils import analyze_sentiment
from services.claude_service import get_claude_response
from services.message_service import add_message, get_char_messages


class BaseCharacter(ABC):
    """Base class for all MUSH characters"""

    def __init__(self, name):
        """Initialize the character with name and basic attributes"""
        self.name = name
        self.character_dir = os.path.join(
            os.environ.get("CHARACTERS_DIR", "characters"), name
        )

        # Set up logging for this instance
        self.logger = logging.getLogger(f"characters.{name}")

        self.memories = self._load_character_memories()
        self.config = self._load_character_config()

    def process_message(self, speaker, text, context=None):
        """Process an incoming message and generate a response"""
        # Default context if none provided
        if context is None:
            context = {
                "season": "Spring",
                "weather": "clear",
                "forecast": "fair",
                "time_info": "afternoon",
                "visited": "",
                "occupants": "",
            }

        # Extract actual speaker if message is from a tavern location
        actual_speaker = self._extract_actual_speaker(speaker, text)

        # Add message to buffer
        add_message("user", text, self.name)

        # Update memory with current environment info
        self._update_environment_info(actual_speaker, context)

        # Prepare prompt and get response
        system_prompt = self._prepare_prompt(actual_speaker, context)
        char_messages = get_char_messages(self.name)

        response = get_claude_response(system_prompt, char_messages)

        if not response:
            return ""

        # Add to message buffer
        add_message("assistant", response, self.name)

        # Update memory with the interaction
        self._update_memory_with_interaction(actual_speaker, text, response)

        # Check for memory commands
        self._check_for_memory_commands(actual_speaker, text, response)

        return response

    def _extract_actual_speaker(self, speaker, text):
        """Extract the actual speaker from tavern-formatted messages"""
        if speaker == "From" and text.startswith("From "):
            parts = text.split(", ", 1)
            if len(parts) > 1 and " says, " in parts[1]:
                actual_speaker = parts[1].split(" says, ", 1)[0]
                self.logger.debug(
                    f"Extracted speaker '{actual_speaker}' from tavern location message"
                )
                return actual_speaker
        return speaker

    def _extract_message_content(self, text):
        """Extract the actual message content from tavern-formatted messages"""
        if text.startswith("From ") and ", " in text:
            parts = text.split(", ", 1)
            if len(parts) > 1 and " says, " in parts[1]:
                content = parts[1].split(" says, ", 1)[1]
                self.logger.debug(f"Extracted message content: '{content}'")
                return content
        return text

    def _load_character_memories(self):
        """Load character-specific memories from file"""
        memory_file = os.path.join(self.character_dir, f"{self.name}_memories.json")

        if not os.path.exists(memory_file):
            # Initialize empty memory structure
            memories = {"players": {}, "last_updated": time.time()}
            # Ensure the directory exists
            os.makedirs(os.path.dirname(memory_file), exist_ok=True)
            # Save the initial empty structure
            with open(memory_file, "w") as f:
                json.dump(memories, f, indent=2)
            return memories

        try:
            with open(memory_file, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading character memories for {self.name}: {e}")
            return {"players": {}, "last_updated": time.time()}

    def _load_character_config(self):
        """Load character-specific configuration from JSON file"""
        config_file = os.path.join(self.character_dir, f"{self.name}.json")

        if not os.path.exists(config_file):
            # Return default config for now
            return {
                "schedules": {},
                "relationship_rules": {
                    "friendship_threshold": 50,
                    "starting_affinity": 0,
                },
                "personality": {},
                "dialogue_adaptations": {},
            }

        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading character config for {self.name}: {e}")
            return {}

    def _save_character_memories(self):
        """Save character memories to file"""
        memory_file = os.path.join(self.character_dir, f"{self.name}_memories.json")

        try:
            with open(memory_file, "w") as f:
                json.dump(self.memories, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving character memories for {self.name}: {e}")
            return False

    def _update_environment_info(self, speaker, context):
        """Update environment info in character memory"""
        # Initialize structures if they don't exist
        if "known_players" not in self.memories:
            self.memories["known_players"] = {}
        if "environment_history" not in self.memories:
            self.memories["environment_history"] = []

        # Add current environment to history (keep last 5)
        self.memories["environment_history"].append(
            {
                "time": context.get("time_info", "afternoon"),
                "season": context.get("season", "Spring"),
                "weather": context.get("weather", "clear"),
                "forecast": context.get("forecast", "fair"),
                "occupants": context.get("occupants", ""),
                "timestamp": time.time(),
            }
        )

        # Keep only most recent 5 environment snapshots
        self.memories["environment_history"] = self.memories["environment_history"][-5:]

        # Update player info
        if speaker not in self.memories["known_players"]:
            self.memories["known_players"][speaker] = {
                "first_seen": time.time(),
                "visit_count": 1,
                "last_visit": time.time(),
            }
        else:
            # Store previous visit for time gap calculations
            self.memories["known_players"][speaker]["previous_visit"] = self.memories[
                "known_players"
            ][speaker]["last_visit"]
            self.memories["known_players"][speaker]["visit_count"] += 1
            self.memories["known_players"][speaker]["last_visit"] = time.time()

        self.memories["last_updated"] = time.time()

        # Save updates to file
        self._save_character_memories()

    def _update_memory_with_interaction(self, speaker, player_text, char_response):
        """Update memory with new interaction details"""
        interaction_time = time.time()
        sentiment_score = analyze_sentiment(player_text)

        # Add to recent events
        if "recent_events" not in self.memories:
            self.memories["recent_events"] = []

        self.memories["recent_events"].append(
            {
                "player": speaker,
                "player_said": player_text,
                "char_response": char_response,
                "timestamp": interaction_time,
                "time_of_day": get_time_context(interaction_time),
                "sentiment": sentiment_score,
            }
        )

        # Keep only last 10 events
        self.memories["recent_events"] = self.memories["recent_events"][-10:]

        # Update relationship
        self._update_relationship(speaker, sentiment_score)

        # Save updates to file
        self._save_character_memories()

    def _update_relationship(self, speaker, sentiment_score):
        """Update the relationship between character and player"""
        # Ensure relationships structure exists
        if "relationships" not in self.memories:
            self.memories["relationships"] = {}

        # Initialize relationship if it doesn't exist
        if speaker not in self.memories["relationships"]:
            starting_affinity = self.config.get("relationship_rules", {}).get(
                "starting_affinity", 0
            )
            self.memories["relationships"][speaker] = {
                "affinity": starting_affinity,
                "trust": 0,
                "last_interaction": time.time(),
                "tags": [],
            }

        rel = self.memories["relationships"][speaker]

        # Update affinity based on sentiment
        impact = sentiment_score * 5.0  # Scale factor
        rel["affinity"] += impact

        # Keep affinity in bounds (-100 to 100)
        rel["affinity"] = max(-100, min(100, rel["affinity"]))

        # Update trust based on interaction frequency and consistency
        if (
            "known_players" in self.memories
            and speaker in self.memories["known_players"]
        ):
            visit_count = self.memories["known_players"][speaker]["visit_count"]
            time_since_last = time.time() - rel["last_interaction"]

            # Regular visitors gain more trust
            if visit_count > 3 and time_since_last < 7 * 24 * 3600:  # Within a week
                rel["trust"] += 2

            # Trust increases with positive interactions
            if sentiment_score > 0:
                rel["trust"] += sentiment_score * 3

            # Keep trust in bounds (0 to 100)
            rel["trust"] = max(0, min(100, rel["trust"]))

            # Update relationship tags
            friendship_threshold = self.config.get("relationship_rules", {}).get(
                "friendship_threshold", 50
            )

            if rel["affinity"] > friendship_threshold and "friend" not in rel["tags"]:
                rel["tags"].append("friend")
            elif rel["affinity"] < friendship_threshold and "friend" in rel["tags"]:
                rel["tags"].remove("friend")

            if visit_count > 5 and "regular" not in rel["tags"]:
                rel["tags"].append("regular")

        # Store last interaction time
        rel["last_interaction"] = time.time()

    def _get_relationship_status(self, speaker):
        """Get the current relationship status with this speaker"""
        if (
            "relationships" not in self.memories
            or speaker not in self.memories["relationships"]
        ):
            return "neutral"

        rel = self.memories["relationships"][speaker]
        friendship_threshold = self.config.get("relationship_rules", {}).get(
            "friendship_threshold", 50
        )

        if rel["affinity"] > friendship_threshold:
            return "friend"
        elif rel["affinity"] < -20:
            return "unfriendly"
        else:
            return "neutral"

    def _get_time_awareness_context(self, speaker, current_time=None):
        """
        Generate time awareness context about interactions with a specific person
        This helps characters understand how much time has passed since they last saw someone
        """
        if current_time is None:
            current_time = time.time()

        # Initialize with default values
        time_context = {
            "is_first_interaction": True,
            "is_new_day": False,
            "time_since_last": None,
            "hours_since_last": 0,
            "days_since_last": 0,
            "last_interaction_time_of_day": None,
            "current_time_of_day": get_time_context(current_time),
            "time_description": "first meeting",
            "prompt_guidance": "This appears to be your first interaction with this person. Introduce yourself appropriately.",
        }

        try:
            # Find the most recent interaction with this speaker
            last_interaction = self._get_last_interaction(speaker)
            if not last_interaction:
                # FIX: Fall back to known_players data before declaring first interaction.
                # recent_events only holds the last 10 interactions across ALL players,
                # so a known visitor can fall out of it even though they're well remembered.
                if (
                    "known_players" in self.memories
                    and speaker in self.memories["known_players"]
                ):
                    player_data = self.memories["known_players"][speaker]
                    if player_data.get("visit_count", 0) > 1:
                        time_context["is_first_interaction"] = False
                        # Use previous_visit if available, otherwise last_visit
                        ref_time = player_data.get(
                            "previous_visit", player_data.get("last_visit", 0)
                        )
                        if ref_time > 0:
                            time_since = current_time - ref_time
                            time_context["time_since_last"] = time_since
                            time_context["hours_since_last"] = time_since / 3600
                            time_context["days_since_last"] = time_since / (3600 * 24)
                            time_context["last_interaction_time_of_day"] = get_time_context(ref_time)
                            self._set_time_guidance(time_context)
                        else:
                            time_context["prompt_guidance"] = (
                                f"You know {speaker} well — they've visited {player_data['visit_count']} times. "
                                "Greet them as a familiar face, not a stranger."
                            )
                        self.logger.debug(
                            f"TIME AWARENESS: No recent_events for {speaker} but found "
                            f"{player_data['visit_count']} visits in known_players — treating as known."
                        )
                return time_context

            # Not the first interaction
            time_context["is_first_interaction"] = False
            last_interaction_time = last_interaction["timestamp"]
            time_context["last_interaction_content"] = last_interaction["char_response"]

            # Validate timestamp
            if (
                last_interaction_time <= 0
                or last_interaction_time > time.time() + 86400
            ):
                self.logger.warning(
                    f"Invalid timestamp: {last_interaction_time}, using current - 1hr"
                )
                last_interaction_time = current_time - 3600  # Assume 1 hour ago

            # Calculate time differences
            time_since_last = current_time - last_interaction_time
            time_context["time_since_last"] = time_since_last
            time_context["hours_since_last"] = time_since_last / 3600
            time_context["days_since_last"] = time_since_last / (3600 * 24)
            time_context["last_interaction_time_of_day"] = get_time_context(
                last_interaction_time
            )

            # Check if it's a new day
            try:
                last_date = datetime.datetime.fromtimestamp(
                    last_interaction_time
                ).date()
                current_date = datetime.datetime.fromtimestamp(current_time).date()

                if current_date > last_date:
                    time_context["is_new_day"] = True
                    time_context["days_since_last"] = (current_date - last_date).days
            except (ValueError, OverflowError) as dt_err:
                self.logger.warning(
                    f"Datetime error: {dt_err}, using simpler calculation"
                )
                if (
                    time_context["hours_since_last"] > 20
                ):  # Assume new day after 20+ hours
                    time_context["is_new_day"] = True
                    time_context["days_since_last"] = (
                        time_context["hours_since_last"] // 24
                    )

            # Generate time description and guidance
            self._set_time_guidance(time_context)

        except Exception as e:
            self.logger.error(f"Error calculating time awareness: {e}")
            # Return safe defaults
            time_context = {
                "is_first_interaction": False,
                "is_new_day": False,
                "time_description": "some time ago",
                "current_time_of_day": get_time_context(current_time),
                "prompt_guidance": "Treat this as a fresh conversation - avoid specific time references.",
            }

        return time_context

    def _get_last_interaction(self, speaker):
        """Get the most recent interaction with a specific speaker"""
        if "recent_events" not in self.memories:
            return None

        # Filter events for this speaker
        speaker_events = [
            e for e in self.memories["recent_events"] if e["player"] == speaker
        ]

        if not speaker_events:
            return None

        # Return the most recent
        return speaker_events[-1]

    def _set_time_guidance(self, time_context):
        """Set the time description and guidance based on time context"""
        if time_context["is_new_day"]:
            if time_context["days_since_last"] == 1:
                time_context["time_description"] = "yesterday"
                time_context["prompt_guidance"] = (
                    "- It's a NEW DAY since you last saw them - acknowledge this naturally\n"
                    "- They were here YESTERDAY and now they've returned today\n"
                    '- Greet them with appropriate "good morning/afternoon/evening" and acknowledge it\'s a new day'
                )
            else:
                days = int(time_context["days_since_last"])
                time_context["time_description"] = f"{days} days ago"
                time_context["prompt_guidance"] = (
                    f"- It's been SEVERAL DAYS ({days}) since you last saw them\n"
                    "- This is NOT a continuation of your previous conversation - significant time has passed\n"
                    "- Acknowledge the multi-day gap naturally\n"
                    "- Consider referencing the change in weather or season if relevant"
                )
        elif time_context["hours_since_last"] > 6:
            hours = int(time_context["hours_since_last"])
            time_context["time_description"] = "several hours ago"
            time_context["prompt_guidance"] = (
                f"- It's been MANY HOURS ({hours} hours) since you last saw them\n"
                "- This is NOT a direct continuation of your previous conversation\n"
                "- Acknowledge the significant time gap naturally"
            )
        elif time_context["hours_since_last"] > 0.5:  # More than 30 minutes
            minutes = int(time_context["time_since_last"] / 60)
            time_context["time_description"] = f"{minutes} minutes ago"
            time_context["prompt_guidance"] = (
                f"- It's been a while ({minutes} minutes) since you last spoke with them\n"
                "- This should be treated as a new conversation, not a direct continuation"
            )
        else:  # Less than 30 minutes
            time_context["time_description"] = "just recently"
            time_context["prompt_guidance"] = (
                "- You just spoke with them very recently (less than 30 minutes ago)\n"
                "- This is a direct continuation of your previous conversation"
            )

    def _check_for_scheduled_events(self):
        """Check if there are any special scheduled events happening"""
        current_time = time.time()
        time_of_day = get_time_context(current_time)
        scheduled_activity = self._get_character_schedule(time_of_day)

        return {"time_of_day": time_of_day, "scheduled_activity": scheduled_activity}

    def _get_character_schedule(self, time_of_day):
        """Get what the character would be doing at this time of day"""
        schedules = self.config.get("schedules", {})
        return schedules.get(time_of_day, "going about their usual business")

    def _get_adaptive_dialogue_style(self, speaker):
        """Get the appropriate dialogue style based on relationship"""
        status = self._get_relationship_status(speaker)
        adaptations = self.config.get("dialogue_adaptations", {})
        style = adaptations.get(status, {})

        return {
            "status": status,
            "greeting": style.get("greeting", "greets"),
            "tone": style.get("tone", "neutral"),
            "speech_patterns": style.get("speech_patterns", ""),
        }

    def _check_for_memory_commands(self, speaker, user_text, char_response):
        """Check if the user is requesting to add a memory"""
        memory_phrases = [
            "remember that",
            "would you remember",
            "don't forget",
            "keep that in mind",
            "make a note of",
            "remember this",
            "please remember",
        ]

        # Extract actual content if this is a tavern speech message
        actual_text = self._extract_message_content(user_text)
        user_text_lower = actual_text.lower()

        # Check if any trigger phrases are in the user's text
        if not any(phrase in user_text_lower for phrase in memory_phrases):
            return False

        # Extract memory content
        memory_content = self._extract_memory_content(actual_text, char_response)
        if not memory_content:
            return False

        # Determine memory type
        memory_type = self._determine_memory_type(memory_content)

        # Determine importance
        importance = 5
        if any(
            term in memory_content.lower() for term in ["wife", "husband", "married"]
        ):
            importance = 8  # Marriage is important!

        # Add the memory
        added = self._add_permanent_memory(
            speaker, memory_type, memory_content, importance
        )
        self.logger.info(
            f"Added memory for {self.name} about {speaker}: {memory_content}"
        )

        return added

    def _extract_memory_content(self, user_text, context):
        """Extract what should be remembered from conversation context"""
        # Memory trigger phrases
        memory_triggers = [
            "remember that",
            "remember this:",
            "please remember",
            "would you remember that",
            "don't forget that",
        ]

        user_text_lower = user_text.lower()

        # Try each extraction method in order of priority

        # 1. Look for explicit content after memory triggers
        for trigger in memory_triggers:
            if trigger in user_text_lower:
                parts = user_text_lower.split(trigger, 1)
                if len(parts) > 1 and parts[1].strip():
                    memory = parts[1].strip().rstrip(".!?,;")
                    return memory[0].upper() + memory[1:] if memory else None

        # 2. Look for relationship info in context
        relationship_keywords = [
            "married to",
            "wife of",
            "husband of",
            "friend of",
            "brother",
            "sister",
        ]

        for keyword in relationship_keywords:
            if keyword in user_text_lower or keyword in context.lower():
                all_text = user_text + " " + context
                sentences = all_text.split(".")
                for sentence in sentences:
                    if keyword in sentence.lower():
                        memory = sentence.strip()
                        return memory[0].upper() + memory[1:] if memory else None

        # 3. Extract phrases after question patterns
        question_patterns = [
            "can you remember",
            "could you remember",
            "will you remember",
        ]

        for pattern in question_patterns:
            if pattern in user_text_lower:
                parts = user_text_lower.split(pattern, 1)
                if len(parts) > 1 and parts[1].strip():
                    memory = parts[1].strip().rstrip(".!?,;")
                    return memory[0].upper() + memory[1:] if memory else None

        # No match found
        return None

    def _determine_memory_type(self, memory_content):
        """Determine what type of memory this is"""
        memory_lower = memory_content.lower()

        # Check for relationship indicators
        relationship_terms = [
            "married",
            "wife",
            "husband",
            "friend",
            "brother",
            "sister",
            "parent",
            "child",
        ]
        if any(term in memory_lower for term in relationship_terms):
            return "relationships"

        # Check for preference indicators
        preference_terms = [
            "likes",
            "prefers",
            "enjoys",
            "favorite",
            "hates",
            "dislikes",
        ]
        if any(term in memory_lower for term in preference_terms):
            return "preferences"

        # Default to facts
        return "facts"

    def _add_permanent_memory(self, player, memory_type, content, importance=5):
        """Add a permanent memory about a player"""
        # Initialize player entry if needed
        if "players" not in self.memories:
            self.memories["players"] = {}

        if player not in self.memories["players"]:
            self.memories["players"][player] = {
                "facts": [],
                "preferences": [],
                "relationships": [],
                "last_updated": time.time(),
            }

        # Create memory entry
        memory_entry = {
            "content": content,
            "timestamp": time.time(),
            "importance": importance,
        }

        # Add to appropriate category (create if doesn't exist)
        if memory_type not in self.memories["players"][player]:
            self.memories["players"][player][memory_type] = []

        # Check for duplicates
        existing_contents = [
            m["content"].lower() for m in self.memories["players"][player][memory_type]
        ]

        if content.lower() not in existing_contents:
            self.memories["players"][player][memory_type].append(memory_entry)

        # Update timestamps
        self.memories["players"][player]["last_updated"] = time.time()
        self.memories["last_updated"] = time.time()

        # Save back to file
        return self._save_character_memories()

    def _get_relevant_permanent_memories(self, player, max_memories_per_category=2):
        """Get the most relevant permanent memories for a character-player interaction"""
        if player not in self.memories.get("players", {}):
            return {}

        player_memories = self.memories["players"][player]
        relevant_memories = {}
        categories = ["facts", "preferences", "relationships"]

        # For each category, get the most important memories
        for category in categories:
            if category in player_memories and player_memories[category]:
                # Sort by importance (primary) and recency (secondary)
                sorted_memories = sorted(
                    player_memories[category],
                    key=lambda x: (x.get("importance", 0) * 10000)
                    + x.get("timestamp", 0),
                    reverse=True,
                )

                # Take only the top N memories
                relevant_memories[category] = sorted_memories[
                    :max_memories_per_category
                ]

        return relevant_memories

    def _format_memory_for_prompt(self, current_speaker):
        """Format memory information for inclusion in prompt with time awareness"""
        # Start with memory header
        memory_prompt = "MEMORY AND CONTEXT INFORMATION:\n"

        # Get time awareness context
        time_context = self._get_time_awareness_context(current_speaker)

        # Add time awareness section
        memory_prompt += "\nTIME AWARENESS:\n"
        if time_context["is_first_interaction"]:
            memory_prompt += "- This is the first time you've met this person.\n"
        else:
            memory_prompt += f"- You last saw {current_speaker} {time_context['time_description']} in the {time_context['last_interaction_time_of_day']}.\n"
            memory_prompt += f"- It is now the {time_context['current_time_of_day']}.\n"

            # Add special guidance for new days
            if time_context["is_new_day"]:
                memory_prompt += "- It's a new day since you last saw them.\n"

            # Add guidance based on time context
            memory_prompt += f"{time_context['prompt_guidance']}\n"

        # Add permanent memories if available
        permanent_memories = self._get_relevant_permanent_memories(current_speaker)
        if permanent_memories:
            self._add_memories_to_prompt(memory_prompt, permanent_memories)

        # Add schedule context
        schedule_info = self._check_for_scheduled_events()
        activity = schedule_info["scheduled_activity"]
        memory_prompt += f"\nYour current activities: It's {schedule_info['time_of_day']} and you would normally be {activity}.\n"

        # Add final guidance
        memory_prompt += "\n\nIMPORTANT: Use this memory information naturally in your responses when it makes sense to do so. Don't explicitly mention that you remember things or mention 'hours ago' - instead, reference the time of day or use natural language like 'this morning', 'yesterday', etc."

        return memory_prompt

    def _add_memories_to_prompt(self, memory_prompt, permanent_memories):
        """Add permanent memories to the prompt"""
        memory_prompt += "\nIMPORTANT THINGS YOU REMEMBER ABOUT THIS PERSON:\n"

        # Add facts
        if "facts" in permanent_memories and permanent_memories["facts"]:
            for fact in permanent_memories["facts"]:
                memory_prompt += f"- {fact['content']}\n"

        # Add relationships
        if (
            "relationships" in permanent_memories
            and permanent_memories["relationships"]
        ):
            for rel in permanent_memories["relationships"]:
                memory_prompt += f"- {rel['content']}\n"

        # Add preferences
        if "preferences" in permanent_memories and permanent_memories["preferences"]:
            memory_prompt += "\nTHIS PERSON'S PREFERENCES:\n"
            for pref in permanent_memories["preferences"]:
                memory_prompt += f"- {pref['content']}\n"

        return memory_prompt

    def _fill_prompt_template(self, prompt_template, speaker, context):
        """Fill in the standard placeholder values in a prompt template"""
        return prompt_template.format(
            s=speaker,
            n=context.get("season", "Spring"),
            t=context.get("time_info", "afternoon"),
            w=context.get("weather", "clear"),
            f=context.get("forecast", "fair"),
            o=context.get("occupants", "No one else is here"),
            v=context.get("visited", "You have not visited before"),
            ######################## ADD NEW FIELDS HERE #######
        )

    @abstractmethod
    def _prepare_prompt(self, speaker, context):
        """
        Prepare the system prompt for this character
        Must be implemented by subclasses
        """
        pass
