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


import argparse
import base64
import binascii
import hashlib
import logging
import os
import sys
import time

import google.auth
import httplib2
import jwt
import requests
import simplejson as json
from google.auth import crypt, impersonated_credentials, jwt
from google.auth.transport import requests as authreq
from google.cloud import pubsub

import utils
from utils import AESCipher, RSACipher

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=False,help='publisher service_account credentials file (must beset unless --impersonated_service_account is set)')
parser.add_argument('--impersonated_service_account',required=False,help='use impersonation to sign')
parser.add_argument('--cert_service_account',required=False,help='publisher service_account file to sign')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--recipient',required=False, help='Service Account to encrypt for')
parser.add_argument('--recipient_key_id',required=False, help='Service Account key_id to use')
parser.add_argument('--project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')

args = parser.parse_args()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

scope='https://www.googleapis.com/auth/iam https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

credentials, project_id = google.auth.default()

project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
PUBSUB_TOPIC = args.pubsub_topic
publisher = pubsub.PublisherClient()
topic_name = 'projects/{project_id}/topics/{topic}'.format(
  project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
  topic=PUBSUB_TOPIC,
)

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
  if args.cert_service_account == None and args.impersonated_service_account == None:
    logging.error("either --cert_service_account or --impersonated_service_account must be set ")
    sys.exit(1)

  logging.info(">>>>>>>>>>> Start Sign with Service Account <<<<<<<<<<<")

  m = hashlib.sha256()
  m.update(json.dumps(cleartext_message).encode())
  data_to_sign = m.digest()
  logging.info("data_to_sign " + base64.b64encode(data_to_sign).decode('utf-8'))

  if args.impersonated_service_account != None:
    # note, we can't use the normal signer here since the existing `sign_bytes()` does not return the key_id
    #  technically, we don't need to submit the key_id into the pubsub message...the subscriber could just iterate
    #  over all keys...but thats inefficient
    # impersonated = impersonated_credentials.Credentials(
    #   source_credentials=credentials,
    #   target_principal=args.impersonated_service_account,
    #   target_scopes = 'https://www.googleapis.com/auth/cloud-platform',
    #   lifetime=500)  
    # data_signed = impersonated.sign_bytes(json.dumps(cleartext_message).encode('utf-8'))
    # service_account = impersonated.signer_email     

    IAM_SIGN_ENDPOINT = (
        "https://iamcredentials.googleapis.com/v1/projects/-"
        + "/serviceAccounts/{}:signBlob"
    )
    iam_sign_endpoint = IAM_SIGN_ENDPOINT.format(args.impersonated_service_account)
    body = {
      "payload": base64.b64encode(data_to_sign).decode("utf-8"),
    }    
    headers = {"Content-Type": "application/json"}
    authed_session = authreq.AuthorizedSession(credentials)

    response = authed_session.post(
        url=iam_sign_endpoint, headers=headers, json=body
    )

    data_signed = base64.b64decode(response.json()["signedBlob"])
    service_account = args.impersonated_service_account
    key_id = response.json()["keyId"]
  else:
    credentials, project_id = google.auth.load_credentials_from_file(args.cert_service_account)
    data_signed = credentials.sign_bytes(data_to_sign)
    key_id = credentials._signer._key_id
    service_account = credentials.signer_email
    
  logging.info("Signature: {}".format(base64.b64encode(data_signed).decode('utf-8')))
  logging.info("key_id {}".format(key_id))
  logging.info("service_account {}".format(service_account))    

  logging.info("Start PubSub Publish")
  publisher = pubsub.PublisherClient()
  topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
  )

  resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), 
      key_id=key_id, service_account=service_account, signature=base64.b64encode(data_signed))
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

  # Create a new TINK AES key used for data encryption
  cc = AESCipher(encoded_key=None)
  dek = cc.getKey()
  logging.info("Generated DEK: " + cc.printKeyInfo() )
 
  # now use the DEK to encrypt the pubsub message
  encrypted_payload = cc.encrypt(json.dumps(cleartext_message).encode('utf-8'),associated_data="")
  logging.info("DEK Encrypted Message: " + encrypted_payload )
  # encrypt the DEK with the service account's key
  dek_wrapped = rs.encrypt(dek.encode('utf-8'))
  logging.info("Wrapped DEK " + dek_wrapped.decode('utf-8'))

  # now publish the dek-encrypted message, the encrypted dek 
  resp=publisher.publish(topic_name, data=encrypted_payload.encode('utf-8'), service_account=args.recipient, key_id=args.recipient_key_id, dek_wrapped=dek_wrapped)

  # alternatively, dont' bother with the dek; just use the rsa key itself to encrypt the message
  #encrypted_payload = rs.encrypt(json.dumps(cleartext_message).encode('utf-8'))
  #resp=publisher.publish(topic_name, data=json.dumps(encrypted_payload).encode('utf-8'), service_account=args.recipient, key_id=args.recipient_key_id)

  logging.info("Start PubSub Publish")

  logging.info("Published Message: " + str(encrypted_payload))
  logging.info("Published MessageID: " + resp.result())
  logging.info("End PubSub Publish")
  logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
