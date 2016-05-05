import unittest
from unittest.mock import create_autospec
import os
from io import StringIO
import sys
from conversationalist import utils
from .mocking import MockAPI


def write_for_tests(conversation, story_out):
    return 'a_page_location'


class MakeStoryTests(unittest.TestCase):

    def setUp(self):
        tests_path = os.path.dirname(__file__)
        test_file_directory = os.path.join(tests_path, 'tmp_test_output/')
        self.timeline_out = os.path.join(test_file_directory, 'timeline_from_test.json')
        self.story_out = os.path.join(test_file_directory, 'story.html')

    def test_make_story(self):
        mock_write = create_autospec(write_for_tests)
        api = MockAPI()
        settings = {
            'api': api,
            'timeline_out': self.timeline_out,
            'story_out': self.story_out,
            'username': 'test_user',
            'write': mock_write
        }
        try:
            utils.make_story(settings)
            self.assertTrue(mock_write.called)
        finally:
            if os.path.isfile(self.timeline_out):
                os.remove(self.timeline_out)
            if os.path.isfile(self.story_out):
                os.remove(self.story_out)


class PrintRateLimitInfoTests(unittest.TestCase):

   def test_print(self):
       out = StringIO()
       sys.stdout = out
       api = MockAPI(statuses=[])
       utils.print_rate_limit_info(api)
       output = out.getvalue().strip()
       self.assertEqual(output, 'KEY:  test_key  VALUE:  test_value')
