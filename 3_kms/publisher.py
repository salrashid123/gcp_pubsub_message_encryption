#!/usr/bin/python

# python publisher.py  --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --kms_location_id us-central1 --kms_key_ring_id mykeyring --kms_crypto_key_id key1


import os ,sys
import time
import logging
import argparse

from google.cloud import pubsub

import jwt
import json
import base64, binascii
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=True,help='publisher service_acount credentials file')
parser.add_argument('--project_id',required=True, help='publisher service_acount credentials file')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--kms_location_id',required=True, help='KMS kms_location_id (eg, us-central1)')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS kms_key_ring_id (eg, mykeyring)')
parser.add_argument('--kms_crypto_key_id',required=True, help='KMS kms_crypto_key_id (eg, key1)')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')

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
kms_location_id = args.kms_location_id
kms_key_ring_id = args.kms_key_ring_id
kms_crypto_key_id = args.kms_crypto_key_id
tenantID = args.tenantID


kms_client = build('cloudkms', 'v1')
name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
        project_id, kms_location_id, kms_key_ring_id, kms_crypto_key_id)

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

crypto_keys = kms_client.projects().locations().keyRings().cryptoKeys()
logging.info("Starting KMS encryption API call")
request = crypto_keys.encrypt(
        name=name,
        body={
         'plaintext': base64.b64encode(json.dumps(cleartext_message)).decode('utf-8'),
         'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')         
        })
response = request.execute()
data_encrypted = response['ciphertext'].encode('utf-8')
logging.info("End KMS encryption API call")
#request = crypto_keys.decrypt(
#        name=name,
#        body={
#         'ciphertext': (data_encrypted).decode('utf-8')
#        })
#response = request.execute()
#logging.info(base64.b64decode(response['plaintext'].encode('utf-8')))

logging.info("Wrapped data: " + data_encrypted)

logging.info("Start PubSub Publish")
publisher = pubsub.PublisherClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
)
publisher.publish(topic_name, data=data_encrypted.encode('utf-8'), kms_key=name)
logging.info("Published Message: " + data_encrypted)
logging.info("End PubSub Publish")
logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
