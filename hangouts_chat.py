import json
import httplib2
import logging
from typing import Iterable, Optional
from errbot.backends.base import Message
from errbot.backends.base import Person
from errbot.backends.base import Room, RoomError
from errbot.errBot import ErrBot
from google.cloud import pubsub
from oauth2client.service_account import ServiceAccountCredentials
from cachetools import LRUCache


from markdownconverter import hangoutschat_markdown_converter

log = logging.getLogger('errbot.backends.hangoutschat')

def removeprefix(source: str, prefix: str):
    if source.startswith(prefix):
        return source[len(prefix):]
    return source

class RoomsNotSupportedError(RoomError):
    def __init__(self, message=None):
        if message is None:
            message = (
                "Most Room operations are not supported in Google Hangouts Chat."
                "While Rooms are a _concept_, the API is minimal and does not "
                "expose this functionality to bots"
            )
        super().__init__(message)


class GoogleHangoutsChatAPI:
    """
    Represents the Google Hangouts REST API
    See: https://developers.google.com/hangouts/chat/reference/rest/
    """
    base_url = 'https://chat.googleapis.com/v1'
    # Number of results to fetch at a time. Default is 100, Max is 1000
    page_size = 500

    # Maximum length of any single message sent to google chat
    max_message_length = 4096

    def __init__(self, creds_file: str, scope: str = 'https://www.googleapis.com/auth/chat.bot'):
        self.creds_file = creds_file
        self.scope = scope

    @property
    def credentials(self):
        return ServiceAccountCredentials.from_json_keyfile_name(self.creds_file,
                                                                scopes=[self.scope])

    @property
    def client(self):
        return self.credentials.authorize(httplib2.Http())

    def _request(self, uri: str, query_string: str = None, **kwargs) -> Optional[dict]:
        request_args = {
            'method': 'GET',
            'headers': {'Content-Type': 'application/json; charset=UTF-8', }}
        request_args.update(kwargs)
        url = '{}/{}'.format(self.base_url, uri)
        if query_string:
            url += '?{}'.format(query_string)
        result, content = self.client.request(
            uri=url,
            **request_args
        )
        if result['status'] == '200':
            content_json = json.loads(content.decode('utf-8'))
            return content_json
        else:
            log.error('status: {}, content: {}'.format(result['status'], content))

    def _list(self, resource: str, return_attr: str, next_page_token: str = '') -> Iterable[dict]:
        """
        Gets a list of resources.

        Args:
            resource: name of resource to list
            return_attr: name of attribute in the root of the response to get
                        resources from
            next_page_token: the nextPageToken returned by the previous call

        Yields:
            dict: the next found resource
        """

        query_string = 'pageSize={}'.format(self.page_size)
        if next_page_token:
            query_string += '&pageToken={}'.format(next_page_token)
        data = self._request(resource, query_string=query_string)
        if data:
            for itm in data[return_attr]:
                yield itm
            next_page_token = data.get('nextPageToken')
            if next_page_token != '':
                yield from self._list(resource, return_attr, next_page_token)

    def get_spaces(self) -> Iterable[dict]:
        return self._list('spaces', 'spaces')

    def get_space(self, name: str) -> Optional[dict]:
        return self._request('spaces/{}'.format(removeprefix(name, 'spaces/')))

    def get_members(self, space_name: str) -> Iterable[dict]:
        return self._list('spaces/{}/members'.format(removeprefix(space_name, 'spaces/')), 'memberships')

    def get_member(self, space_name: str, name: str) -> Optional[dict]:
        return self._request('spaces/{}/members/{}'.format(removeprefix(space_name, 'spaces/'), name))

    def create_message(self, space_name: str, body: dict, thread_key: str = None) -> Optional[dict]:
        url = 'spaces/{}/messages'.format(removeprefix(space_name, 'spaces/'))
        if thread_key is None:
            return self._request(url, body=json.dumps(body), method='POST')
        else:
            return self._request(url, body=json.dumps(body), method='POST',
                                 query_string='threadKey={}'.format(thread_key))


