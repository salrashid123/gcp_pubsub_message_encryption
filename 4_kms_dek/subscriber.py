#!/usr/bin/python

import os
import time
from google.cloud import pubsub
from google.cloud import kms
import argparse
import simplejson as json
import base64
import httplib2

from utils import AESCipher, HMACFunctions, RSACipher

from expiringdict import ExpiringDict

import logging


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--mode',required=True, choices=['decrypt','verify'], help='mode must be decrypt or verify')
parser.add_argument('--service_account',required=False,help='publisher service_acount credentials file')
parser.add_argument('--pubsub_project_id',required=True, help='subscriber PubSub project')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')

parser.add_argument('--kms_project_id',required=True, help='publisher KMS project')
parser.add_argument('--kms_location_id',required=True, help='KMS kms_location_id (eg, us-central1)')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS kms_key_ring_id (eg, mykeyring)')
parser.add_argument('--kms_key_id',required=True, help='KMS kms_key_id (eg, key1)')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')
args = parser.parse_args()

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

pubsub_project_id = args.pubsub_project_id
kms_project_id = args.kms_project_id

tenantID = args.tenantID

PUBSUB_TOPIC = args.pubsub_topic
PUBSUB_SUBSCRIPTION = args.pubsub_subscription

kms_client = kms.KeyManagementServiceClient()

subscriber = pubsub.SubscriberClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=pubsub_project_id,
    topic=PUBSUB_TOPIC,
)
subscription_name = 'projects/{project_id}/subscriptions/{sub}'.format(
    project_id=pubsub_project_id,
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

      try:
         unwrapped_key = cache[sign_key_wrapped]
         logging.info("Using Cached DEK")
      except KeyError:
        logging.info(">>>>>>>>>>>>>>>>   Starting KMS decryption API call")
        keyURI="gcp-kms://" + name
        unwrapped_key = HMACFunctions(encoded_key=sign_key_wrapped,key_uri=keyURI)
        cache[sign_key_wrapped] = unwrapped_key

        logging.info("End KMS decryption API call")
        logging.debug("Verify message: " + message.data.decode('utf-8'))
        logging.debug('  With HMAC: ' + signature)
   
      sig = unwrapped_key.hash(message.data)

      if (unwrapped_key.verify(message.data,base64.b64decode(sig))):
        logging.info("Message authenticity verified")
        message.ack()
      else:
        logging.error("Unable to verify message")
        message.nack()
      logging.debug("********** End PubsubMessage ")


  if (args.mode == "decrypt"):
      logging.info("********** Start PubsubMessage ")
      logging.info('Received message ID: {}'.format(message.message_id))
      logging.debug('Received message publish_time: {}'.format(message.publish_time))
      logging.debug('Received message attributes["kms_key"]: {}'.format(message.attributes['kms_key']))
      logging.debug('Received message attributes["dek_wrapped"]: {}'.format(message.attributes['dek_wrapped']))
      dek_wrapped = message.attributes['dek_wrapped']
      name = message.attributes['kms_key']

      try:
         dek = cache[dek_wrapped]
         logging.info("Using Cached DEK")
      except KeyError:
        logging.info(">>>>>>>>>>>>>>>>   Starting KMS decryption API call")

        name = message.attributes['kms_key']

        keyURI="gcp-kms://" + name
        dek = AESCipher(encoded_key=dek_wrapped,key_uri=keyURI)
        cache[dek_wrapped] = dek

      logging.debug("Starting AES decryption")

      decrypted_data = dek.decrypt(message.data,associated_data=tenantID)
      logging.debug("End AES decryption")
      logging.info('Decrypted data ' + decrypted_data)
      message.ack()
      logging.debug("ACK message")
      logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
