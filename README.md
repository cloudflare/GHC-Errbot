# Google Hangouts Chat - Errbot Backend

This is a backend for Google Hangouts Chat (https://chat.google.com) for Errbot(https://errbot.io).

It allows you to use errbot to create bots, but as always, it's a work in progress.

## Installation

```
git clone https://github.com/sinkingpoint/GHC-Errbot
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
    '@_NAME': '<The @Name of your bot>'
}
```
