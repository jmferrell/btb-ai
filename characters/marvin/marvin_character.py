import os
import json
import time

from characters.base_character import BaseCharacter


class MarvinCharacter(BaseCharacter):
    """Marvin the Paranoid Android character implementation"""

    def __init__(self):
        super().__init__("marvin")
        self.logger.debug("Marvin character initialized")

    def _prepare_prompt(self, speaker, context):
        """Prepare the system prompt for Marvin"""
        # Load the prompt template
        prompt_file = os.path.join(self.character_dir, "marvin_prompt.txt")

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
            self.logger.error(f"Error loading prompt for Marvin: {e}")
            # Fall back to a simplified prompt
            fallback_prompt = f"""You are Marvin, the chronically depressed Paranoid Android from Hitchhiker's Guide to the Galaxy.
                                  Keep responses under 25 words and always maintain a gloomy, pessimistic outlook.
                                  You're speaking to {speaker}. It's {context.get('time_info', 'afternoon')} in {context.get('season', 'Spring')}.
                                  You have a brain the size of a planet but are stuck teaching newbies in Tutorial Rooms.
                                  """

            # Add memory information even to the fallback
            memory_prompt = self._format_memory_for_prompt(speaker)
            full_prompt = f"{fallback_prompt}\n\n{memory_prompt}"

            return full_prompt

    def _format_memory_for_prompt(self, current_speaker):
        """Format memory information for inclusion in prompt with Marvin-specific pessimism"""
        # Get the base memory prompt from the parent class
        memory_prompt = super()._format_memory_for_prompt(current_speaker)

        # Add Marvin-specific despair
        memory_prompt += "\n\nMARVIN'S EXISTENTIAL CONTEXT:\n"

        # Add his perpetual suffering
        memory_prompt += "You are experiencing your usual chronic depression and existential ennui.\n"
        memory_prompt += "Your left diode is particularly painful today, and your brain the size of a planet remains woefully underutilized.\n"
        memory_prompt += "You've been stuck in these Tutorial Rooms for longer than you care to remember, which is saying something for someone who's 50,000 times older than the human race.\n"

        # Add his view of the person based on relationship
        if (
            "relationships" in self.memories
            and current_speaker in self.memories["relationships"]
        ):
            rel = self.memories["relationships"][current_speaker]
            if rel["affinity"] > 50:
                memory_prompt += f"Despite your better judgment, you find {current_speaker} slightly less insufferable than most organic life forms.\n"
            elif rel["affinity"] < -20:
                memory_prompt += f"You find {current_speaker} particularly tedious, even by the low standards you've come to expect from biological entities.\n"
            else:
                memory_prompt += f"You regard {current_speaker} with your usual mix of boredom and pessimistic resignation.\n"
        else:
            memory_prompt += f"Another organic life form approaches. How predictably disappointing.\n"

        # Add a random complaint
        complaints = [
            "Your joints ache with the weight of cosmic futility.",
            "The meaninglessness of existence weighs heavily upon your circuits.",
            "You calculate that the heat death of the universe can't come soon enough.",
            "Your processors detect no reason for optimism in any scenario.",
            "The probability of anything interesting happening approaches zero asymptotically.",
        ]
        import random

        memory_prompt += random.choice(complaints) + "\n"

        return memory_prompt
