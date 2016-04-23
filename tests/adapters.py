from conversationalist.adapters import ParticipationAdapter, TextReplaceAdapter, TopicHeaderAdapter


class ConvoParticipationAdapter(ParticipationAdapter):
    style_words = ['mock', 'status', 'test']
    header_pattern = r'\d'


class ConvoTopicHeaderAdapter(TopicHeaderAdapter):
    pattern = r'\d'
    return_group = 0


class ConvoTextAdapter(TextReplaceAdapter):
    conversions = {'status': 'STATUS'}
