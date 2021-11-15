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


import os ,sys
import time
import logging
import argparse
import hashlib

from google.cloud import pubsub
from google.cloud import kms


import jwt
import simplejson as json
import base64, binascii
import httplib2

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--service_account',required=False,help='publisher service_account credentials file')
parser.add_argument('--project_id',required=True, help='publisher service_acount credentials file')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--kms_location_id',required=True, help='KMS kms_location_id (eg, us-central1)')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS kms_key_ring_id (eg, mykeyring)')
parser.add_argument('--kms_crypto_key_id',required=True, help='KMS kms_crypto_key_id (eg, key1)')
parser.add_argument('--kms_crypto_key_version',required=False, help='KMS kms_crypto_key_version; required for mode=sign ')
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
kms_location_id = args.kms_location_id
kms_key_ring_id = args.kms_key_ring_id
kms_crypto_key_id = args.kms_crypto_key_id
kms_crypto_key_version = args.kms_crypto_key_version
tenantID = args.tenantID

kms_client = kms.KeyManagementServiceClient()

if kms_crypto_key_version is not None:
    name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}/cryptoKeyVersions/{}'.format(
            project_id, kms_location_id, kms_key_ring_id, kms_crypto_key_id, kms_crypto_key_version)    
else:
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

publisher = pubsub.PublisherClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
)

if args.mode=='encrypt':
    logging.info("Start KMS encryption API call")
    encrypt_response = kms_client.encrypt(
        request={'name': name, 'plaintext': json.dumps(cleartext_message).encode('utf-8'), 'additional_authenticated_data': tenantID.encode('utf-8')  })
    logging.info("End KMS encryption API call")

    logging.info("Start PubSub Publish")
    resp=publisher.publish(topic_name, data=base64.b64encode(encrypt_response.ciphertext), kms_key=name)
    logging.info("Published Message: " + base64.b64encode(encrypt_response.ciphertext).decode())
    logging.info("Published MessageID: " + resp.result())
    logging.info("End PubSub Publish")

if args.mode=='sign':
    logging.info("Start KMS mac API call")

    m = hashlib.sha256()
    m.update(json.dumps(cleartext_message).encode())
    data_to_sign = m.digest()
    logging.info("data_to_sign " + base64.b64encode(data_to_sign).decode('utf-8'))

    mac_response = kms_client.mac_sign(
        request={'name': name, 'data': data_to_sign })
    logging.info("End KMS mac API call")

    logging.info("MAC: " + base64.b64encode(mac_response.mac).decode())
    
    logging.info("Start PubSub Publish")
    resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), kms_key=name, signature=base64.b64encode(mac_response.mac).decode())
    logging.info("Published MessageID: " + resp.result())
    logging.info("End PubSub Publish")    


logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
