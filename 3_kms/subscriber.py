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

# python subscriber.py   --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber --kms_location_id us-central1 --kms_key_ring_id mykeyring --kms_crypto_key_id key1

import os
import time
import argparse
from google.cloud import pubsub
from google.cloud import kms

import json
import base64
import httplib2

import logging

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=False,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher service_acount credentials file')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--pubsub_subscription',required=True, help='pubsub_subscription to pull message')
parser.add_argument('--kms_location_id',required=True, help='KMS kms_location_id (eg, us-central1)')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS kms_key_ring_id (eg, mykeyring)')
parser.add_argument('--kms_crypto_key_id',required=True, help='KMS kms_crypto_key_id (eg, key1)')
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
kms_location_id = args.kms_location_id
kms_key_ring_id = args.kms_key_ring_id
kms_crypto_key_id = args.kms_crypto_key_id
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

  logging.info("Starting KMS decryption API call")

  decrypted_message = kms_client.decrypt(name=name, 
                  ciphertext=base64.b64decode(message.data),
                  additional_authenticated_data=tenantID.encode('utf-8'))
  # request = crypto_keys.decrypt(
  #       name=name,
  #       body={
  #        'ciphertext': (message.data).decode('utf-8'),
  #        'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')
  #       })
  # response = request.execute()
  dec =  base64.b64decode(decrypted_message.plaintext)
  logging.info("End KMS decryption API call")
  logging.info('Decrypted data ' + decrypted_message.plaintext.decode('utf-8'))
  message.ack()
  logging.info("ACK message")
  logging.info("********** End PubsubMessage ")

subscriber.subscribe(subscription_name, callback=callback)

logging.info('Listening for messages on {}'.format(subscription_name))
while True:
  time.sleep(10)
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
