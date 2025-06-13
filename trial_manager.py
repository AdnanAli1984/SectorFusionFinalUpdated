# trial_manager.py

import json
import os
from typing import List, Set, Optional

class TrialManager:
    def __init__(self, trial_file_path: str = "trial_data.json"):
        self.trial_file_path = trial_file_path
        self.site_keys: Set[str] = set()
        self.load_trial_data()

    def load_trial_data(self) -> None:
        """Load saved trial data from JSON file"""
        try:
            if os.path.exists(self.trial_file_path):
                with open(self.trial_file_path, 'r') as f:
                    data = json.load(f)
                    self.site_keys = set(data.get('site_keys', []))
        except Exception as e:
            print(f"Error loading trial data: {str(e)}")
            self.site_keys = set()

    def save_trial_data(self) -> bool:
        """Save trial data to JSON file"""
        try:
            with open(self.trial_file_path, 'w') as f:
                json.dump({
                    'site_keys': list(self.site_keys)
                }, f)
            return True
        except Exception as e:
            print(f"Error saving trial data: {str(e)}")
            return False

    def register_sites(self, ep_keys: List[str]) -> bool:
        """Register EP keys for trial version"""
        try:
            if not self.site_keys:  # First time registration
                self.site_keys = set(ep_keys)
                return self.save_trial_data()
            return True
        except Exception as e:
            print(f"Error registering sites: {str(e)}")
            return False

    def validate_sites(self, ep_keys: List[str]) -> tuple[bool, str]:
        """Validate if the EP keys match registered trial sites"""
        try:
            if not self.site_keys:  # No sites registered yet
                return True, "First time trial usage"

            current_keys = set(ep_keys)
            if not current_keys.issubset(self.site_keys):
                return False, "The EP sites in your data don't match the registered trial sites. Please use the original sites or obtain a license to proceed."
            
            return True, "Sites validated successfully"
        except Exception as e:
            print(f"Error validating sites: {str(e)}")
            return False, f"Error validating sites: {str(e)}"