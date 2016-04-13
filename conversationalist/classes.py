from datetime import datetime, timedelta, timezone
import time
import json
import pytz
import re
from operator import attrgetter
from operator import itemgetter
from dateutil.parser import parse
from tweepy.error import TweepError
from tweepy.models import User

DT_FORMAT = '%B-%d-%Y-%I-%p'
VIEW_DT_FORMAT = '%B %d, %Y %I:%M %p'
BLOCK_DT_FORMAT = '%A, %B %d, %Y  %-I%p'


def prepare_hourly_dict(start_dt, cutoff_dt):
    hd = {}
    start_dt.replace(minute=0)
    active_dt = cutoff_dt
    while active_dt < start_dt:
        hourly_key = active_dt.strftime(DT_FORMAT)
        #print 'Preparing key ' + hourly_key
        hd[hourly_key] = []
        active_dt = active_dt + timedelta(hours=1)
    return hd


def generate_hourly_summaries(hourly_dict):
    time_blocks = []
    for k, v in hourly_dict.items():
        struct_time = time.strptime(k, DT_FORMAT)
        seconds = time.mktime(struct_time)
        time_zone = pytz.timezone('America/Chicago')
        dt = datetime.fromtimestamp(time.mktime(struct_time), time_zone)
        subtitle = dt.strftime(BLOCK_DT_FORMAT)
        empty = True
        if len(v) > 0:
            empty = False
            message = 'No updates.'
            hour_block = {
                'id': seconds,
                'empty': empty,
                'empty_message': message,
                'subtitle': subtitle,
                'statuses': v
            }
            time_blocks.append(hour_block)
    time_blocks = sorted(time_blocks, key=itemgetter('id'))
    return time_blocks


class UserEncoder(json.JSONEncoder):
    def default(self, o):
        user = {
            'id': o.id,
            'screen_name': o.screen_name,
            'profile_image_url': o.profile_image_url
        }
        return user


class StatusEncoder(json.JSONEncoder):
    def default(self, o):
        origin = None
        if o.origin:
            origin = {
                'author': UserEncoder().default(o.origin.author),
                'text': o.origin.text
            }
            #print 'Added origin author'
            #print origin['author']['screen_name']
        status = {
            'author': o.author,
            'origin': origin,
            'text': o.text,
            'created_at': str(o.created_at)
        }
        return status


class TimelineEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, User):
            return UserEncoder().default(o)
        else:
            statuses = []
            for s in o.statuses:
                statuses.append(StatusEncoder().default(s))
            timeline = {
                # 'cutoff': o.cutoff.strftime("%Y-%m-%d %H:%M:%S.%f"),
                # 'start': o.start.strftime("%Y-%m-%d %H:%M:%S.%f"),
                'cutoff': str(o.cutoff),
                'start': str(o.start),
                'statuses': statuses,
                'total': o.total,
                'tz': o.tz.zone,
                'user': o.user
            }
            return timeline


class Participant(object):
    def __init__(self, name, profile_url=None):
        self.exchange_count = 0
        self.name = name
        self.profile_url = profile_url

    def increment_participation(self):
        self.exchange_count += 1


class Participation(object):
    def __init__(self):
        self.participants = {}

    def add_tweet(self, author):
        if author['screen_name'] in self.participants:
            participant = self.participants[author['screen_name']]
            participant.increment_participation()
        else:
            participant = Participant(author['screen_name'], author['profile_image_url'])
            #print 'Added participant ', author.screen_name, ' ', author.profile_image_url
            participant.increment_participation()
            self.participants[author['screen_name']] = participant

    def get_ranked_profiles(self):
        ranked_profiles = []
        for key in self.participants:
            ranked_profiles.append(self.participants[key])
        ranked_profiles = sorted(ranked_profiles, key=attrgetter('exchange_count'), reverse=True)
        return ranked_profiles


class Conversation1(object):
    def __init__(self, timeline, start, cutoff, title='Tick Tock',
                 style_words=None, pre_exchange=None, post_exchange=None):
        self.participation = Participation()
        self.exchanges = []
        self.title = title
        self.style_words = style_words
        self.pre_exchange = pre_exchange
        self.post_exchange = post_exchange
        hourly = prepare_hourly_dict(start, cutoff)
        self.data, self.nav = self._get_conversation(timeline, hourly)

    def _get_pre_content(self, status):
        if self.pre_exchange:
            return self.pre_exchange(status)
        else:
            return None

    def _get_post_content(self, status):
        if self.post_exchange:
            return self.post_exchange(status)
        else:
            return None

    def _get_style_classes(self, status):
        style_classes = ''
        style_matches = []
        if self.style_words:
            for word in self.style_words:
                pattern = r'\b%s\b' % word
                regex = re.compile(pattern, re.I)
                match = regex.search(status.text)
                if match:
                    word = word.replace(' ', '-')
                    style_matches.append(word)
        for m in set(style_matches):
            style_classes = ''.join((style_classes, ' ', m, ))
        return style_classes

    def _get_conversation(self, timeline, hourly):
        item_headers = []
        for status in timeline.statuses:
            self.participation.add_tweet(status.author)
            if status.origin:
                self.participation.add_tweet(status.origin.author)
            status.pre_content = self._get_pre_content(status)
            if status.pre_content:
                item_headers.append(status.pre_content)
            status.post_content = self._get_post_content(status)
            status.style_classes = self._get_style_classes(status)
            time_key = status.created_at.strftime(DT_FORMAT)
            #print 'Created key ' + time_key
            hourly[time_key].insert(0, status)
        hourlies = {
            'title': self.title,
            'hourlies': generate_hourly_summaries(hourly)
        }
        return hourlies, set(item_headers)


