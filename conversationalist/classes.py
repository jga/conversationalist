import datetime
import json
import pytz
import re
from operator import attrgetter
from dateutil.parser import parse
from tweepy.error import TweepError
from tweepy.models import User
from . import utils


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
        hourly = utils.prepare_hourly_dict(start, cutoff)
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
            time_key = status.created_at.strftime(utils.DT_FORMAT)
            #print 'Created key ' + time_key
            hourly[time_key].insert(0, status)
        hourlies = {
            'title': self.title,
            'hourlies': utils.generate_hourly_summaries(hourly)
        }
        return hourlies, set(item_headers)


class Conversation(object):
    def __init__(self, timeline, start, cutoff, title='Tick Tock',
                 style_words=None, pre_exchange=None, post_exchange=None):
        self.participation = Participation()
        self.exchanges = []
        self.title = title
        self.style_words = style_words
        self.pre_exchange = pre_exchange
        self.post_exchange = post_exchange
        hourly = utils.prepare_hourly_dict(start, cutoff)
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
            time_key = parse(status['created_at']).strftime(utils.DT_FORMAT)
            #print 'Created key ' + time_key
            hourly[time_key].insert(0, status)
        hourlies = {
            'title': self.title,
            'hourlies': utils.generate_hourly_summaries(hourly)
        }
        nav = sorted(set(item_headers))
        return hourlies, nav


class Timeline(object):
    def __init__(self, api, user, timeframe=-24):
        self.tz = pytz.timezone('America/Chicago')
        self.api = api
        self.user = user
        self.cutoff = datetime.datetime.now(tz=self.tz) + datetime.timedelta(hours=timeframe)
        self.start = datetime.datetime.now(tz=self.tz)
        self.statuses = []
        self._generate_timeline()

    def load(self, statuses):
        for s in statuses:
            utc = pytz.utc
            s.created_at = utc.localize(s.created_at).astimezone(self.tz)
            if s.created_at > self.cutoff:
                s.text = s.text.encode('ascii', 'ignore')
                s.origin = None
                if s.in_reply_to_status_id:
                    try:
                        #print 'Attempting to get ' + str(s.in_reply_to_status_id)
                        s.origin = self.api.get_status(s.in_reply_to_status_id)
                        s.origin.text = s.origin.text.encode('ascii', 'ignore')
                        user = s.origin.user
                        #print 'Origin user name is ' + user.screen_name
                        s.origin.author_name = user.screen_name
                    except TweepError as e:
                        print('Error while fetching origin for tweet {0}'.format(s.id))

                self.statuses.append(s)
                #print 'Appended ' + s.text + " | " + s.created_at.strftime(utils.DT_FORMAT)

    def get_earliest_status(self):
        earliest = None
        if self.statuses:
            earliest = self.statuses[0]
            for s in self.statuses:
                if s.created_at < earliest.created_at:
                    earliest = s
        return earliest

    def get_earliest_id(self):
        identifier = None
        earliest_status = self.get_earliest_status()
        if earliest_status:
            identifier = earliest_status.id
        return identifier

    @property
    def total(self):
        return len(self.statuses)

    def get_timeline_batch(self, max_id=None):
        if max_id is None:
            return self.api.user_timeline(self.user)
        else:
            return self.api.user_timeline(self.user, max_id=max_id)

    def _generate_timeline(self):
        now = datetime.datetime.now()
        #print 'Now ' + now.strftime(utils.DT_FORMAT)
        #print 'Start ' + self.start.strftime(utils.DT_FORMAT)
        #print 'Cutoff ' + self.cutoff.strftime(utils.DT_FORMAT)
        earliest_id = None
        tweets_available = True
        while tweets_available:
            #print 'Getting tweets with max id ' + str(earliest_id)
            next_tweets = self.get_timeline_batch(earliest_id)
            self.load(next_tweets)
            earliest_status = self.get_earliest_status()
            #print 'Earliest status ' + earliest_status.created_at.strftime('%B-%d-%Y-%I-%p')
            if earliest_status and earliest_status.created_at < self.cutoff:
                #print 'Exceeded cutoff'
                tweets_available = False
            else:
                new_earliest_id = self.get_earliest_id()
                #In case all available tweets are exhausted but cutoff not exceeded
                if earliest_id is None or new_earliest_id < earliest_id:
                    earliest_id = new_earliest_id
                    #print 'New earliest id ' + str(earliest_id)
                else:
                    #print "Exhausted available tweets"
                    tweets_available = False


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