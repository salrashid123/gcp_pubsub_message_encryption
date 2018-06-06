#!/usr/bin/python


#  python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1
#  --dek JCZRt+IeTnTFB9OH8McpTlRQYR3I3MHBLy29VhfIUn4=


# python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1

import os ,sys
import time
import logging

from google.cloud import pubsub
import argparse
import jwt
import json
import base64, binascii
import httplib2
from apiclient.discovery import build
from oauth2client.client import GoogleCredentials

from expiringdict import ExpiringDict

import utils
from utils import AESCipher, RSACipher, HMACFunctions

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=True,help='publisher service_acount credentials file')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--kms_location',required=True, help='KMS Location')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS key_ring_id')
parser.add_argument('--kms_key_id',required=True, help='KMS keyid')
parser.add_argument('--project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--dek',required=False, help='Static DEK to use for message encryption')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')
args = parser.parse_args()

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

credentials = GoogleCredentials.get_application_default()
if credentials.create_scoped_required():
  credentials = credentials.create_scoped(scope)

http = httplib2.Http()
credentials.authorize(http)

project_id = args.project_id
os.environ['GOOGLE_CLOUD_PROJECT'] = project_id
location_id = args.kms_location
key_ring_id = args.kms_key_ring_id
crypto_key_id = args.kms_key_id
tenantID = args.tenantID

PUBSUB_TOPIC=args.pubsub_topic

cache = ExpiringDict(max_len=100, max_age_seconds=20)


kms_client = build('cloudkms', 'v1')
name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
        project_id, location_id, key_ring_id, crypto_key_id)

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
  logging.info(">>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<")

  hh = HMACFunctions()
  sign_key = hh.getDerivedKey()
  logging.info("Generated Derived Key: " + base64.b64encode(sign_key))
  msg_hash = hh.hash(json.dumps(cleartext_message))
  logging.info("Generated Signature: " + msg_hash)
  logging.info("End signature")

  logging.info("Starting KMS encryption API call")
  crypto_keys = kms_client.projects().locations().keyRings().cryptoKeys()
  request = crypto_keys.encrypt(
            name=name,
            body={
             'plaintext': base64.b64encode(sign_key).decode('utf-8'),
             'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')
            })
  response = request.execute()
  sign_key_wrapped = response['ciphertext'].encode('utf-8')
  logging.info("End KMS encryption API call")

  logging.info("Start PubSub Publish")
  publisher = pubsub.PublisherClient()
  topic_name = 'projects/{project_id}/topics/{topic}'.format(
    project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
    topic=PUBSUB_TOPIC,
  )

  publisher.publish(topic_name, data=json.dumps(cleartext_message), kms_key=name, sign_key_wrapped=sign_key_wrapped, signature=msg_hash)
  logging.info("Published Message: " + str(cleartext_message))
  logging.info(" with key_id: " + name)
  logging.info(" with wrapped signature key " + sign_key_wrapped)
  logging.info("End PubSub Publish")
  logging.info(">>>>>>>>>>> END <<<<<<<<<<<")

if args.mode =="encrypt":
    logging.info(">>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<")

    if  tenantID in cache:
      dek = cache[tenantID]
      logging.info("Reusing existing dek: " + base64.b64encode(dek) )
    else:
      # 256bit AES key
      dek = os.urandom(32)
      logging.info("Generated dek: " + base64.b64encode(dek) )
      cache[tenantID] = dek

    logging.info("Starting AES encryption")
    ac = AESCipher(dek)

    encrypted_message = ac.encrypt(json.dumps(cleartext_message))
    logging.info("End AES encryption")
    logging.info("Encrypted Message with dek: " + encrypted_message)


    logging.info("Starting KMS encryption API call")
    crypto_keys = kms_client.projects().locations().keyRings().cryptoKeys()
    request = crypto_keys.encrypt(
            name=name,
            body={
             'plaintext': base64.b64encode(dek).decode('utf-8'),
             'additionalAuthenticatedData': base64.b64encode(tenantID).decode('utf-8')
            })
    response = request.execute()
    dek_encrypted = response['ciphertext'].encode('utf-8')
    #request = crypto_keys.decrypt(
    #        name=name,
    #        body={
    #         'ciphertext': (dek_encrypted).decode('utf-8'),
    #         'additionalAuthenticatedData': base64.b64encode(additionalAuthenticatedData).decode('utf-8')
    #        })
    #response = request.execute()
    #logging.info(base64.b64decode(response['plaintext'].encode('utf-8')))
    logging.info("Wrapped dek: " + dek_encrypted)
    logging.info("End KMS encryption API call")

    logging.info("Start PubSub Publish")
    publisher = pubsub.PublisherClient()
    topic_name = 'projects/{project_id}/topics/{topic}'.format(
        project_id=os.getenv('GOOGLE_CLOUD_PROJECT'),
        topic=PUBSUB_TOPIC,
    )
    publisher = pubsub.PublisherClient()
    publisher.publish(topic_name, data=encrypted_message.encode('utf-8'), kms_key=name, dek_wrapped=dek_encrypted)
    logging.info("Published Message: " + encrypted_message)
    logging.info("End PubSub Publish")
    logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
