from datetime import datetime, timedelta, timezone
import json
import pytz
from operator import attrgetter
from dateutil.parser import parse
from tweepy.error import TweepError
from tweepy.models import User, Status


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
        if isinstance(obj, User):
            return UserEncoder().default(obj)
        simple_origin = None
        origin = getattr(obj, 'origin', None)
        if origin:
            simple_origin = {
                'author': UserEncoder().default(obj.origin.author),
                'text': obj.origin.text
            }
        status = {
            'author': obj.author,
            'origin': simple_origin,
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
        timeline = {
            'start': obj.start.isoformat(),
            'cutoff': obj.cutoff.isoformat(),
            'data': obj.data,
            'total': obj.total,
            'username': obj.username
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
    def __init__(self, timeline=None, title='Tick Tock', adapter=None):
        """
        Initializes a ``Conversation`` object.

        When ``timeline``, ``start``, and ``cutoff`` data is passed, the
        class internally undertakes the exchange of status data into
        the conversation's format.  Otherwise, it just holds the
        state of whatever property data is passed.

        Args:
            timeline (dict): A JSON object representing a timeline.
            title (str): The name for the conversation object's data.
            adapter: Handles transformation logic for status data.

        Attributes:
            title (str): Main name for conversation.
            adapter: Handles transformation logic for status data.
            data (dict): Contains pairing of timestamps and statuses keyed to 'hourlies', as
                well as a title name keyed to 'title'.
        """
        self.data = None
        self.timeline = timeline
        self.title = title
        self.adapter = adapter
        self.update_conversation()

    def _get_timeline_interval(self):
        if self.timeline:
            start = parse(self.timeline['start'])
            cutoff = parse(self.timeline['cutoff'])
            return start, cutoff
        return None, None

    def update_conversation(self):
        """
        Applies the class instances adapter to the current timeline data.
        """
        if self.timeline and self.adapter:
            adapter = self.adapter(self)
            self.data = adapter.convert()

    def load(self, json_file):
        """
        Transforms the JSON data for a user timeline into
        relevant properties for this class.

        Args:
            json_file (str): The file location of the timeline JSON.
        """
        with open(json_file) as infile:
            timeline_json = json.load(infile)
        self.timeline = timeline_json
        self.update_conversation()


class Timeline(object):
    """
    Manages state of a a twitter user's timeline data.

    Attributes:
        api: Tweepy API instance.
        earliest_status: Holds the earliest status handled during timeline generation.
        start (datetime): When the timeline starts. Set to ``now`` at initialization.
        cutoff (datetime): When in the past the timeline's search for statuses ends.
        data (dict): Maps an identifier to status information.
        username (str): The targeted account's username.
    """
    def __init__(self, api=None, username=None, timeframe=-24):
        self.api = api
        self.earliest_status = None
        self.start = datetime.now(tz=timezone.utc)
        safe_timeframe = abs(timeframe) * -1
        self.cutoff = self.start + timedelta(hours=safe_timeframe)
        self.data = {}
        self.username = username
        if api and username:
            self._generate_timeline()

    def load(self, statuses):
        """
        The method transforms and appends the passed statuses to the class instances
        `statuses` property.

        If a status is a response, the method searches for the original
        tweet an adds the text and author name to the status data.

        Raises:
            TweepError: If tweepy error occurs while seeking an origin for a
                status, which is typically a tweet that was responded too.
        Args:
            statuses (list): A a list of tweepy ``Status`` objects.
        """
        for status in statuses:
            if str(status.id) not in self.data:
                # check if 'created_at' is naive. Tweepy creates naive created_at fields
                # from utc timestamps parsed from Twitter API's RFC 2822 format
                if status.created_at.tzinfo is None or \
                        status.created_at.tzinfo.utcoffset(status.created_at) is None:
                    utc = pytz.utc
                    # naive to utc
                    utc_created_at = utc.localize(status.created_at)
                    status.created_at = utc_created_at
                if status.created_at > self.cutoff:
                    #status.text = status.text.encode('ascii', 'ignore')
                    status.origin = None
                    if status.in_reply_to_status_id:
                        try:
                            status.origin = self.api.get_status(status.in_reply_to_status_id)
                            #status.origin.text = status.origin.text.encode('ascii', 'ignore')
                            user = status.origin.author
                            status.origin.author_name = user.screen_name
                        except TweepError:
                            print('Error while fetching origin for tweet {0}'.format(status.id))
                    self.data[str(status.id)] = status

    def get_earliest_status(self):
        """
        Sorts the class instance's `statuses` by their `created_at`
        property from oldest at the start of the list to newest
        at the end of the list.

        Returns:
            ``Status``: The earliest (oldest) status or ``None`` if empty.
        """
        earliest = None
        if self.data:
            sorted_statuses = sorted(self.data.values(), key=lambda status: status.created_at)
            earliest = sorted_statuses[0]
        return earliest

    @property
    def total(self):
        """
        Computed property representing the total count of statuses for the instance.

        Returns:
            int: The total count of statuses.
        """
        return len(list(self.data.values()))

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
            return self.api.user_timeline(self.username)
        else:
            return self.api.user_timeline(self.username, max_id=max_id)

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
            earliest_id = getattr(self.earliest_status, 'id', None)
            new_tweets = self.get_timeline_batch(earliest_id)
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
