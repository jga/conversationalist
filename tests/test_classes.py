from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from io import StringIO
import json
import os
import re
import sys
import unittest
from conversationalist import classes, adapters
from .adapters import ConvoParticipationAdapter as ParticipationAdapter
from .adapters import ConvoTextAdapter as TextAdapter
from .mocking import generate_mock_user, generate_mock_status, generate_mock_statuses, generate_mock_timeline_data
from .mocking import MockAPI


class StatusEncoderTests(unittest.TestCase):

    def test_origin_encoding(self):
        origin_user = generate_mock_user()
        origin_user.id = 5
        origin_user.screen_name = 'original_user'
        origin_status = generate_mock_status(1, user=origin_user)
        origin_status.text = 'Original status text'
        child_status = generate_mock_status(2)
        child_status.origin = origin_status
        child_status.in_reply_to_status_id = 1
        child_status_json =  json.loads(classes.StatusEncoder().encode(child_status))
        self.assertEqual(child_status_json['origin']['author']['id'], 5, msg=child_status_json)


class TimelineTests(unittest.TestCase):

    def setUp(self):
        dt1 = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
        dt2 = dt1 + timedelta(hours=-1)
        dt3 = dt1 + timedelta(hours=-3)
        dt4 = dt1 + timedelta(hours=-5)
        dt5 = dt1 + timedelta(hours=-6)
        dt6 = dt1 + timedelta(hours=-7)
        dt7 = dt1 + timedelta(hours=-10)
        datetime_fixtures = [dt1, dt2, dt3, dt4, dt5, dt6, dt7]
        self.mock_timeline_data = generate_mock_timeline_data(datetime_fixtures=datetime_fixtures)
        self.earliest_datetime = dt7
        self.latest_datetime = dt1
        tests_path = os.path.dirname(__file__)
        self.test_file_directory = os.path.join(tests_path, 'tmp_test_output/')

    def test_get_earliest_status(self):
        timeline = classes.Timeline()
        timeline.data = self.mock_timeline_data
        earliest_status = timeline.get_earliest_status()
        self.assertTrue(earliest_status.created_at == self.earliest_datetime)
        self.assertTrue(earliest_status.created_at.day == self.earliest_datetime.day)
        self.assertTrue(earliest_status.created_at.hour == self.earliest_datetime.hour)
        self.assertTrue(earliest_status.created_at.minute == self.earliest_datetime.minute)
        self.assertTrue(earliest_status.created_at.second == self.earliest_datetime.second)

    def test_generate_timeline(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, username='testuser')
        self.assertEqual(len(list(timeline.data.values())), 7)

    def test_generate_timeline_multiple_requests(self):
        api = MockAPI(multi_response=True)
        timeline = classes.Timeline(api=api, username='testuser')
        self.assertEqual(len(list(timeline.data.values())), 7)

    def test_generate_timeline_with_tight_central_cutoff(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, username='testuser', timeframe=-12)
        self.assertEqual(len(list(timeline.data.values())), 7)

    def test_generate_timeline_with_tight_utc_cutoff(self):
        api = MockAPI()
        timeline = classes.Timeline(api=api, username='testuser', timeframe=1)
        self.assertTrue(len(list(timeline.data.values())), 1)

    def test_batch_with_maximum_id(self):
        timeline = classes.Timeline(username='testuser')
        api = MockAPI(multi_response=True)
        timeline.api = api
        statuses = timeline.get_timeline_batch(max_id=2)
        self.assertEqual(statuses[0].text, 'Content for tweet mock status 1')

    def test_old_status_beyond_cutoff(self):
        current_datetime = datetime.now(tz=timezone.utc)
        fresh_status = generate_mock_status(2, created_at=current_datetime)
        expired_datetime = current_datetime + timedelta(hours=-10)
        old_status = generate_mock_status(1, created_at=expired_datetime)
        api = MockAPI(statuses=[fresh_status, old_status])
        timeline = classes.Timeline(username='testuser', timeframe=2)
        timeline.api = api
        timeline.earliest_id = 2
        timeline.earliest_status = fresh_status
        timeline.data['1'] = old_status
        timeline.data['2'] = fresh_status
        self.assertEqual(timeline.earliest_status.id, 2)
        self.assertFalse(timeline._has_next_tweets())
        self.assertEqual(timeline.earliest_status.id, 1)

    def test_load_statuses(self):
        status1 = generate_mock_status(1)
        original_created_at = status1.created_at
        bad_status1 = generate_mock_status(1)
        statuses = [status1, bad_status1]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, username='testuser')
        timeline.load(statuses)
        self.assertTrue(len(list(timeline.data.values())), 1)
        self.assertEqual(timeline.data['1'].created_at.microsecond,
                         original_created_at.microsecond)

    def test_load_status_with_reply_id(self):
        original_user = generate_mock_user()
        original_user.id = 2
        original_user.screen_name = 'reply_user'
        original_status = generate_mock_status(1, user=original_user)
        child_status = generate_mock_status(2)
        child_status.in_reply_to_status_id = 1
        api = MockAPI([original_status, child_status])
        timeline = classes.Timeline(api=api, username='testuser')
        self.assertEqual(timeline.data['2'].origin.author_name, 'reply_user')

    def test_load_status_with_reply_error(self):
        child_status = generate_mock_status(2)
        child_status.in_reply_to_status_id = 7
        api = MockAPI([child_status])
        out = StringIO()
        sys.stdout = out
        classes.Timeline(api=api, username='testuser')
        output = out.getvalue().strip()
        self.assertEqual(output, 'Error while fetching origin for tweet 2')

    def test_has_next_tweets_no_statuses(self):
        statuses = []
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, username='testuser')
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_exceeded_cutoff(self):
        old_status = generate_mock_status(1)
        old_status.created_at = old_status.created_at + timedelta(hours=-2)
        statuses = [old_status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, username='testuser', timeframe=1)
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_exhausted(self):
        status = generate_mock_status(1)
        statuses = [status]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, username='testuser')
        self.assertFalse(timeline._has_next_tweets())

    def test_has_next_tweets_under_cutoff(self):
        status = generate_mock_status(1)
        status2 = generate_mock_status(2)
        statuses = [status, status2]
        api = MockAPI(statuses=statuses)
        timeline = classes.Timeline(api=api, username='testuser', timeframe=5)
        status3 = generate_mock_status(3)
        status3.created_at = status.created_at + timedelta(hours=-1)
        timeline.data[str(status3.id)] = status3
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
        timeline = classes.Timeline(api=api, username='testuser')
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
                self.assertEqual(start.utcoffset(), timedelta(0))
                self.assertTrue('cutoff' in data)
                self.assertTrue('cutoff' in data)
                cutoff_iso_date_string = data['cutoff']
                cutoff = parse(cutoff_iso_date_string)
                self.assertTrue(isinstance(cutoff, datetime))
                self.assertTrue(cutoff.tzinfo)
                self.assertEqual(cutoff.utcoffset(), timedelta(0))
                self.assertTrue('total' in data)
                self.assertEqual(data['total'], 5)
                self.assertTrue('data' in data)
                self.assertTrue(isinstance(data['data'], dict))
                self.assertTrue('username' in data)
                self.assertEqual(data['username'], 'testuser')
        finally:
            if os.path.isfile(test_output_file_path):
                os.remove(test_output_file_path)


