import base64
import json
import re
import os
import time
from datetime import datetime, timedelta
from operator import itemgetter
from jinja2 import Environment, FileSystemLoader
import tweepy
import pytz
from dateutil.parser import parse
from .classes import Timeline, TimelineEncoder, Conversation


DT_FORMAT = '%B-%d-%Y-%I-%p'
VIEW_DT_FORMAT = '%B %d, %Y %I:%M %p'
BLOCK_DT_FORMAT = '%A, %B %d, %Y  %-I%p'
#ISO_WITH_OFFSET_DT_FORMAT = ''

template_path = ''.join((os.path.dirname(os.path.abspath(__file__)), '/templates',))
env = Environment(loader=FileSystemLoader(template_path))


def format_datetime(value, pattern=VIEW_DT_FORMAT):
    return parse(value).strftime(pattern)


def to_background_url(value):
    background_ready = ''.join(("url('", value, "')",))
    return background_ready


def urlize_item_link(value):
    urlized = ''.join(('item-', str(value)))
    return urlized.lower()


env.filters['datetime'] = format_datetime
env.filters['urlize_item_link'] = urlize_item_link
env.filters['to_background_url'] = to_background_url


def write_story(path, title, summaries, participants, navs, template):
    """

    Args:
        path:
        title:
        summaries:
        participants:
        navs:
        template: For example, 'tick_tock_body.html'
    """
    template = env.get_template(template)
    output = template.render(title=title, summaries=summaries, participants=participants, nav_links=navs)
    with open(path, "wb") as fh:
        fh.write(output)


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


def to_json(api, name, hours, file_path):
    """

    Args:
        api:
        name:
        hours:
        file_path: For example, '/Users/me/conversationalist-project/timeline.json'

    Returns:

    """
    timeline = Timeline(api, name, (hours * -1))
    with open(file_path, 'w') as outfile:
        json.dump(timeline, outfile, cls=TimelineEncoder, indent=2)


def get_json_file_path(path, tz_name, file_name='conversationalist_data-'):
    timezone = pytz.timezone(tz_name)
    date_label = datetime.datetime.now(tz=timezone).strftime('%m%d%Y')
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
    date_label = datetime.datetime.now(tz=timezone).strftime('%m%d%Y-%H%M')
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
    date_label = datetime.datetime.now(tz=timezone).strftime('%m-%d-%Y %H:%M')
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


def to_conversation(twitter_username, hours, settings):
    print('Starting conversationalist. Getting tweets...')
    tz_name = settings.get('tz_name', 'UTC')
    auth = tweepy.OAuthHandler(settings['consumer_key'], settings['consumer_secret'])
    auth.set_access_token(settings.access_token, settings.access_token_secret)
    api = tweepy.API(auth)
    t = Timeline(api, twitter_username, (hours * -1))
    json_file = get_json_file_path(settings['data_path'], tz_name)
    print('...writing json...')
    with open(json_file, 'w') as outfile:
        json.dump(t, outfile, cls=TimelineEncoder, indent=1)
    with open(json_file) as infile:
        timeline = json.load(infile)
    start = parse(timeline['start'])
    cutoff = parse(timeline['cutoff'])
    set_pre_exchange_content = settings.get('pre_exchange')
    conversation = Conversation(timeline, start, cutoff, style_words=settings['style_words'],
                                pre_exchange=set_pre_exchange_content)
    output_file_path, output_file_name = get_output_file_path(settings['output_path'], tz_name)
    print('...writing content...')
    write_story(output_file_path, conversation.data['title'], conversation.data['hourlies'],
                    conversation.participation.get_ranked_profiles(), conversation.nav)
    email = settings.get('email', None)
    if email:
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
        if send_email:
            send_email(payload)
    print('...conversationalist done.')


def print_rate_limit_info(settings):
    auth = tweepy.OAuthHandler(settings.consumer_key, settings.consumer_secret)
    auth.set_access_token(settings.access_token, settings.access_token_secret)
    api = tweepy.API(auth)
    status = api.rate_limit_status()
    for (k, v) in status['resources'].items():
        if k == 'statuses':
            for (k2, v2) in v.items():
                print ('KEY: ', k2, ' VALUE: ', v2)