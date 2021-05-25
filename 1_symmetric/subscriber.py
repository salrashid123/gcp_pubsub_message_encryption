#!/usr/bin/python

# Copyright 2018 Google Inc. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_subscription my-new-subscriber --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY
# python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_subscription my-new-subscriber --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY

import os
import time
from google.cloud import pubsub

import argparse
import json
import base64
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

import utils
from utils import AESCipher, HMACFunctions
import canonicaljson

import logging

logging.Formatter('%(asctime)s')
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


parser = argparse.ArgumentParser(description='Subscribe encrypted or signed message')
parser.add_argument('--mode',required=True, choices=['decrypt','verify'], help='mode must be decrypt or verify')
parser.add_argument('--service_account',required=False,help='subscriber service_account credentials file')
parser.add_argument('--project_id',required=True, help='subscription projectID')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull from')
parser.add_argument('--key',required=True, help='key')
args = parser.parse_args()

logging.info(">>>>>>>>>>> Start <<<<<<<<<<<")

scope='https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

credentials = GoogleCredentials.get_application_default()
if credentials.create_scoped_required():
  credentials = credentials.create_scoped(scope)

http = httplib2.Http()
credentials.authorize(http)

project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
key = args.key


PUBSUB_SUBSCRIPTION =args.pubsub_subscription

subscriber = pubsub.SubscriberClient()

subscription_name = 'projects/{project_id}/subscriptions/{sub}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    sub=PUBSUB_SUBSCRIPTION,
)

#PUBSUB_TOPIC = args.pubsub_topic
#topic_name = 'projects/{project_id}/topics/{topic}'.format(
#    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
#    topic=PUBSUB_TOPIC,
#)
#subscriber.create_subscription(name=subscription_name, topic=topic_name)

BLOCK_SIZE = 256
pad = lambda s: s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * \
                chr(BLOCK_SIZE - len(s) % BLOCK_SIZE)
unpad = lambda s: s[:-ord(s[len(s) - 1:])]

def callback(message):
  logging.info("********** Start PubsubMessage ")
  message.ack()
  logging.info('Received message ID: {}'.format(message.message_id))
  logging.info('Received message publish_time: {}'.format(message.publish_time))

  if args.mode=='decrypt':
      try:
        ac = AESCipher(key)
        decrypted_data = ac.decrypt(message.data,associated_data='')
        logging.info('Decrypted data ' + decrypted_data)
        logging.info("ACK message")
        message.ack()
      except:
        logging.info("Unable to decrypt message; NACK pubsub message")
        message.nack()
      logging.info("End AES decryption")

  if args.mode=='verify':
    logging.info("Starting HMAC")
    hmac = message.attributes.get('signature')
    hh = HMACFunctions(key)
    logging.info("Verify message: " + str(message.data))
    logging.info('  With HMAC: ' + str(hmac))
    hashed=hh.hash(message.data)
    if (hh.verify(message.data,base64.b64decode(hashed))):
      logging.info("Message authenticity verified")
      message.ack()
    else:
      logging.error("Unable to verify message")
      message.nack()


  logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
