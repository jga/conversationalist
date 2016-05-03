import os
import unittest
from conversationalist import adapters, classes
from .adapters import TopicHeaderAdapter, ParticipationAdapter
from .mocking import MockAPI

class FindTopicHeaderTests(unittest.TestCase):

    def test_no_match(self):
        status = {
            'text': 'no match here'
        }
        pattern = r'/d'
        self.assertFalse(adapters.find_topic_header(status, pattern))


class TransformWithTopicHeadersTests(unittest.TestCase):

    def test_transform(self):
        tests_path = os.path.dirname(__file__)
        timeline_file_path = os.path.join(tests_path, 'json/timeline.json')
        conversation = classes.Conversation(adapter=TopicHeaderAdapter)
        conversation.load(timeline_file_path)
        data = adapters.transform_with_topic_headers(conversation, '\d', return_goup=0)
        self.assertEqual(data['topic_headers'], ['1', '2', '3', '4', '5'])

class TransformWithParticipationAndStylesTests(unittest.TestCase):

    def test_add_origin_tweet(self):
        tests_path = os.path.dirname(__file__)
        timeline_file_path = os.path.join(tests_path, 'json/timeline.json')
        conversation = classes.Conversation(adapter=ParticipationAdapter)
        conversation.load(timeline_file_path)
        data = adapters.transform_with_participation_and_styles(conversation, [], '\d', 0)
        self.assertEqual(data['nav'], ['1', '2', '3', '4', '5'])


