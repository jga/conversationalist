import base64
import collections
import json
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import tweepy
import pytz
from dateutil.parser import parse
from .classes import Conversation, Timeline, TimelineEncoder


template_path = ''.join((os.path.dirname(os.path.abspath(__file__)), '/templates',))
template_env = Environment(loader=FileSystemLoader(template_path))


def format_datetime(value, pattern='%B %d, %Y %I:%M %p'):
    return parse(value).strftime(pattern)


def to_background_url(value):
    background_ready = ''.join(("url('", value, "')",))
    return background_ready


def urlize_item_link(value):
    urlized = ''.join(('item-', str(value)))
    return urlized.lower()


template_env.filters['datetime'] = format_datetime
template_env.filters['urlize_item_link'] = urlize_item_link
template_env.filters['to_background_url'] = to_background_url


def write_story(path, conversation, template):
    """

    Args:
        path:
        conversation: A :class:`~.classes.Conversation` instance.
        template: For example, 'tick_tock_body.html'
    """
    title = conversation.data['title'],
    summaries = conversation.data['hourlies'],
    participants = conversation.participation.get_ranked_profiles(),
    navs = conversation.nav,
    template = template_env.get_template(template)
    output = template.render(title=title, summaries=summaries,
                             participants=participants, nav_links=navs)
    with open(path, "wb") as fh:
        fh.write(output)


def get_json_file_path(path, tz_name, file_name='conversationalist_data-'):
    timezone = pytz.timezone(tz_name)
    date_label = datetime.now(tz=timezone).strftime('%m%d%Y')
    return ''.join((path, file_name, date_label,'.json'))


def get_output_file_path(path, tz_name, file_name='conversationalist-'):
    """

    Args:
        path:
        tz_name: Such as 'America/Chicago'.
        file_name: For example, 'ticktock-'.

    Returns:

    """
    timezone = pytz.timezone(tz_name)
    date_label = datetime.now(tz=timezone).strftime('%m%d%Y-%H%M')
    output_file_name = ''.join((file_name, date_label,'.txt',))
    return ''.join((path, output_file_name)), output_file_name


def get_email_subject(subject, tz_name):
    """

    Args:
        subject: For example, 'Tick Tock File - '.
        tz_name: Such as 'America/Chicago'.

    Returns:

    """
    timezone = pytz.timezone(tz_name)
    date_label = datetime.now(tz=timezone).strftime('%m-%d-%Y %H:%M')
    return ''.join((subject, date_label,))


def is_valid_payload(payload):
    keys = ['html', 'subject', 'text', 'to']
    for k in keys:
        if not k in payload:
            return False
    return True


def with_encoded(attachment_path, attachment_name):
    encoded_file = base64.b64encode(open(attachment_path, 'r').read())
    attachment = {
        'name': attachment_name,
        'content': encoded_file,
        'type': 'text/plain'
    }
    return attachment


def json_to_conversation(json_file, settings):
    with open(json_file) as infile:
        timeline_json = json.load(infile)
    start = parse(timeline_json['start'])
    cutoff = parse(timeline_json['cutoff'])
    set_pre_exchange_content = settings.get('pre_exchange')
    conversation = Conversation(timeline_json,
                                start,
                                cutoff,
                                style_words=settings['style_words'],
                                pre_exchange=set_pre_exchange_content)
    return conversation


def timeline_to_json(timeline, data_path, tz_name='UTC'):
    json_file = get_json_file_path(data_path, tz_name)
    print('...writing json...')
    with open(json_file, 'w') as outfile:
        json.dump(timeline, outfile, cls=TimelineEncoder, indent=1)
    return json_file


def send_conversation_page(email, output_file_path, output_file_name,
                            settings, tz_name):
    name = settings.get('name', email)
    subject = get_email_subject(settings['email_subject'], tz_name)
    project_name = settings.get('project_name', 'Tweet story')
    payload = {
        'subject': subject,
        'html': '<p>{0} file attached.</p>'.format(project_name),
        'text': '{0} file attached.'.format(project_name),
        'to': [{'email': email, 'name': name, 'type': 'to'}],
        'attachment_path': output_file_path,
        'attachment_name': output_file_name
    }
    print('...sending email to: {0}'.format(email))
    send_email = settings.get('send_email', None)
    if isinstance(send_email, collections.Callable):
        send_email(payload)


def go(twitter_username, hours, settings):
    """
    Creates web page and data from a twitter account's stream.

    After obtaining twitter api instance, a ``Timeline`` object
    is instantiated.

    Args:
        twitter_username (str): The targeted twitter account.
        hours (int): How far back the stream will be explored.
        settings (dict): Configuration settings.
    """
    print('Starting conversationalist. Getting tweets...')
    tz_name = settings.get('tz_name', 'UTC')
    auth = tweepy.OAuthHandler(settings['consumer_key'], settings['consumer_secret'])
    auth.set_access_token(settings['access_token'], settings['access_token_secret'])
    api = tweepy.API(auth)
    timeline = Timeline(api, twitter_username, (hours * -1))
    json_file = timeline_to_json(timeline, settings['data_path'], tz_name)
    conversation = json_to_conversation(json_file, settings)
    output_file_path, output_file_name = get_output_file_path(settings['output_path'], tz_name)
    print('...writing content...')
    write_story(output_file_path,
                conversation,
                settings['template'])
    email = settings.get('email', None)
    if email:
        send_conversation_page(email,
                           output_file_path,
                           output_file_name,
                           settings,
                           tz_name)
    print('...conversationalist done.')


def print_rate_limit_info(settings):
    auth = tweepy.OAuthHandler(settings['consumer_key'], settings['consumer_secret'])
    auth.set_access_token(settings['access_token'], settings['access_token_secret'])
    api = tweepy.API(auth)
    status = api.rate_limit_status()
    for (k, v) in status['resources'].items():
        if k == 'statuses':
            for (k2, v2) in v.items():
                print ('KEY: ', k2, ' VALUE: ', v2)