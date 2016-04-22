from datetime import datetime, timedelta, timezone
import time
import json
import pytz
import re
from operator import attrgetter
from operator import itemgetter
from dateutil.parser import parse
from tweepy.error import TweepError
from tweepy.models import User, Status

DT_FORMAT = '%B-%d-%Y-%I-%p'
VIEW_DT_FORMAT = '%B %d, %Y %I:%M %p'
BLOCK_DT_FORMAT = '%A, %B %d, %Y  %-I%p'


def initialize_hourly_summary(start, cutoff, datetime_format=DT_FORMAT):
    """
    Generates a dict that contains statuses for each hour during
    a timeframe. The statuses are keyed to a timestamp string.

    At initialization, the list for each timestamp is empty.

    Args:
        start (datetime): The timeline's start.
        cutoff (datetime): When the timeline's status search ends.
        datetime_format: The format for the timestamp key.

    Returns:
        dict: Statuses keyed to timestamps arranged in hourly increments.
    """
    hourly_summary = {}
    start.replace(minute=0)
    active = cutoff
    while active < start:
        hourly_key = active.strftime(datetime_format)
        hourly_summary[hourly_key] = []
        active = active + timedelta(hours=1)
    return hourly_summary


def to_periods(hourly_summary, tz_name='UTC'):
    periods = []
    for timestamp, statuses in hourly_summary.items():
        struct_time = time.strptime(timestamp, DT_FORMAT)
        seconds = time.mktime(struct_time)
        time_zone = pytz.timezone(tz_name)
        dt = datetime.fromtimestamp(time.mktime(struct_time), time_zone)
        subtitle = dt.strftime(BLOCK_DT_FORMAT)
        if len(statuses) > 0:
            empty = False
            message = 'No updates.'
            hour_block = {
                'id': seconds,
                'empty': empty,
                'empty_message': message,
                'subtitle': subtitle,
                'statuses': statuses
            }
            periods.append(hour_block)
    periods = sorted(periods, key=itemgetter('id'))
    return periods


class UserEncoder(json.JSONEncoder):
    """
    Encodes ``tweepy`` ``User`` objects into an abbreviated JSON format object.

    Encodes the fields ``id``, ``screen_name``, and ``profile_image_url``. And that's
    it.
    """
    def default(self, o):
        user = {
            'id': o.id,
            'screen_name': o.screen_name,
            'profile_image_url': o.profile_image_url
        }
        return user


class StatusEncoder(json.JSONEncoder):
    """
    Encodes `~.classes.Status` objects into JSON.

    The ``created_at`` property is encoded as a string in ISO8601 format.
    """
    def default(self, obj):
        origin = None
        if obj.origin:
            origin = {
                'author': UserEncoder().default(obj.origin.author),
                'text': obj.origin.text
            }
        status = {
            'author': obj.author,
            'origin': origin,
            'text': obj.text,
            'created_at': obj.created_at.isoformat(),
            'in_reply_to_status_id': getattr(obj, 'in_reply_to_status_id', '')
        }
        return status


class TimelineEncoder(json.JSONEncoder):
    """
    Encodes `~.classes.Timeline` objects into JSON.

    The ``start`` and ``cutoff`` properties are encoded as strings in ISO8601 format.
    """
    def default(self, obj):
        if isinstance(obj, User):
            return UserEncoder().default(obj)
        if isinstance(obj, Status):
            return StatusEncoder().default(obj)
        if isinstance(obj, Timeline):
            timeline = {
                'start': obj.start.isoformat(),
                'cutoff': obj.cutoff.isoformat(),
                'statuses': obj.statuses,
                'total': obj.total,
                'tz': obj.tz.zone,
                'user': obj.user
            }
            return timeline
        else:
            pass


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


class Conversation(object):
    """
    Manages the state of user's tweet stream during application processing.
    """
    def __init__(self, timeline=None, title='Tick Tock',
                 style_words=None, adapter=None):
        """
        Initializes a ``Conversation`` object.

        When ``timeline``, ``start``, and ``cutoff`` data is passed, the
        class internally undertakes the exchange of status data into
        the conversation's format.  Otherwise, it just holds the
        state of whatever property data is passed.

        Args:
            timeline (dict): A JSON object representing a timeline.
            title (str): The name for the conversation object's data.
            style_words (list): The strings are added as CSS selector classes in
                conversation template.
            adapter: Handles transformation logic for status data.

        Attributes:
            participation (:class:``~.classes.Participation``): Tallies engagement.
            title (str): Main name for conversation.
            style_words (list): Words that will trigger addition of a CSS style class in template.
            adapter: Handles transformation logic for status data.
            data (dict): Contains pairing of timestamps and statuses keyed to 'hourlies', as
                well as a title name keyed to 'title'.
            nav: Helpful navigation data for topics identified by content handlers.
        """
        self.participation = Participation()
        self.data = None
        self.nav = None
        self.timeline = timeline
        self.title = title
        self.style_words = style_words
        self.adapter = adapter
        self.update_conversation()

    def transform_content(self, status):
        """
        Applies the class instances adapter to the current status.

        Args:
            status(dict): Tweet status data

        Returns:
            The result from passing the status to the adapter function or ``None`` if
            an adapter is not set for the class instance.
        """
        if self.adapter:
            return self.adapter(status)
        else:
            return None

    def get_style_classes(self, status):
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

    def _get_timeline_interval(self):
        if self.timeline:
            start = parse(self.timeline['start'])
            cutoff = parse(self.timeline['cutoff'])
            return start, cutoff
        return None, None

    def update_conversation(self):
        """
        Iterates through conversation status dictionaries adding their data to
        the instances ``Participation`` property, handling content transformations,
        and inserting style classes.  This logic helps create more informative
        pages once the data is rendered.
        """
        if self.timeline:
            start, cutoff = self._get_timeline_interval()
            hourly_summary = initialize_hourly_summary(start, cutoff)
            statuses = self.timeline.get('statuses', {})
            topic_headers = []
            for identifier, status in statuses.items():
                self.participation.add_tweet(status['author'])
                if status['origin']:
                    self.participation.add_tweet(status['origin']['author'])
                status['adaptation'] = self.transform_content(status)
                if status['adaptation'] and 'topic_header' in status['adaptation']:
                    topic_headers.append(status['adaptation']['topic_header'])
                status['style_classes'] = self.get_style_classes(status)
                time_key = parse(status['created_at']).strftime(DT_FORMAT)
                hourly_summary[time_key].insert(0, status)
            self.data = {
                'title': self.title,
                'periods': to_periods(hourly_summary)
            }
            self.nav = sorted(set(topic_headers))

    def load(self, json_file, settings=None):
        """
        Transforms the JSON data for a user timeline into
        relevant properties for this class.

        Args:
            json_file (str): The file location of the timeline JSON.
            pre_exchange (dict): Configuration information to be set into
                conversation instance.
        """
        with open(json_file) as infile:
            timeline_json = json.load(infile)
        self.timeline = timeline_json
        self.update_conversation()