class Conversation(object):
    """
    Manages the state of user's tweet stream during application processing.
    """
    def __init__(self, timeline, start, cutoff, title='Tick Tock',
                 style_words=None, pre_exchange=None, post_exchange=None):
        self.participation = Participation()
        self.exchanges = []
        self.title = title
        self.style_words = style_words
        self.pre_exchange = pre_exchange
        self.post_exchange = post_exchange
        hourly = prepare_hourly_dict(start, cutoff)
        self.data, self.nav = self._get_conversation(timeline, hourly)

    def _get_pre_content(self, status):
        if self.pre_exchange:
            return self.pre_exchange(status)
        else:
            return None

    def _get_post_content(self, status):
        if self.post_exchange:
            return self.post_exchange(status)
        else:
            return None

    def _get_style_classes(self, status):
        style_classes = ''
        style_matches = []
        if self.style_words:
            for word in self.style_words:
                pattern = r'\b%s\b' % word
                regex = re.compile(pattern, re.I)
                match = regex.search(status['text'])
                if match:
                    word = word.replace(' ', '-')
                    style_matches.append(word)
        for m in set(style_matches):
            style_classes = ''.join((style_classes, ' ', m, ))
        return style_classes

    def _get_conversation(self, timeline, hourly):
        item_headers = []
        for status in timeline['statuses']:
            self.participation.add_tweet(status['author'])
            if status['origin']:
                self.participation.add_tweet(status['origin']['author'])
            status['pre_content'] = self._get_pre_content(status)
            if status['pre_content']:
                item_headers.append(status['pre_content'])
            status['post_content'] = self._get_post_content(status)
            status['style_classes'] = self._get_style_classes(status)
            time_key = parse(status['created_at']).strftime(DT_FORMAT)
            #print 'Created key ' + time_key
            hourly[time_key].insert(0, status)
        hourlies = {
            'title': self.title,
            'hourlies': generate_hourly_summaries(hourly)
        }
        nav = sorted(set(item_headers))
        return hourlies, nav


class Timeline(object):
    """
    Manages state of a a twitter user's timeline data.
    Attributes:
        earliest_id (int): The identifier for the 'earliest' tweet status.
    """
    def __init__(self, api=None, user=None, timeframe=-24, tz_name='America/Chicago'):
        self.tz = pytz.timezone(tz_name)
        self.api = api
        self.current_earliest_status = None
        self.earliest_id = None
        self.encoder = TimelineEncoder
        self.cutoff = datetime.now(tz=self.tz) + timedelta(hours=timeframe)
        self.start = datetime.now(tz=self.tz)
        self.statuses = []
        self.user = user
        if api and user:
            self._generate_timeline()

    def load(self, statuses):
        """
        The method transforms and appends the passed statuses to the class instances
        `statuses` property.

        As part of the transformation of status data, the method converts
        the status `created_at` timestamp into the class instances
        timezone. Additionally, the method encodes the text to 'ascii'.

        If a status is a response, the method searches for the original
        tweet an adds the text and author name to the status data.

        Raises:
            TweepError: If tweepy error occurs while seeking an origin for a
                status, which is typically a tweet that was responded too.
        Args:
            statuses (list): A list of tweepy ``Status`` objects.
        """
        for status in statuses:
            utc = pytz.utc
            status.created_at = utc.localize(status.created_at).astimezone(self.tz)
            if status.created_at > self.cutoff:
                status.text = status.text.encode('ascii', 'ignore')
                status.origin = None
                if status.in_reply_to_status_id:
                    try:
                        status.origin = self.api.get_status(status.in_reply_to_status_id)
                        status.origin.text = status.origin.text.encode('ascii', 'ignore')
                        user = status.origin.user
                        status.origin.author_name = user.screen_name
                    except TweepError as e:
                        print('Error while fetching origin for tweet {0}'.format(status.id))
                self.statuses.append(status)

    def get_earliest_status(self):
        """
        Sorts the class instance's `statuses` by their `created_at`
        property from oldest at the start of the list to newest
        at the end of the list.

        Additionally, sets the 'earliest_id' to that of the earliest
        status.

        Returns:
            The earliest (oldest) status or ``None`` if empty.
        """
        earliest = None
        if self.statuses:
            self.statuses.sort(key=lambda s: s.created_at)
            earliest = self.statuses[0]
        return earliest


    @property
    def total(self):
        return len(self.statuses)

    def get_timeline_batch(self, max_id=None):
        """
        Gets a batch of statuses for a user.

        Args:
            max_id: The last identifier that included in this batch
              of statuses.

        Returns:
            list: A list of tweepy ``Status`` objects. The maximum size of
            the list is 20.
        """
        if max_id is None:
            return self.api.user_timeline(self.user)
        else:
            return self.api.user_timeline(self.user, max_id=max_id)

    def _has_tweets_available(self):
        new_earliest_status = self.get_earliest_status()
        if new_earliest_status:
            # Exceeded cutoff because the earliest status is older (lesser) than the cutoff
            if new_earliest_status.created_at < self.cutoff:
                self.current_earliest_status = new_earliest_status
                return False
            # In case all available tweets are exhausted
            if self.current_earliest_status and \
                    self.current_earliest_status.id == new_earliest_status.id:
                return False
            # keep going - cutoff not exceeded and new earliest id not the current earliest id
            self.current_earliest_status = new_earliest_status
            return True
        return False

    def _generate_timeline(self):
        tweets_available = True
        while tweets_available:
            next_tweets = self.get_timeline_batch(self.earliest_id)
            if next_tweets:
                self.load(next_tweets)
                tweets_available = self._has_tweets_available()
            else:
                tweets_available = False

    def to_json(self, file_path):
        with open(file_path, 'w') as outfile:
            json.dump(self, outfile, cls=self.encoder, indent=2)

