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

#  python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic
#  python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --recipient subscriber@esp-demo-197318.iam.gserviceaccount.com --recipient_key_id f4425f395a815f54379421d8279d8477e70fc189


import os ,sys
import time
import logging
import argparse
import requests

from google.cloud import pubsub
import google.auth
from google.oauth2 import service_account

import jwt
import simplejson as json
import base64, binascii
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials
from google.auth import crypt
from google.auth import jwt
import utils
from utils import AESCipher, HMACFunctions, RSACipher

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=False,help='publisher service_account credentials file')
parser.add_argument('--cert_service_account',required=False,help='publisher service_account file to sign')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--recipient',required=False, help='Service Account to encrypt for')
parser.add_argument('--recipient_key_id',required=False, help='Service Account key_id to use')
parser.add_argument('--project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')

args = parser.parse_args()

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

scope='https://www.googleapis.com/auth/iam https://www.googleapis.com/auth/pubsub'

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

cleartext_message = {
    "data" : "foo".encode(),
    "attributes" : {
        'epoch_time':  int(time.time()),
        'a': "aaa",
        'c': "ccc",
        'b': "bbb"
    }
}

if args.mode =="sign":
  logging.info(">>>>>>>>>>> Start Sign with Service Account json KEY <<<<<<<<<<<")
  if args.cert_service_account == None:
       logging.error("********** cert_service_account must be specified to decrypt ")
       sys.exit()
  credentials = service_account.Credentials.from_service_account_file(args.cert_service_account)
  data_signed = credentials.sign_bytes(json.dumps(cleartext_message))
  logging.info("Signature: "  + base64.b64encode(data_signed).decode('utf-8'))
  key_id = credentials._signer._key_id
  service_account = credentials.service_account_email
  # Also use: https://google-auth.readthedocs.io/en/latest/reference/google.auth.jwt.html#module-google.auth.jwt
  #signer = credentials._signer
  #payload = {'some': 'payload'}
  #data_signed = jwt.encode(signer, cleartext_message)
  #claims = jwt.decode(data_signed, certs=public_certs)

  logging.info("Start PubSub Publish")
  publisher = pubsub.PublisherClient()
  topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
  )

  resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), key_id=key_id, service_account=service_account, signature=base64.b64encode(data_signed))
  logging.info("Published Message: " + str(cleartext_message))
  logging.info("Published MessageID: " + resp.result())
  logging.info("End PubSub Publish")
  logging.info(">>>>>>>>>>> END <<<<<<<<<<<")


if args.mode =="encrypt":
  if ( (args.recipient is None) or (args.recipient_key_id is None)):
      logging.info("Must provide serviceAccount and key_id to use for encryption ")
      logging.info('   --receipient publisher@esp-demo-197318.iam.gserviceaccount.com')
      logging.info('   --key_id 471dc3b590ad422999963cc6ea5a913fee75a2ef')
      sys.exit(1)

  logging.info(">>>>>>>>>>> Start Encrypt with Service Account Public Key Reference <<<<<<<<<<<")
  logging.info('  Using remote public key_id = ' + args.recipient_key_id)
  logging.info('  For service account at: https://www.googleapis.com/service_accounts/v1/metadata/x509/' +  args.recipient)

  cert_url = 'https://www.googleapis.com/service_accounts/v1/metadata/x509/' + args.recipient
  r = requests.get(cert_url)
  pem = r.json().get(args.recipient_key_id)
  rs = RSACipher(public_key_pem = pem)
  encrypted_payload = rs.encrypt(json.dumps(cleartext_message).encode('utf-8'))

  logging.info("Start PubSub Publish")
  publisher = pubsub.PublisherClient()
  topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
  )

  resp=publisher.publish(topic_name, data=json.dumps(encrypted_payload).encode('utf-8'), service_account=args.recipient, key_id=args.recipient_key_id)
  logging.info("Published Message: " + str(encrypted_payload))
  logging.info("Published MessageID: " + resp.result())
  logging.info("End PubSub Publish")
  logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
