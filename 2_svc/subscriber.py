#!/usr/bin/python

# python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber
# python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

import os
import time
import argparse
from google.cloud import pubsub

import requests
import json
import base64
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials
from google.auth import crypt
from google.oauth2.service_account import Credentials
import logging
from utils import AESCipher, HMACFunctions, RSACipher
import binascii

parser = argparse.ArgumentParser(description='Subscribe and verify Service Account based messages')
parser.add_argument('--mode',required=True, choices=['decrypt','verify'], help='mode must be decrypt or verify')
parser.add_argument('--service_account',required=True,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='subscriber projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')
args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

credentials = GoogleCredentials.get_application_default()
if credentials.create_scoped_required():
  credentials = credentials.create_scoped(scope)

http = httplib2.Http()
credentials.authorize(http)

project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
PUBSUB_TOPIC = args.pubsub_topic
PUBSUB_SUBSCRIPTION = args.pubsub_subscription

subscriber = pubsub.SubscriberClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
)
subscription_name = 'projects/{project_id}/subscriptions/{sub}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    sub=PUBSUB_SUBSCRIPTION,
)

#subscriber.create_subscription(name=subscription_name, topic=topic_name)

def callback(message):

  logging.info("********** Start PubsubMessage ")
  logging.info('Received message ID: {}'.format(message.message_id))
  logging.info('Received message publish_time: {}'.format(message.publish_time))

  if args.mode == "verify":
    key_id = message.attributes['key_id']
    service_account= message.attributes['service_account']
    signature = message.attributes['signature']

    logging.info("Attempting to verify message: " + message.data)
    logging.info("Verify message with signature: " + signature)
    logging.info("  Using service_account/key_id: " + service_account + " " + key_id )

    cert_url = 'https://www.googleapis.com/service_accounts/v1/metadata/x509/' + service_account
    r = requests.get(cert_url)
    pem = r.json().get(key_id)
    v = crypt.RSAVerifier.from_string(pem)

    if v.verify(message.data, base64.b64decode(signature)):
      logging.info("Message integrity verified")
      message.ack()
    else:
      logging.info("Unable to verify message")
      message.nack()
    message.ack()
    logging.info("********** End PubsubMessage ")

  if args.mode == "decrypt":
    message.ack()
    key_id = message.attributes['key_id']
    msg_service_account= message.attributes['service_account']

    logging.info("Attempting to decrypt message: " + message.data)
    logging.info("  Using service_account/key_id: " + msg_service_account + " " + key_id )

    credentials = Credentials.from_service_account_file(args.service_account)
    key_key_id = credentials._signer._key_id

    key_service_account_email = credentials.service_account_email
    if (msg_service_account != key_service_account_email):
        logging.info("Service Account specified in command line does not match message payload service account")
        logging.info(msg_service_account + " --- " + args.service_account)
        message.nack()
    else:
      private_key = credentials._signer._key
      rs = RSACipher(private_key = private_key)
      plaintext = rs.decrypt(message.data)
      logging.info("Decrypted Message payload: " +plaintext)
      message.ack()


    logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
