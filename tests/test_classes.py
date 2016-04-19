import unittest
import os
from datetime import datetime, timezone, timedelta
from conversationalist import classes


class MockStatus:
    def __init__(self, text=None):
        self.id = 1
        self.author = 'testing_author'
        if text:
            self.text = text
        else:
            self.text = 'Testing content.'
        self.in_reply_to_status_id = None
        self.created_at = datetime.utcnow()


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
        mock_status = MockStatus()
        mock_status.created_at = dt
        mock_status.id = len(mock_statuses) + 1
        mock_statuses[str(mock_status.id)] = mock_status
    return mock_statuses, earliest


def generate_mock_statuses(naive_dt=True):
    """
    A dict of statuses keyed to their id. Useful for ``Timeline`` class testing.

    May be set to have a utc timezone with a ``False`` value for the ``naive_dt`` argument.
    """
    mock_statuses = list()
    datetime_fixtures, earliest = generate_datetime_fixtures()
    for dt in datetime_fixtures:
        mock_status = MockStatus()
        mock_status.created_at = dt
        mock_status.id = len(mock_statuses) + 1
        mock_status.text = 'Content for tweet status {0}'.format(mock_status.id)
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
        status1 = MockStatus()
        status1.id = 1
        original_created_at = status1.created_at
        bad_status1 = MockStatus()
        bad_status1.id = 1
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
        old_status = MockStatus()
        old_status.created_at = old_status.created_at + timedelta(hours=-2)
        statuses = [old_status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', timeframe=1)
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_exhausted(self):
        status = MockStatus()
        statuses = [status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser')
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_under_cutoff(self):
        status = MockStatus()
        status2 = MockStatus()
        statuses = [status, status2]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser', timeframe=5)
        status3 = MockStatus()
        status3.id = 3
        status3.created_at = status.created_at + timedelta(hours=-1)
        timeline.statuses[str(status3.id)] = status3
        self.assertTrue(timeline._has_next_tweets())
        self.assertEqual(timeline.earliest_status.id, 3)

    def test_to_json(self):
        status = MockStatus()
        status.created_at = datetime.utcnow()
        statuses = [status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, user='testuser')
        test_output_file_path = os.path.join(self.test_file_directory, 'test_to_json.json')
        try:
            timeline.to_json(test_output_file_path)
        finally:
            if os.path.isfile(test_output_file_path):
                #os.remove(test_output_file_path)
                pass

