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

# python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber
# python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

import os, sys
import time
import argparse
from google.cloud import pubsub

import requests
import simplejson as json
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
parser.add_argument('--service_account',required=False,help='publisher service_account credentials file for ADC')
parser.add_argument('--cert_service_account',required=False,help='publisher service_account file to decrypt')
parser.add_argument('--project_id',required=True, help='subscriber projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')
args = parser.parse_args()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
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

    logging.info("Attempting to verify message: " + str(message.data))
    logging.info("Verify message with signature: " + str(signature))
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

    logging.info("Attempting to decrypt message: " + str(message.data))
    logging.info("  Using service_account/key_id: " + msg_service_account + " " + key_id )

    if args.cert_service_account == None:
       logging.error("********** cert_service_account must be specified to decrypt ")       
       message.nack()
       sys.exit()

    credentials = Credentials.from_service_account_file(args.cert_service_account)
    key_key_id = credentials._signer._key_id

    key_service_account_email = credentials.service_account_email
    if (msg_service_account != key_service_account_email):
        logging.info("Service Account specified in command line does not match message payload service account")
        logging.info(msg_service_account + " --- " + args.cert_service_account)
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
