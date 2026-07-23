import os
import unittest
from unittest.mock import patch
import tempfile

from src.core import name_cache

class TestNameCache(unittest.TestCase):
    def setUp(self):
        # Create a temp file for cache path redirect
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_file.close()
        self.patcher = patch("src.core.name_cache.CACHE_PATH", self.temp_file.name)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_load_empty_cache(self):
        # Cache file is empty/nonexistent
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)
        
        data = name_cache.load_cache()
        self.assertEqual(data, {})

    def test_save_and_load_cache(self):
        test_data = {"110": "Sandor Clegane", "111": "Arya Stark"}
        name_cache.save_cache(test_data)
        
        data = name_cache.load_cache()
        self.assertEqual(data, test_data)

    def test_update_entry(self):
        test_data = {"110": "Sandor Clegane"}
        name_cache.save_cache(test_data)
        
        # Update entry
        name_cache.update_entry("111", "Arya Stark")
        
        # Load and verify both exist
        data = name_cache.load_cache()
        self.assertEqual(data.get("110"), "Sandor Clegane")
        self.assertEqual(data.get("111"), "Arya Stark")

        # Update existing
        name_cache.update_entry("110", "Sandor Clegane Updated")
        data = name_cache.load_cache()
        self.assertEqual(data.get("110"), "Sandor Clegane Updated")
