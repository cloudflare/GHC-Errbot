import json
import httplib2
import logging
from errbot.backends.base import Message
from errbot.backends.base import Person
from errbot.backends.base import Room
from errbot.errBot import ErrBot
from google.cloud import pubsub
from oauth2client.service_account import ServiceAccountCredentials

log = logging.getLogger('errbot.backends.hangoutschat')

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
        self.http_client = self._get_authenticated_http_client('https://www.googleapis.com/auth/chat.bot')
        self.bot_identifier = None

    def _get_google_credentials(self, scope):
        return ServiceAccountCredentials.from_json_keyfile_name(self.creds_file, scopes=[scope])

    def _subscribe_to_pubsub_topic(self, project, topic_name, subscription_name):
        subscriber = pubsub.SubscriberClient()
        subscription_name = 'projects/{}/subscriptions/{}'.format(project, subscription_name)
        log.info("Subscribed to {}".format(subscription_name))
        return subscriber.subscribe(subscription_name)

    def _get_authenticated_http_client(self, scope):
        return self._get_google_credentials(scope).authorize(httplib2.Http())

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

    def respond_to(self, incoming_message, outgoing_message):
        outgoing_message['space_id'] = incoming_message.extras['space_id']
        outgoing_message['thread_id'] = incoming_message.extras['thread_id']

        self.send_message(outgoing_message)

    def serve_forever(self):
        subscription = self._subscribe_to_pubsub_topic(self.gce_project, self.gce_topic, self.gce_subscription)
        self.connect_callback()

        future = subscription.open(self._handle_message)
        try:
            future.result()
        except Exception:
            log.info("Exiting")
            raise
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
        return None

    def rooms(self):
        return None
