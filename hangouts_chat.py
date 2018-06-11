import json
import httplib2
import logging
from errbot.backends.base import Message
from errbot.backends.base import Person
from errbot.backends.base import Room, RoomError
from errbot.errBot import ErrBot
from google.cloud import pubsub
from oauth2client.service_account import ServiceAccountCredentials

log = logging.getLogger('errbot.backends.hangoutschat')

def _get_authenticated_http_client(creds_file, scope='https://www.googleapis.com/auth/chat.bot'):
    return _get_google_credentials(creds_file, scope).authorize(httplib2.Http())

def _get_google_credentials(creds_file, scope):
    return ServiceAccountCredentials.from_json_keyfile_name(creds_file, scopes=[scope])

class RoomsNotSupportedError(RoomError):
    def __init__(self, message=None):
        if message is None:
            message = (
                "Room Operations are not supported in Google Hangouts Chat."
                "While Rooms are a _concept_, the API is minimal and does not "
                "expose this functionality to bots"
            )
        super().__init__(message)

class HangoutsChatRoom(Room):
    """
    Represents a 'Space' in Google-Hangouts-Chat terminology
    """
    def __init__(self, space_id, google_creds_file):
        super().__init__()
        self.space_id = space_id
        self.creds_file = google_creds_file
        self._load()

    def _load(self):
        http_client = _get_authenticated_http_client(self.creds_file)

        url = 'https://chat.googleapis.com/v1/spaces/{}'.format(self.space_id)
        response, content = http_client.request(uri=url, method='GET')
        if response['status'] == '200':
            content_json = json.loads(content.decode('utf-8'))
            self.display_name = content_json['displayName']
            self.does_exist = True
        else:
            self.does_exist = False
            self.display_name = ''

    def join(self, username = None, password = None):
        raise RoomsNotSupportedError()

    def create(self):
        raise RoomsNotSupportedError()

    def leave(self, reason = None):
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
        raise RoomsNotSupportedError()

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
        self.at_name = identity['@_NAME']
        self.creds_file = identity['GOOGLE_CREDS_FILE']
        self.gce_project = identity['GOOGLE_CLOUD_ENGINE_PROJECT']
        self.gce_topic = identity['GOOGLE_CLOUD_ENGINE_PUBSUB_TOPIC']
        self.gce_subscription = identity['GOOGLE_CLOUD_ENGINE_PUBSUB_SUBSCRIPTION']
        self.http_client = _get_authenticated_http_client(self.creds_file)
        self.bot_identifier = None

    def _subscribe_to_pubsub_topic(self, project, topic_name, subscription_name, callback):
        subscriber = pubsub.SubscriberClient()
        subscription_name = 'projects/{}/subscriptions/{}'.format(project, subscription_name)
        log.info("Subscribed to {}".format(subscription_name))
        return subscriber.subscribe(subscription_name, callback=callback)

    def _handle_message(self, message):
        data = json.loads(message.data)
        sender_blob = data['message']['sender']
        sender = HangoutsChatUser(sender_blob['name'], 
                                  sender_blob['displayName'], 
                                  sender_blob['email'],
                                  sender_blob['type'])
        message_body = data['message']['text']
        # If the message starts with @bot, trim that out before we send it off for processing
        if message_body.startswith(self.at_name):
            message_body = message_body[len(self.at_name):]
        message.ack()
        context = {
            'space_id': data['space']['name'],
            'thread_id': data['message']['thread']['name']
        }
        self.callback_message(Message(body=message_body.strip(), frm=sender, extras=context))

    def send_message(self, message):
        super(GoogleHangoutsChatBackend, self).send_message(message)
        log.info("Sending {}".format(message.body))
        space_id = message.extras.get('space_id', None)
        if not space_id:
            log.info(message.body)
            return
        thread_id = message.extras.get('thread_id', None)
        message_payload = {
            'text': message.body
        }

        if thread_id:
            message_payload['thread'] = {'name': thread_id }

        url = 'https://chat.googleapis.com/v1/{}/messages'.format(space_id)
        response, content = self.http_client.request(uri=url, method='POST',
                                                    headers={'Content-Type': 'application/json; charset=UTF-8'},
                                                    body=json.dumps(message_payload))

    def serve_forever(self):
        subscription = self._subscribe_to_pubsub_topic(self.gce_project, self.gce_topic, self.gce_subscription, self._handle_message)
        self.connect_callback()

        try:
            import time
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            log.info("Exiting")
        finally:
            subscription.close()
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
        return HangoutsChatRoom(room, self.creds_file)

    def rooms(self):
        return None