class HangoutsChatRoom(Room):
    """
    Represents a 'Space' in Google-Hangouts-Chat terminology
    """
    def __init__(self, space_id, chat_api):
        super().__init__()
        self.space_id = space_id
        self.chat_api = chat_api
        self._load()

    def _load(self):
        space = self.chat_api.get_space(self.space_id)
        self.does_exist = bool(space)
        self.display_name = space['displayName'] if self.does_exist else ''

    def join(self, username=None, password=None):
        raise RoomsNotSupportedError()

    def create(self):
        raise RoomsNotSupportedError()

    def leave(self, reason=None):
        raise RoomsNotSupportedError()

    def destroy(self):
        raise RoomsNotSupportedError()

    @property
    def joined(self):
        raise RoomsNotSupportedError()

    @property
    def exists(self):
        raise RoomsNotSupportedError()

    @property
    def topic(self):
        raise RoomsNotSupportedError()

    @property
    def occupants(self):
        memberships = self.chat_api.get_members(self.space_id)
        occupants = []
        for membership in memberships:
            name = '{} ({} / {})'.format(membership['member']['displayName'],
                                         membership['member']['name'],
                                         membership['state'])
            if membership['member']['type'] == 'BOT':
                name += ' **BOT**'
            occupants.append(HangoutsChatUser(name,
                                              membership['member']['displayName'],
                                              None,
                                              membership['member']['type']))

        return occupants

    def invite(self, *args):
        raise RoomsNotSupportedError()


class HangoutsChatUser(Person):
    def __init__(self, name, display_name, email, user_type):
        super().__init__()
        self.name = name
        self.display_name = display_name
        self.email = email
        self.user_type = user_type

    @property
    def person(self):
        return self.name

    @property
    def fullname(self):
        return self.display_name

    @property
    def client(self):
        return 'Hangouts Chat'

    @property
    def nick(self):
        return self.display_name

    @property
    def aclattr(self):
        return self.email


