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

# python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY
# python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --salt mysalt --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY

import os ,sys
import time
import logging
import argparse

import base64, binascii
import httplib2
import hmac
import canonicaljson
import simplejson as json
from google.cloud import pubsub

from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

import utils
from utils import AESCipher, HMACFunctions

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted or signed message')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--service_account',required=False,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--key',required=True, help='key, for encryption, use 32bytes, for sign, use use complex passphrase')
args = parser.parse_args()

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
PUBSUB_TOPIC = args.pubsub_topic

publisher = pubsub.PublisherClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
)

#BLOCK_SIZE=256
#key = binascii.hexlify(os.urandom(BLOCK_SIZE))
#print key
key = args.key

logging.info(">>>>>>>>>>> Start <<<<<<<<<<<")

cleartext_message = {
    "data" : "foo".encode(),
    "attributes" : {
        'epoch_time':  int(time.time()),
        'a': "aaa",
        'c': "ccc",
        'b': "bbb"
    }
}
# cleartext_message = canonicaljson.encode_canonical_json(cleartext_message)
# logging.info("Canonical JSON message " + cleartext_message.decode('utf-8'))

if args.mode=='encrypt':
    logging.info("Starting AES encryption")
    ac = AESCipher(key)
    msg = ac.encrypt(json.dumps(cleartext_message).encode('utf-8'),associated_data='')
    logging.info("End AES encryption")
    logging.info("Start PubSub Publish")
    resp=publisher.publish(topic_name, data=msg.encode('utf-8'))
    logging.info("Published Message: " + str(msg))
    logging.info("Published MessageID: " + resp.result())
    logging.info("End PubSub Publish")

if args.mode=='sign':
    logging.info("Starting signature")
    hh = HMACFunctions(key)
    msg_hash = hh.hash(json.dumps(cleartext_message).encode('utf-8'))
    logging.info("End signature")

    logging.info("Start PubSub Publish")
    resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), signature=msg_hash)
    logging.info("Published Message: " + json.dumps(cleartext_message))
    logging.info("  with hmac: " + str(msg_hash))
    logging.info("Published MessageID: " + resp.result())
    logging.info("End PubSub Publish")

logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
