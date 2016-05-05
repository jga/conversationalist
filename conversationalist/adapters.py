import re
from datetime import datetime, timedelta
from operator import itemgetter
from dateutil.parser import parse
from .classes import Participation

PERIOD_DT_FORMAT = '%A, %B %d, %Y  %-I%p'


def initialize_hourly_summary(start, cutoff):
    """
    Generates a dict that contains statuses for each hour during
    a timeframe. The statuses are keyed to a timestamp string.

    At initialization, the list for each timestamp is empty.

    Args:
        start (datetime): The timeline's start.
        cutoff (datetime): When the timeline's status search ends.

    Returns:
        dict: Statuses keyed to timestamps arranged in hourly increments.
    """
    hourly_summary = {}
    start = start.replace(minute=0)
    active = cutoff
    while active < start:
        hourly_key = active
        hourly_key = hourly_key.replace(minute=0, second=0, microsecond=0)
        hourly_summary[hourly_key.isoformat()] = []
        active = active + timedelta(hours=1)
    return hourly_summary


def sort_statuses(statuses):
    return sorted(statuses, key=lambda s: s['created_at'])


def to_periods(hourly_summary):
    periods = []
    for iso_timestamp, statuses in hourly_summary.items():
        period_datetime = parse(iso_timestamp)
        unix_epoch = datetime(1970, 1, 1, tzinfo=period_datetime.tzinfo)
        seconds = (period_datetime - unix_epoch).total_seconds()
        subtitle = period_datetime.strftime(PERIOD_DT_FORMAT)
        if len(statuses) > 0:
            empty = False
            message = 'No updates.'
            hour_block = {
                'id': int(seconds),
                'empty': empty,
                'empty_message': message,
                'subtitle': subtitle,
                'statuses': sort_statuses(statuses)
            }
            periods.append(hour_block)
    periods = sorted(periods, key=itemgetter('id'))
    return periods


def find_topic_header(status, pattern, return_group=0):
    """
    Searches a status for the presence of a pattern, and returns matches


    Args:
        status(dict): A dictionary with information for a tweet. Expected to
          include a ``text`` key.
        pattern: A raw string with a regular expression pattern.
        return_group (int): The regex group that may be returned. Defaults to all groups.
    Returns:
        The requested return group for the match or ``None``.
    """
    text = status['text']
    topic_regex = re.compile(pattern, re.I)
    match = topic_regex.search(text)
    if match:
        return match.group(return_group)
    return None


def get_style_classes(style_words, status):
    """
    Searches for occurrence of key words in status text; the matches
    will be used by templates to apply those word matches as CSS styles.

    Args:
        style_words (list): The targeted search words.
        status (dict): Data for a tweet status.

    Returns:
        str: The matched classes or an empty string if no matches found.
    """
    style_classes = ''
    style_matches = []
    if style_words:
        for word in style_words:
            pattern = r'\b%s\b' % word
            regex = re.compile(pattern, re.I)
            match = regex.search(status['text'])
            if match:
                word = word.replace(' ', '-')
                style_matches.append(word)
    for m in set(style_matches):
        style_classes = '{0} {1}'.format(style_classes, m)
    return style_classes.strip()


def transform_with_topic_headers(conversation, pattern, return_goup):
    start, cutoff = conversation._get_timeline_interval()
    hourly_summary = initialize_hourly_summary(start, cutoff)
    timeline_data = conversation.timeline.get('data', {})
    topic_headers = []
    for identifier, status in timeline_data.items():
        if pattern:
            topic_header = find_topic_header(status, pattern, return_goup)
            if topic_header:
                status['topic_header'] = topic_header
                topic_headers.append(topic_header)
        created_with_no_minutes = parse(status['created_at']).replace(minute=0, second=0, microsecond=0)
        time_key = created_with_no_minutes.isoformat()
        if time_key in hourly_summary:
            # statuses not sorted by time
            hourly_summary[time_key].append(status)
        else:
            hourly_summary[time_key] = [status]
    nav = sorted(set(topic_headers))
    data = {
        'title': conversation.title,
        'periods': to_periods(hourly_summary),
        'topic_headers': nav
    }
    return data


def transform_with_participation_and_styles(conversation, style_words,
                                            header_pattern, return_group):
    """
    Iterates through conversation status dictionaries adding their data to
    the instances ``Participation`` property, handling content transformations,
    and inserting style classes.  This logic helps create more informative
    pages once the data is rendered.
    """
    start, cutoff = conversation._get_timeline_interval()
    hourly_summary = initialize_hourly_summary(start, cutoff)
    timeline_data = conversation.timeline.get('data', {})
    participation = Participation()
    topic_headers = []
    for identifier, status in timeline_data.items():
        participation.add_tweet(status['author'])
        if status['origin']:
            participation.add_tweet(status['origin']['author'])
        if header_pattern:
            topic_header = find_topic_header(status, header_pattern, return_group)
            if topic_header:
                status['topic_header'] = topic_header
                topic_headers.append(topic_header)
        if style_words:
            status['style_classes'] = get_style_classes(style_words, status)
        created_with_no_minutes = parse(status['created_at']).replace(minute=0, second=0, microsecond=0)
        time_key = created_with_no_minutes.isoformat()
        if time_key in hourly_summary:
            # statuses not sorted by time
            hourly_summary[time_key].append(status)
        else:
            hourly_summary[time_key] = [status]
    nav = sorted(set(topic_headers))
    data = {
        'title': conversation.title,
        'periods': to_periods(hourly_summary),
        'participation': participation,
        'nav': nav
    }
    return data


class ParticipationAdapter:
    style_words = None
    header_pattern = None
    return_group = 0

    def __init__(self, conversation):
        self.conversation = conversation

    def convert(self):
        return transform_with_participation_and_styles(self.conversation,
                                                       self.style_words,
                                                       self.header_pattern,
                                                       self.return_group)


class TopicHeaderAdapter:
    pattern = None
    return_group = 0

    def __init__(self, conversation):
        self.conversation = conversation

    def convert(self):
        return transform_with_topic_headers(self.conversation, self.pattern, self.return_group)


class TextReplaceAdapter:
    conversions = None

    def __init__(self, conversation):
        self.conversation = conversation

    def convert(self):
        start, cutoff = self.conversation._get_timeline_interval()
        hourly_summary = initialize_hourly_summary(start, cutoff)
        timeline_data = self.conversation.timeline.get('data', {})
        for identifier, status in timeline_data.items():
            if self.conversions:
                for original, replacement in self.conversions.items():
                    status['text'].replace(original, replacement)
            created_with_no_minutes = parse(status['created_at']).replace(minute=0, second=0, microsecond=0)
            time_key = created_with_no_minutes.isoformat()
            if time_key in hourly_summary:
                # statuses not sorted by time
                hourly_summary[time_key].append(status)
            else:
                hourly_summary[time_key] = [status]
        data = {
            'title': self.conversation.title,
            'periods': to_periods(hourly_summary),
        }
        return data