class Timeline(object):
    """
    Manages state of a a twitter user's timeline data.

    Attributes:
        earliest_id (int): The identifier for the 'earliest' tweet status.
    """
    def __init__(self, api=None, user=None, timeframe=-24, tz_name='UTC'):
        self.tz = pytz.timezone(tz_name)
        self.api = api
        self.earliest_status = None
        self.earliest_id = None
        safe_timeframe = abs(timeframe) * -1
        self.cutoff = datetime.now(tz=self.tz) + timedelta(hours=safe_timeframe)
        self.start = datetime.now(tz=self.tz)
        self.statuses = {}
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
            statuses (list): A a list of tweepy ``Status`` objects.
        """
        for status in statuses:
            if str(status.id) not in self.statuses:
                # check if 'created_at' is naive. Tweepy creates naive created_at fields
                # from utc timestamps parsed from Twitter API's RFC 2822 format
                if status.created_at.tzinfo is None or \
                        status.created_at.tzinfo.utcoffset(status.created_at) is None:
                    utc = pytz.utc
                    # naive to utc
                    utc_created_at = utc.localize(status.created_at)
                    # utc to user-selected timezone
                    status.created_at = utc_created_at.astimezone(self.tz)
                if status.created_at > self.cutoff:
                    #status.text = status.text.encode('ascii', 'ignore')
                    status.origin = None
                    if status.in_reply_to_status_id:
                        try:
                            status.origin = self.api.get_status(status.in_reply_to_status_id)
                            #status.origin.text = status.origin.text.encode('ascii', 'ignore')
                            user = status.origin.user
                            status.origin.author_name = user.screen_name
                        except TweepError as e:
                            print('Error while fetching origin for tweet {0}'.format(status.id))
                    self.statuses[str(status.id)] = status

    def get_earliest_status(self):
        """
        Sorts the class instance's `statuses` by their `created_at`
        property from oldest at the start of the list to newest
        at the end of the list.

        Returns:
            ``Status``: The earliest (oldest) status or ``None`` if empty.
        """
        earliest = None
        if self.statuses:
            sorted_statuses = sorted(self.statuses.values(), key=lambda status: status.created_at)
            earliest = sorted_statuses[0]
        return earliest

    @property
    def total(self):
        """
        Computed property representing the total count of statuses for the instance.

        Returns:
            int: The total count of statuses.
        """
        return len(list(self.statuses.values()))

    def get_timeline_batch(self, max_id=None):
        """
        Gets a batch of statuses for a user.

        If a ``max_id`` is passed, that is supplied to the API
        is a starting point for fetching the previous 20 tweets.

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

    def _has_next_tweets(self):
        """
        Checks current statuses to see if the timeframe cutoff for a user's timeline
        has been reached or available statuses have been exhausted.

        Returns:
            bool: ``True`` if additional twitter statuses that fit into the timeframe cutoff
                may exist. ``False`` otherwise.
        """
        new_earliest_status = self.get_earliest_status()
        if new_earliest_status:
            # Exceeded cutoff because the earliest status is older (lesser) than the cutoff
            if new_earliest_status.created_at < self.cutoff:
                self.earliest_status = new_earliest_status
                return False
            # In case all available tweets are exhausted
            if self.earliest_status and \
                    self.earliest_status.id == new_earliest_status.id:
                return False
            # keep going - cutoff not exceeded and new earliest id not the current earliest id
            self.earliest_status = new_earliest_status
            return True
        return False

    def _generate_timeline(self):
        """
        Called during instance intialization. It fetches tweet statuses allowed
        by the cutoff timeframe until available statuses are exhausted.
        """
        tweets_available = True
        while tweets_available:
            new_tweets = self.get_timeline_batch(self.earliest_id)
            if new_tweets:
                self.load(new_tweets)
                tweets_available = self._has_next_tweets()
            else:
                tweets_available = False

    def to_json(self, file_path):
        """
        Writes a JSON file base on instance data.

        Args:
            file_path (str): Where the JSON file will be written.
        """
        with open(file_path, 'w') as outfile:
            json.dump(self, outfile, cls=TimelineEncoder, indent=2)
        return file_path
