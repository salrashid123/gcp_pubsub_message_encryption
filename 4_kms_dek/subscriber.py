#!/usr/bin/python

# python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1

# python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1

import os
import time
from google.cloud import pubsub
import argparse
import json
import base64
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

from utils import AESCipher, HMACFunctions, RSACipher

from expiringdict import ExpiringDict

import logging


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--mode',required=True, choices=['decrypt','verify'], help='mode must be decrypt or verify')
parser.add_argument('--service_account',required=True,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher service_acount credentials file')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')
parser.add_argument('--kms_location_id',required=True, help='KMS kms_location_id (eg, us-central1)')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS kms_key_ring_id (eg, mykeyring)')
parser.add_argument('--kms_key_id',required=True, help='KMS kms_key_id (eg, key1)')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')
args = parser.parse_args()

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

credentials = GoogleCredentials.get_application_default()
if credentials.create_scoped_required():
  credentials = credentials.create_scoped(scope)

http = httplib2.Http()
credentials.authorize(http)

project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
tenantID = args.tenantID

PUBSUB_TOPIC = args.pubsub_topic
PUBSUB_SUBSCRIPTION = args.pubsub_subscription

kms_client = build('cloudkms', 'v1')
crypto_keys = kms_client.projects().locations().keyRings().cryptoKeys()

subscriber = pubsub.SubscriberClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
)
subscription_name = 'projects/{project_id}/subscriptions/{sub}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    sub=PUBSUB_SUBSCRIPTION,
)

cache = ExpiringDict(max_len=100, max_age_seconds=20)

#subscriber.create_subscription(name=subscription_name, topic=topic_name)

logging.info(">>>>>>>>>>> Start <<<<<<<<<<<")


def callback(message):

  if (args.mode == "verify"):

      logging.info("********** Start PubsubMessage ")
      logging.info('Received message ID: {}'.format(message.message_id))
      logging.info('Received message publish_time: {}'.format(message.publish_time))
      logging.info('Received message attributes["kms_key"]: {}'.format(message.attributes['kms_key']))
      logging.info('Received message attributes["sign_key_wrapped"]: {}'.format(message.attributes['sign_key_wrapped']))
      logging.info('Received message attributes["signature"]: {}'.format(message.attributes['signature']))
      signature = message.attributes['signature']
      name = message.attributes['kms_key']
      sign_key_wrapped = message.attributes['sign_key_wrapped']

      logging.info("Starting KMS decryption API call")
      request = crypto_keys.decrypt(
            name=name,
            body={
             'ciphertext': (sign_key_wrapped).decode('utf-8'),
             'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')
            })
      response = request.execute()
      unwrapped_key =  base64.b64decode(response['plaintext'])
      logging.info("End KMS decryption API call")
      logging.info("Verify message: " + message.data)
      logging.info('  With HMAC: ' + signature)
      logging.info('  With unwrapped key: ' + base64.b64encode(unwrapped_key))
      hh = HMACFunctions(base64.b64encode(unwrapped_key))
      sig = hh.hash(message.data)

      if (hh.verify(base64.b64decode(sig))):
        logging.info("Message authenticity verified")
        message.ack()
      else:
        logging.error("Unable to verify message")
        message.nack()
      logging.info("********** End PubsubMessage ")


  if (args.mode == "decrypt"):
      logging.info("********** Start PubsubMessage ")
      logging.info('Received message ID: {}'.format(message.message_id))
      logging.info('Received message publish_time: {}'.format(message.publish_time))
      logging.info('Received message attributes["kms_key"]: {}'.format(message.attributes['kms_key']))
      logging.info('Received message attributes["dek_wrapped"]: {}'.format(message.attributes['dek_wrapped']))
      dek_wrapped = message.attributes['dek_wrapped']
      name = message.attributes['kms_key']

      logging.info("Starting KMS decryption API call")
      request = crypto_keys.decrypt(
            name=name,
            body={
             'ciphertext': (dek_wrapped).decode('utf-8'),
             'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')
            })
      response = request.execute()
      dek=  base64.b64decode(response['plaintext'])
      logging.info("End KMS decryption API call")
      logging.info('Received aes_encryption_key : {}'.format( base64.b64encode(dek)))

      logging.info("Starting AES decryption")
      ac = AESCipher(dek)
      decrypted_data = ac.decrypt(message.data)
      logging.info("End AES decryption")
      logging.info('Decrypted data ' + decrypted_data)
      message.ack()
      logging.info("ACK message")
      logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