class GoogleHangoutsChatBackend(ErrBot):
    def __init__(self, config):
        super().__init__(config)
        identity = config.BOT_IDENTITY
        self.at_name = config.BOT_PREFIX
        self.creds_file = identity['GOOGLE_CREDS_FILE']
        self.gce_project = identity['GOOGLE_CLOUD_ENGINE_PROJECT']
        self.gce_topic = identity['GOOGLE_CLOUD_ENGINE_PUBSUB_TOPIC']
        self.gce_subscription = identity['GOOGLE_CLOUD_ENGINE_PUBSUB_SUBSCRIPTION']
        self.chat_api = GoogleHangoutsChatAPI(self.creds_file)
        self.bot_identifier = HangoutsChatUser(None, self.at_name, None, None)
        self.message_cache = LRUCache(1024)
        self.md = hangoutschat_markdown_converter()

    def _subscribe_to_pubsub_topic(self, project, topic_name, subscription_name, callback):
        subscriber = pubsub.SubscriberClient()
        subscription_name = 'projects/{}/subscriptions/{}'.format(project, subscription_name)
        log.info("Subscribed to {}".format(subscription_name))
        return subscriber.subscribe(subscription_name, callback=callback)

    def _handle_message(self, message):
        try:
            data = json.loads(message.data.decode('utf-8'))
        except Exception:
            log.warning('Received malformed message: {}'.format(message.data))
            message.ack()
            return

        if not data.get('message') or not data.get('message', {}).get('text'):
            message.ack()
            return
        sender_blob = data['message']['sender']
        sender = HangoutsChatUser(sender_blob['name'],
                                  sender_blob['displayName'],
                                  sender_blob['email'],
                                  sender_blob['type'])
        message_body = data['message']['text']
        message.ack()
        # message.ack() may fail silently, so we should ensure our messages are somewhat idempotent
        time = data.get('eventTime', 0)
        if time == 0:
            log.warning('Received 0 eventTime from message')

        send_name = sender_blob.get('name', '')
        thread_name = data.get('message', {}).get('thread', {}).get('name', '')
        body_length = len(message_body)
        message_id = "{}{}{}{}".format(time, send_name, thread_name, body_length)
        cached = self.message_cache.get(message_id)
        if cached is not None:
            return
        self.message_cache[message_id] = True

        context = {
            'argument_text': data['message'].get('argumentText',''),
            'slash_command_id': data['message'].get('slashCommand',{}).get('commandId',None),
            'space_id': data['space']['name'],
            'thread_id': data['message']['thread']['name']
        }
        msg = Message(body=message_body.strip(), frm=sender, extras=context)
        is_dm = data['message']['space']['type'] == 'DM'
        if is_dm:
            msg.to = self.bot_identifier
        self.callback_message(msg)


    def _split_message(self, text, maximum_message_length=GoogleHangoutsChatAPI.max_message_length):
        '''
        Splits a given string up into multiple strings all of length less than some maximum size

        Edge Case: We don't handle the case where one line is big enough for a whole message
        '''
        lines = text.split('\n')
        messages = []
        current_message = ''
        for line in lines:
            if len(current_message) + len(line) + 1 > maximum_message_length:
                messages.append(current_message)
                current_message = line + '\n'
            else:
                current_message += line + '\n'

        messages.append(current_message)
        return messages


    def send_message(self, message):
        super(GoogleHangoutsChatBackend, self).send_message(message)
        log.info("Sending {}".format(message.body))
        space_id = message.extras.get('space_id', None)
        convert_markdown = message.extras.get('markdown', True)
        if not space_id:
            log.info(message.body)
            return
        thread_id = message.extras.get('thread_id', None)
        thread_key = message.extras.get('thread_key', None)
        mentions = message.extras.get('mentions', None)
        text = message.body
        if convert_markdown:
            text = self.md.convert(message.body)
        sub_messages = self._split_message(text)
        log.info("Split message into {} parts".format(len(sub_messages)))
        for message in sub_messages:
            message_payload = {
                'text': message
            }
            if mentions:
                message_payload['annotations'] = []
                for mention in mentions:
                    message_payload['annotations'].append(
                        {
                        "type":"USER_MENTION",
                        "startIndex":mention['start'],
                        "length":mention['length'],
                        "userMention": {
                            "user": {
                                "name": mention['user_id'],
                                "displayName":mention['display_name'],
                                "type":"HUMAN"
                            },
                            "type":"ADD"
                            }
                        }
                    )
            if thread_id:
                message_payload['thread'] = {'name': thread_id}

            self.chat_api.create_message(space_id, message_payload, thread_key)

    def send_card(self, cards, space_id, thread_id=None):
        log.info("Sending card")
        message_payload = {
            'cards': cards
        }
        if thread_id:
            message_payload['thread'] = {'name': thread_id}

        self.chat_api.create_message(space_id, message_payload)

    def serve_forever(self):
        subscription = self._subscribe_to_pubsub_topic(self.gce_project,
                                                       self.gce_topic,
                                                       self.gce_subscription,
                                                       self._handle_message)
        self.connect_callback()

        try:
            import time
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            log.info("Exiting")
        finally:
            self.disconnect_callback()
            self.shutdown()

    def build_identifier(self, strrep):
        return HangoutsChatUser(None, strrep, None, None)

    def build_reply(self, msg, text=None, private=False, threaded=False):
        response = Message(body=text, frm=msg.to, to=msg.frm, extras=msg.extras)
        return response

    def change_presence(self, status='online', message=''):
        return None

    @property
    def mode(self):
        return 'Google_Hangouts_Chat'

    def query_room(self, room):
        return HangoutsChatRoom(room, self.chat_api)

    def rooms(self):
        spaces = self.chat_api.get_spaces()
        rooms = ['{} ({})'.format(space['displayName'], space['name'])
                 for space in list(spaces) if space['type'] == 'ROOM']

        return rooms
