# Google Hangouts Chat - Errbot Backend

This is a backend for Google Hangouts Chat (https://chat.google.com) for Errbot(https://errbot.io).

It allows you to use errbot to create bots, but as always, it's a work in progress.

## Installation

```
git clone https://github.com/cloudflare/GHC-Errbot
```

and then

```
BACKEND = 'Google-Hangouts-Chat'
BOT_EXTRA_BACKEND_DIR = '/path/to/where/you/cloned/the/repo/'
```

to your config.py

## Authentication

1. Create a Google Pub/Sub topic in a GCE project

2. Create a Subscriber on that topic and grant your bot account Subscriber permissions

3. Generate a creds.json for your bot

4. Create an application with `errbot init`, and then create a `BOT_IDENTITY` block in your config.py with the following information:

```
BOT_IDENTITY = {
    'GOOGLE_CREDS_FILE': '/path/to/bot/creds.json',
    'GOOGLE_CLOUD_ENGINE_PROJECT': '<your project name>',
    'GOOGLE_CLOUD_ENGINE_PUBSUB_TOPIC': '<your pub/sub topic>',
    'GOOGLE_CLOUD_ENGINE_PUBSUB_SUBSCRIPTION': '<your pub/sub subscription name>',
}
```

5. Set BOT_PREFIX to the name of the bot, including the mention(`@`)

# Examples

## Attachments

This backend supports attachments in [message events][1]. To download a Google Chat upload attachment, we need to use the [GetAttachment API][2] and HTTP GET request with _Bearer authentication_. Since the backend is already authenticated, we opportunistically provide a ready-to-use _downloader_ object with the message context, so that errbot [plugins][3] can use it to directly download the attachments, no extra steps required.

Here's a code example on how to use the downloader helper in a errbot plugin:

```python
from io import BytesIO
from errbot import BotPlugin, botcmd

@botcmd(split_args_with=None)
def upload(self, msg, args):
    attachments = msg._extras.get('attachment', [])
    for attachment in attachments:
        if attachment['source'] == 'UPLOADED_CONTENT':
            url = f"""https://chat.googleapis.com/v1/media/{ attachment['attachmentDataRef']['resourceName'] }?alt=media"""
            downloader = msg._extras.get('downloader')
            content = downloader(url)
            if content != None:
                d = BytesIO()
                d.write(content)
                # jira.add_attachment(issue=issue, attachment=d, filename=attachment['contentName'])
```

# Acknowledgement
The code in `markdownconverter.py` is from https://github.com/dr-BEat/errbot-backend-hangoutschat. It is MIT licensed.

# License

Licensed under the BSD 3 License.

[1]: https://developers.google.com/chat/api/guides/message-formats/events#message
[2]: https://developers.google.com/chat/how-tos/get-attachment
[3]: https://errbot.readthedocs.io/en/latest/errbot.botplugin.html
