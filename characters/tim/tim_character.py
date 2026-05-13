import os
import json
import time
import random
import logging

from characters.base_character import BaseCharacter
from utils.time_utils import format_time_since, get_time_context

# Define the log directory path - we'll need this for the file handler
logic_log_dir = "/home/pennboy/tech/claudeai/logs"
os.makedirs(logic_log_dir, exist_ok=True)
logic_log_file = os.path.join(logic_log_dir, "tim_logic.log")


class TimCharacter(BaseCharacter):
    """Tim the tavern keeper character implementation"""

    def __init__(self):
        super().__init__("tim")

        # Set up special logging for Tim's decision logic
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG level explicitly

        # Create a dedicated file handler for Tim's decision logic
        tim_logic_handler = logging.FileHandler(logic_log_file)
        tim_logic_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        tim_logic_handler.setLevel(logging.DEBUG)  # Capture all details

        # Add the handler to Tim's logger
        self.logger.addHandler(tim_logic_handler)

        # Initialize tavern state
        self.tavern_state = self._initialize_tavern_state()
        self.logger.debug("Tim character initialized")

    def _initialize_tavern_state(self):
        """Initialize tavern-specific state in memory"""
        if "tavern_state" not in self.memories:
            self.memories["tavern_state"] = {
                "current_occupants": [],
                "entry_events": [],
                "exit_events": [],
                "visitor_history": {},
                "last_update": time.time(),
            }
            self._save_character_memories()

        return self.memories["tavern_state"]

    def process_tavern_event(self, speaker, text, event_type="event", context=None):
        """Process any event happening in the tavern and determine if Tim should respond"""
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

        # CRITICAL: Sync Tim's memory with MUSH reality on EVERY event
        # This prevents Tim from hallucinating people who have left
        if context and 'occupants' in context and context['occupants']:
            self.sync_occupants_with_mush(context['occupants'])
            self.logger.info(f"Synced with MUSH occupants: {context['occupants']}")

        # Store current time for this interaction
        current_time = time.time()

        # Update environment info
        self._update_environment_info(speaker, context)

        # Classify the event more specifically based on content
        classified_event = self._classify_event(text)
        self.logger.debug(f"Classified event: '{text}' as '{classified_event}'")

        # Handle bar seating specially
        if classified_event == "bar_seating":
            # Extract person name
            person = text.split(" takes a seat at the Bar")[0].strip()
            self.logger.info(f"Processing Bar seating for: {person}")

            # Add to current occupants if not already there
            if person not in self.tavern_state["current_occupants"]:
                self.tavern_state["current_occupants"].append(person)

            # Always respond to someone sitting at the bar
            self.logger.debug(
                f"Someone is sitting at the bar - Tim will always respond to this"
            )
            return self._generate_bar_greeting(person, context)

        # Handle bar direct speech
        elif classified_event == "bar_direct_speech":
            # Extract the actual content and speaker after "From the Bar,"
            bar_content = text[len("From the Bar,") :].strip()
            actual_speaker = bar_content.split(" says, ")[0].strip()
            content = bar_content.split(" says, ", 1)[1].strip()

            from services.message_service import add_message

            add_message("user", content, self.name)

            # Let the regular relevance assessment handle this with the correct speaker
            relevance_score, should_respond = self._assess_event_relevance(
                actual_speaker, content, classified_event
            )

            if should_respond:
                # Process as direct speech
                return self._handle_direct_speech(actual_speaker, content, context)

        # Handle bar conversations and actions
        elif classified_event == "bar_conversation":
            # Extract the actual content and speaker after "From the Bar,"
            bar_content = text[len("From the Bar,") :].strip()
            actual_speaker = bar_content.split(" says, ")[0].strip()
            content = bar_content.split(" says, ", 1)[1].strip()

            from services.message_service import add_message

            add_message("user", content, self.name)

            # Check if Tim should chime in
            relevance_score, should_respond = self._assess_event_relevance(
                actual_speaker, content, classified_event
            )

            if should_respond:
                # Generate a bar conversation response
                return self._generate_bar_conversation_response(
                    actual_speaker, content, classified_event, context
                )

        # Handle bar actions
        elif classified_event == "bar_action":
            # Extract the actual content after "From the Bar,"
            bar_content = text[len("From the Bar,") :].strip()
            # For actions, first word is typically the actor
            parts = bar_content.split(" ", 1)
            actual_speaker = parts[0].strip()
            content = bar_content

            from services.message_service import add_message

            add_message("user", content, self.name)

            # Check if Tim should chime in
            relevance_score, should_respond = self._assess_event_relevance(
                actual_speaker, content, classified_event
            )

            if should_respond:
                # Generate a bar conversation response
                return self._generate_bar_conversation_response(
                    actual_speaker, content, classified_event, context
                )

        # Track arrivals and respond
        elif classified_event == "true_arrival":
            # Extract person name - handle both door and Pass-Out Room arrivals
            if "enters through" in text:
                person = text.split(" enters through")[0].strip()
            elif "wanders in from" in text:
                person = text.split(" wanders in from")[0].strip()
            else:
                person = text.split(" ")[0].strip()  # fallback: first word

            self.logger.info(f"Processing TRUE arrival for: {person}")
            self._update_tavern_occupants(person, "enter")

            if self._should_greet_arrival(person):
                return self._generate_greeting_response(person, context)

        # Track departures but don't respond
        elif classified_event == "true_departure":
            # Extract person name
            person = text.split(" pulls open")[0].strip()
            if not person:  # Try alternate pattern
                person = text.split(" opens")[0].strip()

            self.logger.debug(f"Tracking departure for: {person} (not responding)")
            self._update_tavern_occupants(person, "exit")
            return ""  # Don't generate a response

        # Simply ignore generic notifications
        elif (
            classified_event == "generic_arrival"
            or classified_event == "generic_departure"
        ):
            self.logger.debug(f"Ignoring generic arrival/departure message: {text}")
            return ""

        # For all other events, determine relevance and whether Tim should respond
        relevance_score, should_respond = self._assess_event_relevance(
            speaker, text, classified_event
        )

        # If relevant enough, generate a response
        if should_respond:
            # Add message to buffer
            from services.message_service import add_message

            add_message("user", text, self.name)

            # Use the standard prompt with memories included
            return super().process_message(speaker, text, context)

        # If not relevant enough to respond
        return ""

    def _classify_event(self, text):
        """Classify what type of event this is based on text patterns"""
        text_lower = text.lower()

        # Check for Bar conversations
        if text.startswith("From "):
            # Extract the actual content after "From X,"
            if ", " in text:
                location_part, content_part = text.split(", ", 1)

                # Check if it's direct speech to Tim
                if (
                    " says, " in content_part
                    and "tim" in content_part.split(" says, ", 1)[1].lower()
                ):
                    return (
                        "bar_direct_speech"
                        if "Bar" in location_part
                        else "direct_speech"
                    )

                # NEW: Check if it's a response to an offer (yes/no/thanks responses)
                if " says, " in content_part:
                    response_text = content_part.split(" says, ", 1)[1].lower()
                    if any(
                        term in response_text
                        for term in [
                            "thanks",
                            "thank you",
                            "no thanks",
                            "yes please",
                            "not now",
                            "maybe later",
                            "sure",
                            "please",
                        ]
                    ):
                        self.logger.debug(
                            f"Detected response to an offer: '{response_text}'"
                        )
                        return "response_to_offer"

                # Check if it's someone else talking
                if " says, " in content_part:
                    return (
                        "bar_conversation"
                        if "Bar" in location_part
                        else "ambient_speech"
                    )

                # Must be an action/emote
                return "bar_action" if "Bar" in location_part else "general_action"

        # Check for Bar seating
        if "takes a seat at the Bar" in text:
            return "bar_seating"

        # Check for actual arrivals (entering through the door)
        if ("enters through" in text and "door" in text) or "wanders in from The Pass-Out Room" in text:
            return "true_arrival"

        # Generic arrival notification - we want to ignore for responses
        if text.endswith(" has arrived."):
            return "generic_arrival"

        # Track departures for memory, but don't respond
        if (
            ("pulls open" in text or "opens" in text)
            and "door" in text
            and ("heads outside" in text or "leaves" in text)
        ):
            return "true_departure"

        if text.endswith(" has left."):
            return "generic_departure"

        # Check for speech patterns
        if " says, " in text:
            # Extract what's said
            said_text = text.split(" says, ", 1)[1].lower()
            # Check if it's directed at Tim (contains "tim" or is just "tim?")
            if "tim" in said_text:
                return "direct_speech"
            # NEW: Check if it's a response to an offer (yes/no/thanks responses)
            elif any(
                term in said_text
                for term in [
                    "thanks",
                    "thank you",
                    "no thanks",
                    "yes please",
                    "not now",
                    "maybe later",
                    "sure",
                    "please",
                ]
            ):
                self.logger.debug(f"Detected response to an offer: '{said_text}'")
                return "response_to_offer"
            else:
                return "ambient_speech"

        # Check for different types of actions/emotes
        action_types = {
            "emotional": [
                "smile",
                "frown",
                "laugh",
                "sigh",
                "glare",
                "wince",
                "tears",
                "grin",
                "scowl",
            ],
            "tavern_related": [
                "drink",
                "glass",
                "mug",
                "coin",
                "ducats",
                "payment",
                "tab",
                "ale",
                "beer",
                "wine",
            ],
            "physical": [
                "sits",
                "stands",
                "walks",
                "moves",
                "places",
                "takes",
                "gives",
                "puts",
                "picks up",
            ],
            "social": ["wave", "nod", "greet", "bow", "handshake", "gesture", "wink"],
        }

        event_category = "general_action"

        # Categorize by action type
        for category, keywords in action_types.items():
            if any(keyword in text_lower for keyword in keywords):
                event_category = category
                break

        # Check if action is directed at Tim
        if "tim" in text_lower:
            event_category = "tim_directed_" + event_category

        return event_category

    def _assess_event_relevance(self, speaker, event_text, event_type):
        """Determine how relevant an event is for Tim to respond to"""
        relevance_score = 0

        # Initialize all score components for debugging
        timing_score = 0
        event_type_score = 0
        direct_mention_score = 0
        relationship_score = 0
        item_score = 0
        last_speaker_score = 0
        tavern_activity_score = 0
        follow_up_score = 0
        response_score = 0  # NEW: Score for responses to offers
        empty_tavern_score = 0  # NEW: Score for when tavern is nearly empty

        # Get time since Tim last spoke
        time_since_last_spoke = 9999  # Default high value
        current_time = time.time()  # Define current_time FIRST

        # Find Tim's last message
        from services.message_service import get_message_buffer

        message_buffer = get_message_buffer()
        tim_messages = [
            m
            for m in message_buffer
            if m["character"] == self.name and m["role"] == "assistant"
        ]
        if tim_messages:
            time_since_last_spoke = current_time - tim_messages[-1]["timestamp"]

        # NEW: Check if this is a response to an offer
        if event_type == "response_to_offer":
            response_score = 40  # High score to ensure Tim responds to direct responses
            self.logger.debug(f"Response to offer: +{response_score} points")

        # NEW: Check if tavern is nearly empty (1-2 people)
        tavern_occupants = len(self.tavern_state.get("current_occupants", []))
        if tavern_occupants <= 2:
            empty_tavern_score = 15  # Boost score when tavern is empty
            self.logger.debug(
                f"Nearly empty tavern ({tavern_occupants} occupants): +{empty_tavern_score} points"
            )

        # Check if this is likely a follow-up to Tim's last message
        # Get the last few messages in sequence
        recent_messages = sorted(message_buffer, key=lambda x: x["timestamp"])[-5:]

        # Check if Tim was the last speaker
        if len(recent_messages) >= 2:
            last_message = recent_messages[-2]  # The message before the current one
            if (
                last_message["character"] == self.name
                and last_message["role"] == "assistant"
            ):
                # This is a direct follow-up to Tim's message
                time_since_tim = current_time - last_message["timestamp"]

                # Higher weight for quick responses (within 1 minute)
                if time_since_tim < 60:
                    # NEW: Check if Tim's last message contained an offer
                    last_tim_message = last_message["content"].lower()
                    made_offer = any(
                        term in last_tim_message
                        for term in [
                            "want",
                            "would you like",
                            "can i get you",
                            "how about",
                            "kettle",
                            "tea",
                            "coffee",
                            "drink",
                            "ale",
                            "beer",
                        ]
                    )

                    if made_offer:
                        follow_up_score = (
                            40  # Substantial boost for direct responses to offers
                        )
                        self.logger.debug(
                            f"Detected follow-up to Tim's offer: +{follow_up_score} points"
                        )
                    else:
                        follow_up_score = 25  # Regular boost for general follow-ups
                        self.logger.debug(
                            f"Detected follow-up to Tim's message: +{follow_up_score} points"
                        )
                elif time_since_tim < 300:  # Within 5 minutes
                    follow_up_score = 15  # Smaller boost for delayed follow-ups
                    self.logger.debug(
                        f"Detected delayed follow-up to Tim's message: +{follow_up_score} points"
                    )

                # If it's a question, even higher weight
                if "?" in event_text:
                    follow_up_score += 10
                    self.logger.debug(
                        f"Question detected in follow-up: +10 additional points"
                    )

        # Add the follow-up score to the total
        relevance_score += follow_up_score

        # Base relevance on timing - modified to be less harsh for quick responses
        if time_since_last_spoke < 10:  # Within 10 seconds of Tim speaking
            timing_score = -15  # Negative score but less severe
        elif time_since_last_spoke < 30:  # Within 30 seconds
            timing_score = -10  # Even less severe for slightly longer gaps
        elif time_since_last_spoke < 300:  # Within 5 minutes
            timing_score = 0  # Neutral
        else:
            timing_score = 10  # More likely to speak if he's been quiet a while

        relevance_score += timing_score

        # Event type scoring - enhanced for responses
        if event_type == "direct_speech" or event_type == "bar_direct_speech":
            event_type_score = 50  # Very high - almost always respond
        elif event_type == "response_to_offer":
            event_type_score = 35  # High - respond to offers most of the time
        elif event_type == "bar_seating":
            event_type_score = 50  # Also very high - bar is Tim's domain
        elif event_type == "bar_conversation":
            event_type_score = (
                25  # Medium-high - sometimes chime in on bar conversations
            )
        elif event_type == "bar_action":
            event_type_score = 20  # Medium - sometimes react to bar actions
        elif event_type.startswith("tim_directed_"):
            event_type_score = 40  # High - action directed at Tim
        elif event_type == "true_arrival" or event_type == "true_departure":
            event_type_score = 20  # Medium - acknowledge comings and goings sometimes
        elif event_type == "ambient_speech":
            event_type_score = 5  # Low - rarely respond to others' conversations
        elif event_type == "tavern_related":
            event_type_score = 15  # Medium-low - sometimes comment on tavern activities
        elif event_type == "emotional":
            event_type_score = 10  # Medium-low - sometimes react to emotional displays

        relevance_score += event_type_score

        # Direct mention scoring
        if (
            "tim" in event_text.lower()
            or "barkeep" in event_text.lower()
            or "tavern keeper" in event_text.lower()
        ):
            direct_mention_score = 35  # High - respond when mentioned
            relevance_score += direct_mention_score

        # Tavern-related items and activities
        tavern_keywords = [
            "drink",
            "ale",
            "beer",
            "wine",
            "mead",
            "glass",
            "mug",
            "jar",
            "bottle",
            "ducats",
            "coin",
            "money",
            "payment",
            "tab",
            "food",
            "meal",
            "table",
            "chair",
            "service",
            "order",
            "request",
            "menu",
            "special",
            "brew",
            "spill",
            "broke",
            "fight",
        ]

        tavern_activity_score = min(
            20, sum(3 for word in tavern_keywords if word in event_text.lower())
        )
        relevance_score += tavern_activity_score

        # Check relationship (if known)
        if (
            "relationships" in self.memories
            and speaker in self.memories["relationships"]
        ):
            rel = self.memories["relationships"][speaker]
            relationship_score = min(
                20, abs(rel["affinity"]) / 5
            )  # Up to 20 points based on relationship
            relevance_score += relationship_score

        # Check if speaker was the last person Tim spoke to
        if (
            hasattr(self.memories, "last_interaction_with")
            and self.memories["last_interaction_with"] == speaker
        ):
            last_speaker_score = 15  # Continuing an interaction
            relevance_score += last_speaker_score

        # Add response score for direct responses to offers
        relevance_score += response_score

        # Add empty tavern score
        relevance_score += empty_tavern_score

        # Add randomness to make Tim's responses less predictable
        # Higher randomness for ambient events, lower for direct interactions
        if (
            event_type.startswith("tim_directed_")
            or event_type == "direct_speech"
            or event_type == "response_to_offer"
        ):
            randomness = random.randint(
                -5, 5
            )  # Small random factor for direct interactions
        else:
            randomness = random.randint(
                -15, 15
            )  # Larger random factor for ambient events

        relevance_score += randomness

        # Calculate threshold - lower when tavern is empty or nearly empty
        base_threshold = 35

        # NEW: Lower the base threshold when tavern is nearly empty
        if tavern_occupants <= 1:  # Just the speaker
            base_threshold = 25
        elif tavern_occupants <= 3:  # Very few people
            base_threshold = 30

        busyness_adjustment = min(
            15, tavern_occupants * 3
        )  # Up to 15 points higher threshold when busy
        response_threshold = base_threshold + busyness_adjustment

        # REPLACE the existing logging with this enhanced version
        self.logger.debug("----- RESPONSE DECISION PROCESS -----")
        self.logger.debug(f"EVENT: '{event_text}'")
        self.logger.debug(f"SPEAKER: {speaker}")
        self.logger.debug(f"EVENT TYPE: {event_type}")
        self.logger.debug(f"TIME SINCE LAST SPOKE: {time_since_last_spoke:.1f} seconds")
        self.logger.debug("SCORE COMPONENTS:")
        self.logger.debug(f"- Timing score: {timing_score}")
        self.logger.debug(f"- Event type score: {event_type_score}")
        self.logger.debug(f"- Direct mention score: {direct_mention_score}")
        self.logger.debug(f"- Relationship score: {relationship_score}")
        self.logger.debug(f"- Tavern activity score: {tavern_activity_score}")
        self.logger.debug(f"- Last speaker score: {last_speaker_score}")
        self.logger.debug(f"- Follow-up score: {follow_up_score}")
        self.logger.debug(f"- Response to offer score: {response_score}")
        self.logger.debug(f"- Empty tavern score: {empty_tavern_score}")
        self.logger.debug(f"- Random factor: {randomness}")
        self.logger.debug(f"TOTAL SCORE: {relevance_score}")
        self.logger.debug(
            f"THRESHOLD: {response_threshold} (base {base_threshold} + busyness {busyness_adjustment})"
        )
        self.logger.debug(
            f"DECISION: {'RESPOND' if relevance_score >= response_threshold else 'IGNORE'}"
        )
        self.logger.debug("----------------------------------")

        return relevance_score, relevance_score >= response_threshold

    def _update_tavern_occupants(self, person, action_type="update"):
        """Track changes in tavern occupants for Tim"""
        current_time = time.time()

        # For enter/exit events
        if action_type == "enter":
            # Someone entered - extract name
            entrant = person

            # Skip processing if already considered present
            if entrant in self.tavern_state["current_occupants"]:
                self.logger.info(
                    f"{entrant} is already marked as present but re-entered — resetting for fresh greeting"
                )
                self.tavern_state["current_occupants"].remove(entrant)

            # Check if this is a rapid re-entry
            rapid_reentry = False
            repeat_visitor = False

            # Initialize visitor history if new
            if entrant not in self.tavern_state["visitor_history"]:
                self.tavern_state["visitor_history"][entrant] = {
                    "first_seen": current_time,
                    "last_exit": 0,
                    "last_entry": current_time,
                    "visit_count": 1,
                    "greeting_type": "full",  # Options: full, brief, nod, none
                }
            else:
                visitor = self.tavern_state["visitor_history"][entrant]
                # Only consider them returning if they were previously known to have left
                if visitor.get("last_exit", 0) > 0:
                    time_since_exit = current_time - visitor["last_exit"]
                    visitor["last_entry"] = current_time
                    visitor["visit_count"] += 1
                    repeat_visitor = True

                    # Determine greeting type based on time since last exit
                    if time_since_exit < 300:  # Less than 5 minutes
                        visitor["greeting_type"] = "nod"  # Just a nod or brief glance
                        rapid_reentry = True
                    elif time_since_exit < 1800:  # Less than 30 minutes
                        visitor["greeting_type"] = "brief"  # Brief acknowledgment
                    else:
                        visitor["greeting_type"] = "full"  # Full greeting
                else:
                    # They never left or were already here
                    visitor["greeting_type"] = "none"
                    self.logger.info(
                        f"{entrant} was never marked as having left, using 'none' greeting"
                    )

            # Record the entry with appropriate greeting type
            if entrant in self.tavern_state["visitor_history"]:
                greeting_type = self.tavern_state["visitor_history"][entrant].get(
                    "greeting_type", "none"
                )
            else:
                greeting_type = "none"

            entry_event = {
                "person": entrant,
                "timestamp": current_time,
                "acknowledged": False,
                "rapid_reentry": rapid_reentry,
                "repeat_visitor": repeat_visitor,
                "greeting_type": greeting_type,
            }

            self.tavern_state["entry_events"].append(entry_event)

            # Add to current occupants if not already there
            if entrant not in self.tavern_state["current_occupants"]:
                self.tavern_state["current_occupants"].append(entrant)

            self.logger.debug(
                f"Recorded entry of {entrant} into tavern (greeting: {entry_event['greeting_type']})"
            )

        elif action_type == "exit":
            # Someone left - extract name
            exiter = person

            # Initialize with some defaults for unknown exiters if needed
            if exiter not in self.tavern_state["visitor_history"]:
                self.tavern_state["visitor_history"][exiter] = {
                    "first_seen": current_time,
                    "last_exit": current_time,
                    "last_entry": current_time,
                    "visit_count": 1,
                    "greeting_type": "full",
                }
                self.logger.info(
                    f"Created new visitor history entry for departing visitor: {exiter}"
                )

            # Record exit time in visitor history
            self.tavern_state["visitor_history"][exiter]["last_exit"] = current_time

            # Determine exit type based on time spent
            rapid_exit = False
            time_spent = 0

            # Calculate time spent
            time_spent = current_time - self.tavern_state["visitor_history"][
                exiter
            ].get("last_entry", current_time)
            if time_spent < 300:  # Less than 5 minutes
                rapid_exit = True

            # Record the exit
            self.tavern_state["exit_events"].append(
                {
                    "person": exiter,
                    "timestamp": current_time,
                    "acknowledged": False,
                    "rapid_exit": rapid_exit,
                    "time_spent": time_spent,
                }
            )

            # Remove from current occupants
            if exiter in self.tavern_state["current_occupants"]:
                self.tavern_state["current_occupants"].remove(exiter)

            self.logger.info(
                f"Recorded exit of {exiter} from tavern (rapid: {rapid_exit})"
            )

        # Keep lists manageable
        self.tavern_state["entry_events"] = self.tavern_state["entry_events"][-10:]
        self.tavern_state["exit_events"] = self.tavern_state["exit_events"][-10:]

        # Update timestamp
        self.tavern_state["last_update"] = current_time

        # Save updates to file
        self._save_character_memories()

    def _should_greet_arrival(self, person):
        """Determine if Tim should greet someone who just arrived"""
        # Find the entry event
        for entry in self.tavern_state["entry_events"]:
            if entry["person"] == person and not entry["acknowledged"]:
                # Check greeting type
                greeting_type = entry.get("greeting_type", "full")
                if greeting_type == "none":
                    return False

                # Add randomness - don't always greet everyone
                if greeting_type == "nod" and random.random() < 0.3:
                    # 30% chance to skip greeting for rapid re-entries
                    self._acknowledge_tavern_event(
                        person, "entry"
                    )  # Mark as acknowledged anyway
                    return False

                return True

        return False

    def _acknowledge_tavern_event(self, person, event_type="entry"):
        """Mark that Tim has acknowledged someone's entry or exit"""
        if event_type == "entry":
            # Find and update the entry event
            for entry in self.tavern_state["entry_events"]:
                if entry["person"] == person and not entry["acknowledged"]:
                    entry["acknowledged"] = True
                    self.logger.info(
                        f"Marked entry of {person} as acknowledged by {self.name}"
                    )
                    self._save_character_memories()
                    break
        elif event_type == "exit":
            # Find and update the exit event
            for exit_event in self.tavern_state["exit_events"]:
                if exit_event["person"] == person and not exit_event["acknowledged"]:
                    exit_event["acknowledged"] = True
                    self.logger.info(
                        f"Marked exit of {person} as acknowledged by {self.name}"
                    )
                    self._save_character_memories()
                    break

    def _generate_greeting_response(self, person, context):
        """Generate an appropriate greeting for someone entering the tavern"""
        # Get time, season, weather info
        current_time = time.time()
        time_of_day = get_time_context(current_time)

        # Get visitor info
        visitor_info = {}
        greeting_style = "full"  # Default
        visit_count = 1  # Default

        visitor_info = self.tavern_state["visitor_history"].get(person, {})
        greeting_style = visitor_info.get("greeting_type", "full")
        visit_count = visitor_info.get("visit_count", 1)

        # Get relationship status
        relationship_status = self._get_relationship_status(person)

        # Create a special greeting context prompt for Claude
        greeting_context = f"""
        GREETING CONTEXT:
        - The person '{person}' has just entered your tavern
        - It's {context.get('time_info', 'afternoon')} and {context.get('weather', 'clear')}
        - This is {'their first visit' if visit_count == 1 else f'their {visit_count}th visit'} to your tavern
        - The greeting style should be {'a full welcome' if greeting_style == 'full' else 'brief' if greeting_style == 'brief' else 'just a quick nod or glance'}
        - Your relationship with them is {relationship_status}
        - They {' just left a short while ago and returned quickly' if greeting_style == 'nod' else ''}

        Based on this context, you should acknowledge their arrival in an appropriate, natural way. Keep your response brief (under 35 words) and authentic to your character as an Irish tavern keeper.
        """

        # Add user message to buffer
        from services.message_service import add_message

        add_message("user", f"{person} has entered the Tavern", self.name)

        # Format system prompt with memory and greeting context
        base_prompt = self._prepare_prompt(person, context)
        full_prompt = f"{base_prompt}\n\n{greeting_context}"

        # Get response from Claude API
        from services.message_service import get_char_messages
        from services.claude_service import get_claude_response

        char_messages = get_char_messages(self.name)
        greeting = get_claude_response(full_prompt, char_messages, max_tokens=150)

        if greeting:
            # Add to message buffer
            add_message("assistant", greeting, self.name)
            self._update_memory_with_interaction(
                            person, f"{person} entered the Tavern", greeting
                        )
            # Mark as acknowledged
            self._acknowledge_tavern_event(person, "entry")

            return greeting
        else:
            # Fallback if API fails
            fallback = f'Tim nods to {person}. "Welcome to the tavern."'
            add_message("assistant", fallback, self.name)
            return fallback

    def _generate_bar_greeting(self, person, context):
        """Generate a special greeting for someone sitting at the Bar"""
        # Get time context
        current_time = time.time()
        time_of_day = get_time_context(current_time)

        # PRIMARY: Use visitor history to determine time since last visit
        visitor_info = self.tavern_state["visitor_history"].get(person, {})
        last_exit_time = visitor_info.get("last_exit", 0)
        last_entry_time = visitor_info.get("last_entry", 0)

        # Calculate time since they were last here
        if last_exit_time > 0:
            # They left at some point - use exit time
            time_since_last_visit = current_time - last_exit_time
            was_here_before = True
        elif last_entry_time > 0:
            # They entered but never left (still here?) - this shouldn't happen but handle it
            time_since_last_visit = current_time - last_entry_time
            was_here_before = True
        else:
            # First time visitor
            time_since_last_visit = float("inf")
            was_here_before = False

        # Log visitor history information
        self.logger.debug(
            f"TIME DEBUG: Bar greeting for {person} - current time: {current_time}"
        )
        self.logger.debug(
            f"TIME DEBUG: Visitor history - last_exit: {last_exit_time}, last_entry: {last_entry_time}"
        )
        self.logger.debug(
            f"TIME DEBUG: Time since last visit: {time_since_last_visit/3600:.2f} hours" if was_here_before else "TIME DEBUG: First time visitor"
        )

        # SECONDARY: Check message buffer for conversation context
        recent_interaction = False
        recent_interaction_text = ""
        time_since_last_interaction = float("inf")
        from services.message_service import get_message_buffer

        message_buffer = get_message_buffer()

        # Look through recent messages
        recent_messages = sorted(message_buffer, key=lambda x: x["timestamp"])[-10:]

        # Find the most recent interaction with this person
        for msg in recent_messages:
            if msg["role"] == "user" and person in msg.get("speaker", ""):
                # Find Tim's response to this
                for response in recent_messages:
                    if (
                        response["role"] == "assistant"
                        and response["character"] == self.name
                        and response["timestamp"] > msg["timestamp"]
                    ):
                        time_since_last_interaction = (
                            current_time - response["timestamp"]
                        )
                        recent_interaction = True
                        recent_interaction_text = response["content"]
                        break
                if recent_interaction:
                    break

        # Log message buffer interaction for debugging
        if recent_interaction:
            self.logger.debug(
                f"TIME DEBUG: Message interaction with {person} - time since last: {time_since_last_interaction/3600:.2f} hours"
            )
            self.logger.debug(
                f"TIME DEBUG: Last interaction text: '{recent_interaction_text[:50]}...'"
            )
        else:
            self.logger.debug(f"TIME DEBUG: No message interaction found with {person}")

        # Flush old messages if there's been a significant time gap
        if was_here_before and time_since_last_visit > 60 * 60 * 2:  # More than 2 hours
            self.logger.info(
                f"Significant time gap detected ({time_since_last_visit/3600:.2f} hours) - flushing old messages"
            )
            from services.message_service import flush_old_messages

            try:
                flush_old_messages(self.name, max_age_hours=2)
                # After flushing, there's no recent interaction
                recent_interaction = False
                recent_interaction_text = ""
            except Exception as e:
                self.logger.warning(f"Error flushing old messages: {e}")

        # Get relationship status
        relationship_status = self._get_relationship_status(person)

        # Get visitor info for frequency
        visit_count = visitor_info.get("visit_count", 1)

        # Handle first-time visitor text separately
        if visit_count == 1:
            visitor_text = "their first visit"
        else:
            visitor_text = f"someone you've seen {visit_count} times before"

        # Determine time perception context based on VISITOR HISTORY (primary source)
        time_perception = ""
        try:
            if not was_here_before:
                # First time visitor
                time_perception = (
                    "- This is the FIRST TIME you're meeting this person\n"
                    "- Give them a warm, welcoming first-time greeting\n"
                    "- You don't know them yet, so keep it friendly but professional"
                )
            elif time_since_last_visit > 60 * 60 * 24:  # More than 1 day
                # Check if it's a new day
                import datetime

                last_visit_date = datetime.datetime.fromtimestamp(last_exit_time).date()
                current_date = datetime.datetime.fromtimestamp(current_time).date()
                days_since = (current_date - last_visit_date).days

                if days_since >= 1:
                    time_perception = (
                        f"- CRITICAL TIME AWARENESS: It has been {days_since} DAY(S) since you last saw {person}\n"
                        f"- Last visit: {last_visit_date.strftime('%A, %B %d')}\n"
                        f"- Today: {current_date.strftime('%A, %B %d')}\n"
                        "- This is a COMPLETELY NEW DAY and a FRESH VISIT\n"
                        "- IMPORTANT: Do NOT reference or assume they are continuing any specific activity from days ago\n"
                        "- DO NOT say things like 'back for another game?' or 'still working on that?'\n"
                        "- DO NOT act like a previous conversation is continuing\n"
                        "- DO greet them warmly as someone you recognize who's come back on a new day\n"
                        f"- Consider using time-appropriate greetings like 'Good {time_of_day}'\n"
                        "- Treat this as: You know them, but this is a brand new visit"
                    )
            elif time_since_last_visit > 60 * 60 * 6:  # More than 6 hours but same day
                time_perception = (
                    f"- It's been MANY HOURS ({int(time_since_last_visit/3600)} hours) since you last saw them\n"
                    "- CRITICAL: This is NOT a continuation of your previous conversation\n"
                    "- Too much time has passed to assume they're still doing the same activity\n"
                    "- Treat this as a completely fresh visit from someone you know\n"
                    "- DO NOT reference specific activities they were doing earlier\n"
                    "- DO NOT ask if they're 'back' for something specific\n"
                    "- DO NOT act as if a conversation is continuing"
                )
            elif time_since_last_visit > 60 * 30:  # 30 minutes to 6 hours
                time_perception = (
                    f"- It's been a while ({int(time_since_last_visit/60)} minutes) since you last saw them\n"
                    "- This should be treated as a new conversation, not a direct continuation\n"
                    "- They may have been doing other things in the meantime\n"
                    "- Greet them as someone returning after a break"
                )
            elif time_since_last_visit < 60 * 5:  # Less than 5 minutes
                time_perception = (
                    "- They just left VERY RECENTLY (less than 5 minutes ago) and are already back\n"
                    "- This is likely a quick return - maybe they forgot something or just stepped out briefly\n"
                    "- A simple acknowledgment or brief comment is appropriate\n"
                    "- You might even just nod or give a knowing look"
                )
            else:  # 5-30 minutes
                time_perception = (
                    f"- They were here not too long ago ({int(time_since_last_visit/60)} minutes)\n"
                    "- This could be a continuation, but don't assume they're still doing the same specific activity\n"
                    "- Acknowledge their return in a friendly but casual way"
                )
        except (ValueError, OverflowError) as e:
            self.logger.warning(f"Datetime conversion error in bar greeting: {e}")
            # Fallback to simpler time perception without datetime
            time_perception = (
                "- It's been some time since you last saw them\n"
                "- Treat this as a fresh interaction - do not reference specific prior activities"
            )

        # Create a special bar greeting context for Claude
        bar_greeting_context = (
            "BAR GREETING CONTEXT:\n"
            f"- The person '{person}' has just sat down directly at your Bar\n"
            f"- It's {context.get('time_info', 'afternoon')} and {context.get('weather', 'clear')}\n"
            f"- This is {visitor_text}\n"
            f"- Your relationship with them is {relationship_status}\n"
            "- They are now sitting right in front of you, looking for service or conversation\n"
            "\n"
            "TIME AWARENESS (based on when they were last here):\n"
            f"{time_perception}"
        )

        # Only add conversation continuity if it's actually relevant (recent interaction AND short time gap)
        if recent_interaction and time_since_last_visit < 60 * 30:  # Only if within 30 minutes
            recent_context = (
                "\nRECENT CONVERSATION CONTEXT:\n"
                f'- Your last response to them was: "{recent_interaction_text}"\n'
                "- Since this was recent, you can reference your previous conversation if appropriate\n"
                "- But still keep in mind the time that has passed"
            )
            bar_greeting_context += recent_context
        elif recent_interaction:
            # There was an interaction, but it was too long ago to be directly relevant
            bar_greeting_context += (
                "\nPREVIOUS CONVERSATION NOTE:\n"
                "- You spoke with them earlier, but enough time has passed that this is a fresh interaction\n"
                "- Do not directly continue previous conversation topics unless they bring them up"
            )

        bar_greeting_context += (
            "\n"
            "Based on this context, respond appropriately to them taking a seat at your bar. "
            "Keep your response brief (under 35 words) and authentic to your character as an Irish tavern keeper."
        )

        # Add user message to buffer
        from services.message_service import add_message

        add_message("user", f"{person} takes a seat at the Bar", self.name)

        # Format system prompt with memory and bar greeting context
        base_prompt = self._prepare_prompt(person, context)
        full_prompt = f"{base_prompt}\n\n{bar_greeting_context}"

        # Get response from Claude API
        from services.message_service import get_char_messages
        from services.claude_service import get_claude_response

        char_messages = get_char_messages(self.name)
        greeting = get_claude_response(full_prompt, char_messages, max_tokens=150)

        if greeting:
            # Add to message buffer
            add_message("assistant", greeting, self.name)
            self._update_memory_with_interaction(
                            person, f"{person} takes a seat at the Bar", greeting
                        )
            return greeting
        else:
            # Fallback if API fails - choose based on time context
            try:
                if not was_here_before:
                    fallback = f'Tim smiles warmly. "Welcome to the tavern, {person}. First time here?"'
                elif time_since_last_visit > 60 * 60 * 24:  # More than a day
                    import datetime
                    days_since = int(time_since_last_visit / (60 * 60 * 24))
                    fallback = f'Tim looks up with a smile. "Well, good {time_of_day}, {person}! Been a few days, hasn\'t it?"'
                elif time_since_last_visit > 60 * 60 * 6:  # More than 6 hours
                    fallback = f'Tim nods as {person} returns to the bar. "Back again, {person}? What can I get you?"'
                elif time_since_last_visit > 60 * 30:  # More than 30 minutes
                    fallback = f'Tim looks up. "Back for another, {person}?"'
                elif time_since_last_visit < 60 * 5:  # Less than 5 minutes
                    fallback = f"Tim raises an eyebrow as {person} returns quickly."
                else:
                    fallback = f"Tim acknowledges {person} with a nod."
            except Exception as e:
                # Ultimate fallback if calculations fail
                self.logger.warning(f"Error in fallback response selection: {e}")
                fallback = f'Tim smiles. "Welcome to the bar, {person}. What can I get for you?"'

            add_message("assistant", fallback, self.name)
            return fallback

    def _generate_bar_conversation_response(
        self, speaker, content, event_type, context
    ):
        """Generate a response to a conversation happening at the Bar"""
        # Get relationship status
        relationship_status = self._get_relationship_status(speaker)

        # Create a context for Claude about bar conversations
        bar_conversation_context = f"""
        BAR CONVERSATION CONTEXT:
        - You are Tim O'Lucian, the Irish tavern keeper
        - Someone at your Bar ({speaker}) has just {event_type.replace('bar_', '')}ed: "{content}"
        - They were not directly addressing you, but you're close by behind the bar
        - It's {context.get('time_info', 'afternoon')} and {context.get('weather', 'clear')}
        - Your relationship with them is {relationship_status}

        Based on this context, you may occasionally chime in on conversations happening at your bar, especially if:
        - The topic relates to the tavern, drinks, or local matters
        - You have useful information to add
        - Someone asks a question that others aren't answering
        - The conversation has an awkward pause
        - Someone mentions something you'd naturally have an opinion on

        Your response should be casual and natural, as if you're part of the social environment. Keep it brief (under 35 words) and authentic to your character. You might be wiping glasses, preparing drinks, or doing other bartender activities while speaking.
        """

        # Format system prompt with memory and bar conversation context
        base_prompt = self._prepare_prompt(speaker, context)
        full_prompt = f"{base_prompt}\n\n{bar_conversation_context}"

        # Get response from Claude API
        from services.message_service import get_char_messages, add_message
        from services.claude_service import get_claude_response

        char_messages = get_char_messages(self.name)
        reply = get_claude_response(full_prompt, char_messages, max_tokens=150)

        if reply:
            # Add to message buffer
            add_message("assistant", reply, self.name)
            return reply
        else:
            # No response in this case is fine too - don't always need to chime in
            return ""

    def _handle_direct_speech(self, speaker, content, context):
        """Handle direct speech to Tim"""
        # Use standard process_message with the direct speech content
        return super().process_message(speaker, content, context)

    def sync_occupants_with_mush(self, occupants_text):
        """Ensure Tim's memory of who's in the tavern matches MUSH reality"""
        # Parse occupants text to extract names
        # Format might be like: "No one is sitting at the Bar... Enki, Mr.Ferrell, and SampleS are just standing around"
        occupants = []

        # Try to extract names from the "X, Y, and Z are just standing around" format
        if " are just standing around" in occupants_text:
            standing_part = occupants_text.split(" are just standing around")[0]
            if "," in standing_part or " and " in standing_part:
                # Extract the last part of the text which should contain the names
                last_section = standing_part.split("  ")[-1]
                # Split by commas and 'and'
                parts = last_section.replace(" and ", ", ").split(", ")
                occupants = [name.strip() for name in parts if name.strip()]

        if occupants:
            self.logger.info(f"Syncing occupants from MUSH: {occupants}")

            # Update current_occupants
            self.tavern_state["current_occupants"] = occupants

            # For each occupant, make sure they have visitor history
            for person in occupants:
                if person not in self.tavern_state["visitor_history"]:
                    # Initialize visitor history for someone who's already here
                    self.tavern_state["visitor_history"][person] = {
                        "first_seen": time.time(),
                        "last_entry": time.time(),
                        "last_exit": 0,  # Never exited
                        "visit_count": 1,
                        "greeting_type": "none",  # No greeting needed
                    }

            # Save updates
            self._save_character_memories()

    def cleanup_tavern_state(self):
        """Periodically clean up unused event lists"""
        current_time = time.time()

        # Still keep track of entries, but prune old ones
        self.tavern_state["entry_events"] = [
            event
            for event in self.tavern_state["entry_events"]
            if current_time - event["timestamp"]
            < 3600  # Only keep events from the last hour
        ]

        # Update visitor history - still useful for greeting styles
        for visitor in list(self.tavern_state["visitor_history"].keys()):
            # Clean up visitor history for people who haven't been seen in a week
            if (
                current_time
                - self.tavern_state["visitor_history"][visitor].get("last_entry", 0)
                > 7 * 24 * 3600
            ):
                del self.tavern_state["visitor_history"][visitor]

        # Save the updated memories
        self._save_character_memories()
        self.logger.info("Completed tavern state cleanup")

    def _prepare_prompt(self, speaker, context):
        """Prepare the system prompt for Tim"""
        # Load the prompt template
        prompt_file = os.path.join(self.character_dir, "tim_prompt.txt")

        try:
            with open(prompt_file, "r") as f:
                prompt_template = f.read()

            # Use the centralized method for placeholder filling
            prompt = self._fill_prompt_template(prompt_template, speaker, context)

            # Add memory information
            memory_prompt = self._format_memory_for_prompt(speaker)
            full_prompt = f"{prompt}\n\n{memory_prompt}"

            return full_prompt

        except Exception as e:
            self.logger.error(f"Error loading prompt for Tim: {e}")

            # Create a simple fallback prompt
            fallback_prompt = f"""You are Tim O'Lucian, an Irish tavern keeper.
    You're speaking to {speaker}. Keep responses under 35 words."""

            # Try to get memory information
            try:
                memory_prompt = self._format_memory_for_prompt(speaker)
                full_prompt = f"{fallback_prompt}\n\n{memory_prompt}"
                return full_prompt
            except Exception as memory_error:
                self.logger.error(f"Error getting memory for Tim: {memory_error}")
                # If memory also fails, just return the basic fallback
                return fallback_prompt

    def _format_memory_for_prompt(self, current_speaker):
        """Format memory information for inclusion in prompt with tavern-specific additions"""
        # Get the base memory prompt from the parent class
        memory_prompt = super()._format_memory_for_prompt(current_speaker)

        # Add tavern-specific information
        memory_prompt += "\n\nTAVERN INFORMATION:\n"

        # Add information about current occupants
        if self.tavern_state["current_occupants"]:
            memory_prompt += "\nCURRENT TAVERN OCCUPANTS:\n"
            memory_prompt += ", ".join(self.tavern_state["current_occupants"]) + "\n"
        else:
            memory_prompt += "\nThe tavern is currently empty except for you and the person you're speaking with.\n"

        # Add recent entries that haven't been acknowledged
        recent_entries = [
            e for e in self.tavern_state["entry_events"] if not e["acknowledged"]
        ]
        if recent_entries:
            memory_prompt += "\nRECENT TAVERN ENTRIES (not yet acknowledged):\n"
            for entry in recent_entries:
                person = entry["person"]
                greeting_type = entry.get(
                    "greeting_type", "full"
                )  # Default to full if not specified
                rapid_reentry = entry.get("rapid_reentry", False)
                repeat_visitor = entry.get("repeat_visitor", False)
                time_ago = format_time_since(entry["timestamp"])

                entry_info = f"- {person} entered {time_ago}"

                if rapid_reentry:
                    entry_info += " (returned quickly after leaving)"
                if repeat_visitor:
                    entry_info += " (regular visitor)"

                entry_info += f" - appropriate greeting: {greeting_type}"

                if greeting_type == "full":
                    entry_info += " (normal welcome)"
                elif greeting_type == "brief":
                    entry_info += " (brief welcome)"
                elif greeting_type == "nod":
                    entry_info += " (just a nod or glance)"

                memory_prompt += entry_info + "\n"

        # Add recent exits that haven't been acknowledged
        recent_exits = [
            e for e in self.tavern_state["exit_events"] if not e["acknowledged"]
        ]
        if recent_exits:
            memory_prompt += "\nRECENT TAVERN EXITS (not yet acknowledged):\n"
            for exit_event in recent_exits:
                person = exit_event["person"]
                rapid_exit = exit_event.get("rapid_exit", False)
                time_ago = format_time_since(exit_event["timestamp"])

                exit_info = f"- {person} left {time_ago}"

                if rapid_exit:
                    exit_info += " (was only here briefly)"
                    memory_prompt += (
                        exit_info + " - consider a 'leaving so soon?' remark\n"
                    )
                else:
                    memory_prompt += (
                        exit_info + " - consider a brief farewell if appropriate\n"
                    )

        return memory_prompt
