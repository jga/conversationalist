from .classes import Conversation, Timeline


def make_story(settings):
    """
    Creates web page and data from a twitter account's stream.

    Function extracts needed settings. Then, after, btaining twitter api instance,
    a ``Timeline`` object is instantiated. It's data is encoded into a JSON file. This
    allows portability for the timeline instance.

    The timeline's JSON is then consumed for the creation of a ``Conversation``
    instance.

    The ``Conversation`` instance is passed along with a template file path location
    and a file path for output to a ``write`` function.  The ``write`` function
    takes care of usering conversation data to produce the HTML page that represents
    the "story".

    Finally, if an email handler was included in the settings, then that email
    handler is called; it is passed the location of the just-produced HTML "story"
    page, but it may choose to not use it/attach it.

    Args:
        settings (dict): Configuration settings.

    Returns:
        str: The file path location of the generated web page.
    """
    print('Starting conversationalist. Getting tweets...')
    adapter = settings.get('adapter')
    api = settings['api']
    timeline_json_output_file = settings['timeline_out']
    timeframe_hours = int(settings.get('timeframe', 24))
    title = settings.get('title', 'Story')
    twitter_username = settings['username']
    write = settings['write']
    timeline = Timeline(api, twitter_username, (timeframe_hours * -1))
    print("...saving Timeline as JSON file...")
    timeline.to_json(timeline_json_output_file)
    conversation = Conversation(title=title, adapter=adapter)
    conversation.load(timeline_json_output_file)
    print("...writing story file...")
    page_location = write(conversation, settings['story_out'])
    print('...conversationalist done.')
    return page_location


def print_rate_limit_info(api):
    """
    Prints rate limit information for passed API instance.

    Args:
        api: A tweepy API instance.
    """
    info = api.rate_limit_status()
    for (key, val) in info['resources'].items():
        if key == 'statuses':
            for (status_key, status_value) in val.items():
                print ('KEY: ', status_key, ' VALUE: ', status_value)