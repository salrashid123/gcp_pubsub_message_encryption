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

import os
import time
import argparse
from google.cloud import pubsub
from google.cloud import kms

import json
import base64
import httplib2
import hashlib

import logging

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--mode',required=True, choices=['decrypt','verify'], help='mode must be decrypt or verify')
parser.add_argument('--service_account',required=False,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher service_acount credentials file')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')

args = parser.parse_args()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account


project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
PUBSUB_TOPIC = args.pubsub_topic
PUBSUB_SUBSCRIPTION = args.pubsub_subscription

tenantID = args.tenantID


kms_client = kms.KeyManagementServiceClient()

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
  logging.info('Received message attributes["kms_key"]: {}'.format(message.attributes['kms_key']))
  name = message.attributes['kms_key']

  if args.mode=='decrypt':
      try:
        logging.info("Starting KMS decryption API call")

        decrypted_message = kms_client.decrypt(
            request={'name': name, 'ciphertext': base64.b64decode(message.data), 'additional_authenticated_data': tenantID.encode('utf-8')  })

        dec =  base64.b64decode(decrypted_message.plaintext)
        logging.info("End KMS decryption API call")
        logging.info('Decrypted data ' + decrypted_message.plaintext.decode('utf-8'))
        message.ack()
        logging.info("ACK message")
      except Exception as e:
        logging.info("Unable to decrypt message; NACK pubsub message " + str(e))
        message.nack()
      logging.info("End AES decryption")

  if args.mode=='verify':
    try:
      logging.info("Starting HMAC")
      hmac = message.attributes.get('signature')

      m = hashlib.sha256()
      m.update(message.data)
      data_to_verify = m.digest()
    
      logging.info("Verify message: " + str(message.data))
      logging.info("data_to_verify " + base64.b64encode(data_to_verify).decode('utf-8'))
      logging.info('  With HMAC: ' + str(hmac))

      verification_message = kms_client.mac_verify(
            request={'name': name, 'data': data_to_verify, 'mac': base64.b64decode(hmac)  })
      if verification_message.success:
        logging.info("MAC verified ")
        message.ack()
      else:
        logging.info("Mac verification failed; NACK pubsub message")
        message.nack()        
    except Exception as e:
      logging.info("Unable to verify message; NACK pubsub message " + str(e))
      message.nack()

  logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
