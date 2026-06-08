import unittest
import os
import json
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from templates import TemplatesManager

class TestTemplatesManager(unittest.TestCase):
    def setUp(self):
        self.custom_file = "test_custom.json"
        self.default_file = "test_default.json"
        with open(self.default_file, 'w') as f:
            json.dump({"vscode": [{"key_num": 1, "description": "Format Document"}]}, f)
        with open(self.custom_file, 'w') as f:
            json.dump({"vscode": [{"key_num": 2, "description": "Toggle Terminal"}]}, f)
            
        self.mgr = TemplatesManager(self.custom_file, self.default_file)

    def tearDown(self):
        if os.path.exists(self.custom_file): os.remove(self.custom_file)
        if os.path.exists(self.default_file): os.remove(self.default_file)

    def test_get_context_shortcuts(self):
        shortcuts = self.mgr.get_context_shortcuts("vscode")
        self.assertEqual(len(shortcuts), 2)
        descriptions = [s["description"] for s in shortcuts]
        self.assertIn("Toggle Terminal", descriptions) # custom should be included
        self.assertIn("Format Document", descriptions) # default should be included
        
    def test_add_shortcuts(self):
        new_shortcut = [{"key_num": 3, "description": "New Action"}]
        self.mgr.add_shortcuts("vscode", new_shortcut)
        shortcuts = self.mgr.get_context_shortcuts("vscode")
        self.assertEqual(len(shortcuts), 3)

if __name__ == '__main__':
    unittest.main()
