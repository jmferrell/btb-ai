import os
import importlib
import inspect
from characters.base_character import BaseCharacter

class CharacterFactory:
    """Factory for dynamically loading character classes"""
    
    @staticmethod
    def create_character(char_name):
        """
        Dynamically create a character instance by name
        
        This allows new characters to be added without modifying the main code
        """
        try:
            # Attempt to import the character module
            module_name = f"characters.{char_name}.{char_name}_character"
            class_name = f"{char_name.capitalize()}Character"
            
            # Dynamically import the module
            module = importlib.import_module(module_name)
            
            # Find the character class within the module
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BaseCharacter) and name == class_name:
                    # Create and return an instance
                    return obj()
            
            raise ValueError(f"Character class {class_name} not found in module {module_name}")
            
        except (ImportError, AttributeError, ValueError) as e:
            print(f"Error creating character {char_name}: {e}")
            return None