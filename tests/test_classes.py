import unittest
import datetime
from conversationalist import classes


def generate_mock_statuses():
    dt1 = datetime.datetime.now()
    dt2 = dt1 + datetime.timedelta(hours=-1)
    dt3 = dt1 + datetime.timedelta(hours=-2)
    dt4 = dt1 + datetime.timedelta(hours=-3)
    dt5 = dt1 + datetime.timedelta(hours=-4)
    dt6 = dt1 + datetime.timedelta(hours=-5)
    dt7 = dt1 + datetime.timedelta(hours=-6)
    datetime_fixtures = [dt3, dt2, dt1, dt7, dt5, dt6, dt4]
    mock_statuses = list()
    for dt in datetime_fixtures:
        mock_status = MockStatus()
        mock_status.created_at = dt
        mock_status.id = len(mock_statuses) + 1
        mock_statuses.append(mock_status)
    return mock_statuses, dt7


class MockStatus:
    pass


class MockAPI:
    def user_timeline(self, user, max_id=None):
        mock_statuses = generate_mock_statuses()
        return mock_statuses


class TimelineTests(unittest.TestCase):

    def setUp(self):
        mock_statuses, earliest = generate_mock_statuses()
        self.mock_statuses = mock_statuses
        self.earliest_datetime = earliest

    def test_get_earliest_status(self):
        timeline = classes.Timeline()
        timeline.statuses = self.mock_statuses
        earliest_status = timeline.get_earliest_status()
        self.assertTrue(earliest_status.created_at == self.earliest_datetime)
        self.assertTrue(earliest_status.created_at.day == self.earliest_datetime.day)
        self.assertTrue(earliest_status.created_at.hour == self.earliest_datetime.hour)
        self.assertTrue(earliest_status.created_at.minute == self.earliest_datetime.minute)
        self.assertTrue(earliest_status.created_at.second == self.earliest_datetime.second)

class GenerateTimelineTests(unittest.TestCase):

    def test_generate_timeline(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, user='testuser')


