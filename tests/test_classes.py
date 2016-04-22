import json
import re
import unittest
from unittest.mock import Mock
import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from conversationalist import classes


def generate_mock_user():
    user = Mock(spec=classes.User)
    user.id = 1
    user.screen_name = 'test_author'
    user.profile_image_url = "http:\/\/a1.twimg.com\/profile_images\/101\/avatar_normal.png"
    return user


def generate_mock_status(id=None, text=None, created_at=None):
    status = Mock(spec=classes.Status)
    status.id = id
    status.text = text if text else "The text for mock status {0}".format(status.id)
    status.created_at = created_at if created_at else datetime.utcnow()
    user = generate_mock_user()
    status.author = user
    status.in_reply_to_status_id = None
    return status


def generate_datetime_fixtures(naive_dt=True):
    if naive_dt:
        dt1 = datetime.utcnow()
    else:
        dt1 = datetime.now(tz=timezone.utc)
    dt2 = dt1 + timedelta(hours=-1)
    dt3 = dt1 + timedelta(hours=-3)
    dt4 = dt1 + timedelta(hours=-5)
    dt5 = dt1 + timedelta(hours=-6)
    dt6 = dt1 + timedelta(hours=-7)
    dt7 = dt1 + timedelta(hours=-10)
    return [dt1, dt2, dt3, dt7, dt4, dt6, dt5], dt7


def generate_mock_timeline_statuses(naive_dt=True):
    """
    A list of statuses. May be set to have a utc timezone with a ``False``
    value for the ``naive_dt`` argument.
    """
    mock_statuses = dict()
    datetime_fixtures, earliest = generate_datetime_fixtures()
    for dt in datetime_fixtures:
        status = Mock(spec=classes.Status)
        status.id = len(mock_statuses) + 1
        status.text = "The text for mock status {0}".format(status.id)
        status.created_at = dt
        status.author = 'test_author'
        status.in_reply_to_status_id = None
        mock_statuses[str(status.id)] = status
    return mock_statuses, earliest


def generate_mock_statuses(naive_dt=True):
    """
    A dict of statuses keyed to their id. Useful for ``Timeline`` class testing.

    May be set to have a utc timezone with a ``False`` value for the ``naive_dt`` argument.
    """
    mock_statuses = list()
    datetime_fixtures, earliest = generate_datetime_fixtures()
    for dt in datetime_fixtures:
        identifier = len(mock_statuses) + 1
        mock_status_text = 'Content for tweet status {0}'.format(identifier)
        mock_status = generate_mock_status(identifier, mock_status_text)
        mock_status.created_at = dt
        mock_statuses.append(mock_status)
    return mock_statuses, earliest


class MockAPI:
    def __init__(self, statuses=None):
        if statuses:
            self.statuses = statuses
        else:
            self.statuses = generate_mock_statuses()[0]

    def user_timeline(self, user, max_id=None):
        return self.statuses


