#!/usr/bin/python

# python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY
# python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --salt mysalt --key btetykj7jJTiCNZmmGzTtuoRNLmnBtxY

import os ,sys
import time
import logging
import argparse
import json
import base64, binascii
import httplib2
import hmac
import canonicaljson

from google.cloud import pubsub

from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

import utils
from utils import AESCipher, HMACFunctions

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted or signed message')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--salt',required=False,default="foo", help='Salt to use for singed message')
parser.add_argument('--service_account',required=True,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--key',required=True, help='key, for encryption, use 32bytes, for sign, use use complex passphrase')
args = parser.parse_args()

scope='https://www.googleapis.com/auth/pubsub'

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
#cleartext_message = canonicaljson.encode_canonical_json({})
#logging.info("Canonical JSON message " + cleartext_message)

if args.mode=='encrypt':
    if len(key) < 32:
      logging.error("Encryption key for AES must be (8,24 or 32 bytes).  eg: --key " + utils.getKey(size=32))
      sys.exit(0)
    logging.info("Starting AES encryption")
    ac = AESCipher(key)
    msg = ac.encrypt(json.dumps(cleartext_message))
    logging.info("End AES encryption")
    logging.info("Start PubSub Publish")
    publisher.publish(topic_name, data=msg.encode('utf-8'))
    logging.info("Published Message: " + msg)
    logging.info("End PubSub Publish")

if args.mode=='sign':
    if len(key) < 32:
      logging.error("Use 32 bit pasphrase.  eg: --key " + utils.getKey(size=32))
      sys.exit(0)
    logging.info("Starting signature")
    hh = HMACFunctions(base64.b64encode(key))
    msg_hash = hh.hash(json.dumps(cleartext_message))
    logging.info("End signature")

    logging.info("Start PubSub Publish")
    publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), signature=msg_hash)
    logging.info("Published Message: " + json.dumps(cleartext_message))
    logging.info("  with hmac: " + msg_hash)

    logging.info("End PubSub Publish")

logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
