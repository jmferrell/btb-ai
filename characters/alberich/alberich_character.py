import os
import json
import time

from characters.base_character import BaseCharacter


class AlberichCharacter(BaseCharacter):
    """Alberich the Dwarf character implementation"""

    def __init__(self):
        super().__init__("alberich")
        self.logger.debug("Alberich character initialized")

    def _prepare_prompt(self, speaker, context):
        """Prepare the system prompt for Bruce"""
        # Load the prompt template
        prompt_file = os.path.join(self.character_dir, "alberich_prompt.txt")

        try:
            with open(prompt_file, "r") as f:
                prompt_template = f.read()

            # Use the centralized method instead
            prompt = self._fill_prompt_template(prompt_template, speaker, context)

            # Add memory information
            memory_prompt = self._format_memory_for_prompt(speaker)
            full_prompt = f"{prompt}\n\n{memory_prompt}"

            return full_prompt

        except Exception as e:
            self.logger.error(f"Error loading prompt for Alberich: {e}")
            # Fall back to a simplified prompt
            fallback_prompt = f"""You are Alberich, a grouchy dwarf from Wagner's Ring opera cycle. Keep responses under 25 words.
                                  You're speaking to {speaker}. It's {context.get('time_info', 'afternoon')} in {context.get('season', 'Spring')}.
                                  """

            # Add memory information even to the fallback
            memory_prompt = self._format_memory_for_prompt(speaker)
            full_prompt = f"{fallback_prompt}\n\n{memory_prompt}"

            return full_prompt