class TimelineTests(unittest.TestCase):

    def setUp(self):
        mock_statuses, earliest = generate_mock_timeline_statuses()
        self.mock_statuses = mock_statuses
        self.earliest_datetime = earliest
        tests_path = os.path.dirname(__file__)
        self.test_file_directory = os.path.join(tests_path, 'tmp_test_output/')

    def test_get_earliest_status(self):
        timeline = classes.Timeline()
        timeline.statuses = self.mock_statuses
        earliest_status = timeline.get_earliest_status()
        self.assertTrue(earliest_status.created_at == self.earliest_datetime)
        self.assertTrue(earliest_status.created_at.day == self.earliest_datetime.day)
        self.assertTrue(earliest_status.created_at.hour == self.earliest_datetime.hour)
        self.assertTrue(earliest_status.created_at.minute == self.earliest_datetime.minute)
        self.assertTrue(earliest_status.created_at.second == self.earliest_datetime.second)

    def test_generate_timeline(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, user='testuser')
        self.assertEqual(len(list(timeline.statuses.values())), 7)

    def test_generate_timeline_with_tight_central_cutoff(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, user='testuser', timeframe=-12, tz_name='America/Chicago')
        self.assertEqual(len(list(timeline.statuses.values())), 7)

    def test_generate_timeline_with_tight_utc_cutoff(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, user='testuser', timeframe=1)
        self.assertTrue(len(list(timeline.statuses.values())), 1)

    def test_load_statuses(self):
        status1 = generate_mock_status(1)
        original_created_at = status1.created_at
        bad_status1 = generate_mock_status(1)
        statuses = [status1, bad_status1]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser')
        timeline.load(statuses)
        self.assertTrue(len(list(timeline.statuses.values())), 1)
        self.assertEqual(timeline.statuses['1'].created_at.microsecond,
                         original_created_at.microsecond)

    def test_has_next_tweets_no_statuses(self):
        statuses = []
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser')
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_exceeded_cutoff(self):
        old_status = generate_mock_status(1)
        old_status.created_at = old_status.created_at + timedelta(hours=-2)
        statuses = [old_status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', timeframe=1)
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_exhausted(self):
        status = generate_mock_status(1)
        statuses = [status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser')
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_under_cutoff(self):
        status = generate_mock_status(1)
        status2 = generate_mock_status(2)
        statuses = [status, status2]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', timeframe=5)
        status3 = generate_mock_status(3)
        status3.created_at = status.created_at + timedelta(hours=-1)
        timeline.statuses[str(status3.id)] = status3
        self.assertTrue(timeline._has_next_tweets())
        self.assertEqual(timeline.earliest_status.id, 3)

    def test_timeline_to_json(self):
        statuses = list()
        for index in range(1, 6):
            text = "The text for mock status {0}".format(index)
            created_at = datetime.now()
            status = generate_mock_status(index, text=text, created_at=created_at)
            statuses.append(status)
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', tz_name='America/Chicago')
        test_output_file_path = os.path.join(self.test_file_directory, 'test_timeline_to_json.json')
        try:
            timeline.to_json(test_output_file_path)
            with open(test_output_file_path) as data_file:
                data = json.load(data_file)
                self.assertTrue('start' in data)
                start_iso_date_string = data['start']
                start = parse(start_iso_date_string)
                self.assertTrue(isinstance(start, datetime))
                self.assertTrue(start.tzinfo)
                self.assertEqual(start.utcoffset(), timedelta(-1, 68400))
                self.assertTrue('cutoff' in data)
                self.assertTrue('cutoff' in data)
                cutoff_iso_date_string = data['cutoff']
                cutoff = parse(cutoff_iso_date_string)
                self.assertTrue(isinstance(cutoff, datetime))
                self.assertTrue(cutoff.tzinfo)
                self.assertEqual(cutoff.utcoffset(), timedelta(-1, 68400))
                self.assertTrue('total' in data)
                self.assertEqual(data['total'], 5)
                self.assertTrue('statuses' in data)
                self.assertTrue(isinstance(data['statuses'], dict))
                self.assertTrue('user' in data)
                self.assertEqual(data['user'], 'testuser')
                self.assertTrue('tz' in data)
                self.assertEqual(data['tz'], 'America/Chicago')
        finally:
            if os.path.isfile(test_output_file_path):
                os.remove(test_output_file_path)


class PrepareHourlySummaryTests(unittest.TestCase):
    def test_summary(self):
        start = datetime(2001, 2, 3, 5, 6, 7, 8)
        cutoff = datetime(2001, 2, 3, 0, 0, 0, 0)
        summary = classes.initialize_hourly_summary(start, cutoff)
        self.assertEqual(len(list(summary.values())), 6, msg=summary)
        self.assertTrue('February-03-2001-12-AM' in summary)
        self.assertTrue('February-03-2001-01-AM' in summary)
        self.assertTrue('February-03-2001-02-AM' in summary)
        self.assertTrue('February-03-2001-03-AM' in summary)
        self.assertTrue('February-03-2001-04-AM' in summary)
        self.assertTrue('February-03-2001-05-AM' in summary)
        self.assertFalse('February-03-2001-06-AM' in summary)


class ConversationTests(unittest.TestCase):

    def setUp(self):
        statuses, self.earliest_datetime = generate_mock_statuses()
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', tz_name='America/Chicago')
        encoder = classes.TimelineEncoder()
        timeline_json = json.loads(encoder.encode(timeline))
        self.test_timeline = timeline_json

    def test_title_after_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline)
        self.assertEqual(conversation.data['title'], 'Tick Tock')

    def test_custom_title_after_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline, title='Other Title')
        self.assertEqual(conversation.data['title'], 'Other Title')

    def test_title_periods_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline)
        self.assertTrue(isinstance(conversation.data['periods'], list))
        periods = conversation.data['periods']
        self.assertTrue(len(periods), 6)

    def test_title_periods_subtitles(self):
        conversation = classes.Conversation(timeline=self.test_timeline)
        periods = conversation.data['periods']
        for period in periods:
            subtitle = period['subtitle']
            self.assertTrue(isinstance(subtitle, str))
            regex_pattern = re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)')
            result = regex_pattern.match(subtitle)
            self.assertTrue(result)

    def test_period_format(self):
        conversation = classes.Conversation(timeline=self.test_timeline)
        periods = conversation.data['periods']
        for period in periods:
            self.assertTrue('subtitle' in period)
            self.assertTrue('statuses' in period)
            self.assertTrue('empty' in period)
            self.assertTrue('id' in period)
            self.assertTrue('empty_message' in period)

    def test_period_status_format(self):
        conversation = classes.Conversation(timeline=self.test_timeline)
        periods = conversation.data['periods']
        for period in periods:
            statuses = period['statuses']
            for status in statuses:
                self.assertTrue('adaptation' in status)
                self.assertTrue('origin' in status)
                self.assertTrue('text' in status)
                self.assertTrue('style_classes' in status)
                self.assertTrue('created_at' in status)
                self.assertTrue('author' in status)
                self.assertTrue('in_reply_to_status_id' in status)

    def test_hour_parsing(self):
        timeline_json = {
            'start': "2001-02-03T20:44:32.316656+00:00",
            'cutoff': "2001-02-03T15:44:32.316656+00:00",
        }
        conversation = classes.Conversation(timeline_json)
        start, cutoff = conversation._get_timeline_interval()
        self.assertEqual(start.hour, 20)
        self.assertEqual(cutoff.hour, 15)

    def test_timezone_parsing(self):
        timeline_json = {
            'start': "2001-02-03T20:44:32.316656+00:00",
            'cutoff': "2001-02-03T15:44:32.316656+00:00",
        }
        conversation = classes.Conversation(timeline_json)
        start, cutoff = conversation._get_timeline_interval()
        self.assertTrue(start.tzinfo)
        self.assertTrue(cutoff.tzinfo)

    def test_eastern_time_parsing(self):
        timeline_json = {
            'start': "2001-02-03T20:44:32.316656-05:00",
            'cutoff': "2001-02-03T15:44:32.316656-05:00",
        }
        conversation = classes.Conversation(timeline_json)
        start, cutoff = conversation._get_timeline_interval()
        start = start.astimezone(timezone.utc)
        cutoff = cutoff.astimezone(timezone.utc)
        self.assertEqual(start.hour, 1)
        self.assertEqual(cutoff.hour, 20)

    def test_central_time_parsing(self):
        timeline_json = {
            'start': "2001-02-03T20:44:32.316656-06:00",
            'cutoff': "2001-02-03T15:44:32.316656-06:00",
        }
        conversation = classes.Conversation(timeline_json)
        start, cutoff = conversation._get_timeline_interval()
        start = start.astimezone(timezone.utc)
        cutoff = cutoff.astimezone(timezone.utc)
        self.assertEqual(start.hour, 2)
        self.assertEqual(cutoff.hour, 21)

    def test_adapter(self):
        def adapter(status):
            text = status['text']
            return {'topic_header': 'TRANSFORMED {0}'.format(text)}
        conversation = classes.Conversation(timeline=self.test_timeline, adapter=adapter)
        self.assertEqual(len(list(conversation.nav)), 7)