class PrepareHourlySummaryTests(unittest.TestCase):
    def test_summary(self):
        start = datetime(2001, 2, 3, 5, 6, 7, 8)
        cutoff = datetime(2001, 2, 3, 0, 0, 0, 0)
        summary = adapters.initialize_hourly_summary(start, cutoff)
        self.assertEqual(len(list(summary.values())), 6, msg=summary)
        self.assertTrue('2001-02-03T00:00:00' in summary, msg=summary)
        self.assertTrue('2001-02-03T01:00:00' in summary, msg=summary)
        self.assertTrue('2001-02-03T02:00:00' in summary, msg=summary)
        self.assertTrue('2001-02-03T03:00:00' in summary, msg=summary)
        self.assertTrue('2001-02-03T04:00:00' in summary, msg=summary)
        self.assertTrue('2001-02-03T05:00:00' in summary, msg=summary)


class ConversationTests(unittest.TestCase):
    def setUp(self):
        dt1 = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
        dt2 = dt1 + timedelta(hours=-1)
        dt3 = dt1 + timedelta(hours=-3)
        dt4 = dt1 + timedelta(hours=-5)
        dt5 = dt1 + timedelta(hours=-6)
        dt6 = dt1 + timedelta(hours=-7)
        dt7 = dt1 + timedelta(hours=-10)
        self.earliest_datetime = dt7
        self.latest_datetime = dt1
        datetime_fixtures = [dt1, dt2, dt3, dt4, dt5, dt6, dt7]
        statuses = generate_mock_statuses(datetime_fixtures=datetime_fixtures)
        api = MockAPI(statuses=statuses)
        # we skip passing in the API so we can force start and cutoff properties
        timeline = classes.Timeline(username='testuser')
        timeline.start = datetime(2001, 2, 3, 5, 30, 0, tzinfo=timezone.utc)
        timeline.cutoff = timeline.start + timedelta(hours=-24)
        timeline.api = api
        timeline._generate_timeline()
        encoder = classes.TimelineEncoder()
        timeline_json = json.loads(encoder.encode(timeline))
        self.test_timeline = timeline_json

    def test_title_after_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        self.assertEqual(conversation.data['title'], 'Tick Tock')

    def test_custom_title_after_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            title='Other Title',
                                            adapter=ParticipationAdapter )
        self.assertEqual(conversation.data['title'], 'Other Title')

    def test_empty_timeline_interval(self):
        conversation = classes.Conversation()
        start, cutoff = conversation._get_timeline_interval()
        self.assertEqual(start, None)
        self.assertEqual(cutoff, None)

    def test_title_periods_initial_update(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        self.assertTrue(isinstance(conversation.data['periods'], list))
        periods = conversation.data['periods']
        self.assertTrue(len(periods), 6)

    def test_title_periods_subtitles(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        periods = conversation.data['periods']
        for period in periods:
            subtitle = period['subtitle']
            self.assertTrue(isinstance(subtitle, str))
            regex_pattern = re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)')
            result = regex_pattern.match(subtitle)
            self.assertTrue(result)

    def test_period_format(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        periods = conversation.data['periods']
        for period in periods:
            self.assertTrue('subtitle' in period)
            self.assertTrue('statuses' in period)
            self.assertTrue('empty' in period)
            self.assertTrue('id' in period)
            self.assertTrue('empty_message' in period)

    def test_period_status_format(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        periods = conversation.data['periods']
        for period in periods:
            statuses = period['statuses']
            for status in statuses:
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
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        self.assertEqual(len(list(conversation.data['nav'])), 7, msg=conversation.data)

    def test_nav_sort(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        self.assertEqual(conversation.data['nav'], ['1', '2', '3', '4', '5', '6', '7'])

    def test_style_words(self):
        conversation = classes.Conversation(timeline=self.test_timeline,
                                            adapter=ParticipationAdapter)
        for period in conversation.data['periods']:
            for status in period['statuses']:
                self.assertEqual(set(status['style_classes'].split()), {'mock', 'status'})

    def test_period_sort_earliest(self):
        conversation = classes.Conversation(timeline=self.test_timeline, adapter=TextAdapter)
        periods = conversation.data['periods']
        earliest = self.earliest_datetime
        clean_earliest = earliest.replace(minute=0, second=0)
        unix_epoch = datetime(1970, 1, 1, tzinfo=earliest.tzinfo)
        seconds = (clean_earliest - unix_epoch).total_seconds()
        key = int(seconds)
        self.assertEqual(key, periods[0]['id'], msg=periods)

    def test_period_sort_latest(self):
        conversation = classes.Conversation(timeline=self.test_timeline, adapter=TextAdapter)
        periods = conversation.data['periods']
        last = self.latest_datetime
        clean_latest = last.replace(minute=0, second=0)
        unix_epoch = datetime(1970, 1, 1, tzinfo=last.tzinfo)
        seconds = (clean_latest - unix_epoch).total_seconds()
        key = int(seconds)
        self.assertEqual(key, periods[6]['id'], msg=periods)

    def test_load_timeline_json(self):
        tests_path = os.path.dirname(__file__)
        timeline_file_path = os.path.join(tests_path, 'json/timeline.json')
        conversation = classes.Conversation(adapter=ParticipationAdapter)
        conversation.load(timeline_file_path)
        data = conversation.data
        self.assertEqual(len(data['periods']), 5)
        self.assertEqual(data['periods'][0]['subtitle'], 'Tuesday, February 23, 2010  8PM')
        self.assertEqual(data['periods'][1]['subtitle'], 'Wednesday, February 24, 2010  5AM')
        self.assertEqual(data['periods'][2]['subtitle'], 'Wednesday, February 24, 2010  6AM')
        self.assertEqual(data['periods'][3]['subtitle'], 'Wednesday, February 24, 2010  7AM')
        self.assertEqual(data['periods'][4]['subtitle'], 'Wednesday, February 24, 2010  8AM')
        self.assertEqual(data['title'], 'Tick Tock')
        self.assertEqual(data['nav'], ['1', '2', '3', '4', '5'])
        self.assertTrue(isinstance(data['participation'], classes.Participation))
        participation = data['participation']
        self.assertEqual(participation.participants.keys(), {'test_author'}, msg=participation.participants)
        participant = participation.participants['test_author']
        # It's six instead of five because of one of the tweets is a reply
        self.assertEqual(participant.exchange_count, 6)

    def test_load_timeline_json_central(self):
        tests_path = os.path.dirname(__file__)
        timeline_file_path = os.path.join(tests_path, 'json/timeline_central.json')
        conversation = classes.Conversation(adapter=ParticipationAdapter)
        conversation.load(timeline_file_path)
        data = conversation.data
        self.assertEqual(len(data['periods']), 5)
        self.assertEqual(data['periods'][0]['subtitle'], 'Tuesday, February 23, 2010  8PM')
        self.assertEqual(data['periods'][1]['subtitle'], 'Wednesday, February 24, 2010  5AM')
        self.assertEqual(data['periods'][2]['subtitle'], 'Wednesday, February 24, 2010  6AM')
        self.assertEqual(data['periods'][3]['subtitle'], 'Wednesday, February 24, 2010  7AM')
        self.assertEqual(data['periods'][4]['subtitle'], 'Wednesday, February 24, 2010  8AM')
        self.assertEqual(data['title'], 'Tick Tock')
        self.assertEqual(data['nav'], ['1', '2', '3', '4', '5'])
        self.assertTrue(isinstance(data['participation'], classes.Participation))
        participation = data['participation']
        self.assertEqual(participation.participants.keys(), {'test_author'}, msg=participation.participants)
        participant = participation.participants['test_author']
        self.assertEqual(participant.exchange_count, 5)


class ParticipationTests(unittest.TestCase):
    def test_ranked_profiles(self):
        participation = classes.Participation()
        busy_participant = classes.Participant('busy_participant', 'test.url.busy_participant')
        busy_participant.exchange_count = 10
        participation.participants[busy_participant.name] = busy_participant
        quiet_participant = classes.Participant('quiet_participant', 'test.url.quiet_participant')
        quiet_participant.exchange_count = 2
        participation.participants[quiet_participant.name] = quiet_participant
        inactive_participant = classes.Participant('inactive_participant', 'test.url.inactive_participant')
        inactive_participant.exchange_count = 0
        participation.participants[inactive_participant.name] = inactive_participant
        ranked = participation.get_ranked_profiles()
        self.assertEqual(ranked[0].name, 'busy_participant')
        self.assertEqual(ranked[1].name, 'quiet_participant')
        self.assertEqual(ranked[2].name, 'inactive_participant')



