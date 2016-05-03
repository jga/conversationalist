from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from tweepy.error import TweepError
from conversationalist import classes

def generate_mock_user():
    user = Mock(spec=classes.User)
    user.id = 1
    user.screen_name = 'test_author'
    user.profile_image_url = "http:\/\/a1.twimg.com\/profile_images\/101\/avatar_normal.png"
    return user


def generate_mock_status(id=None, text=None, created_at=None, user=None):
    status = Mock(spec=classes.Status)
    status.id = id
    status.text = text if text else "The text for mock status {0}".format(status.id)
    status.created_at = created_at if created_at else datetime.utcnow()
    if user is None:
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
    return [dt1, dt2, dt3, dt4, dt5, dt6, dt7]


def generate_mock_timeline_data(naive_dt=True, datetime_fixtures=None):
    """
    A list of statuses. May be set to have a utc timezone with a ``False``
    value for the ``naive_dt`` argument.
    """
    mock_data = dict()
    if datetime_fixtures is None:
        datetime_fixtures, latest = generate_datetime_fixtures()
    for dt in datetime_fixtures:
        status = Mock(spec=classes.Status)
        status.id = len(mock_data) + 1
        status.text = "The text for mock status {0}".format(status.id)
        status.created_at = dt
        status.author = generate_mock_user()
        status.in_reply_to_status_id = None
        mock_data[str(status.id)] = status
    return mock_data


def generate_mock_statuses(naive_dt=True, datetime_fixtures=None):
    """
    A dict of statuses keyed to their id. Useful for mocking an API response.
    These are useful in``Timeline`` class testing.

    May be set to have a utc timezone with a ``False`` value for the ``naive_dt`` argument.
    """
    mock_statuses = list()
    if datetime_fixtures is None:
        datetime_fixtures = generate_datetime_fixtures()
    for dt in datetime_fixtures:
        identifier = len(mock_statuses) + 1
        mock_status_text = 'Content for tweet mock status {0}'.format(identifier)
        mock_status = generate_mock_status(identifier, mock_status_text)
        mock_status.created_at = dt
        mock_statuses.append(mock_status)
    return mock_statuses


class MockAPI:
    def __init__(self, statuses=None, multi_response=False):
        self.multi_response = multi_response
        if statuses is not None:
            self.statuses = statuses
        else:
            self.statuses = generate_mock_statuses()

    def rate_limit_status(self):
        info = {
            'resources': {
                'statuses': {
                    'test_key': 'test_value'
                }
            }
        }
        return info

    def get_status(self, status_id):
        status = next((s for s in self.statuses if s.id == status_id), None)
        if status:
            return status
        else:
            raise TweepError('No status with requested id')

    def user_timeline(self, user, max_id=None):
        if self.multi_response:
            if len(self.statuses) == 1:
                return self.statuses
            else:
                status = self.statuses.pop(0)
                return [status]
        else:
            return self.statuses

