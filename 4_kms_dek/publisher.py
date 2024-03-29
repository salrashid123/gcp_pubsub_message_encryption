#!/usr/bin/python

import os ,sys
import time
import logging

from google.cloud import pubsub
from google.cloud import kms
import argparse
import jwt
import simplejson as json
import time
import base64, binascii
import httplib2


from expiringdict import ExpiringDict

import utils
from utils import AESCipher, RSACipher, HMACFunctions

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

parser = argparse.ArgumentParser(description='Publish encrypted message with KMS only')
parser.add_argument('--service_account',required=False,help='publisher service_acount credentials file')
parser.add_argument('--mode',required=True, choices=['encrypt','sign'], help='mode must be encrypt or sign')
parser.add_argument('--kms_project_id',required=True, help='publisher KMS project')
parser.add_argument('--kms_location',required=True, help='KMS Location')
parser.add_argument('--kms_key_ring_id',required=True, help='KMS key_ring_id')
parser.add_argument('--kms_key_id',required=True, help='KMS keyid')
parser.add_argument('--pubsub_project_id',required=True, help='publisher projectID')
parser.add_argument('--pubsub_topic',required=True, help='pubsub_topic to publish message')
parser.add_argument('--tenantID',required=False, default="tenantKey", help='Optional additionalAuthenticatedData')
args = parser.parse_args()

scope='https://www.googleapis.com/auth/cloudkms https://www.googleapis.com/auth/pubsub'

if args.service_account != None:
  os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.service_account

pubsub_project_id = args.pubsub_project_id
kms_project_id = args.kms_project_id
location_id = args.kms_location
key_ring_id = args.kms_key_ring_id
crypto_key_id = args.kms_key_id
tenantID = args.tenantID

PUBSUB_TOPIC=args.pubsub_topic

cache = ExpiringDict(max_len=100, max_age_seconds=20)


kms_client = kms.KeyManagementServiceClient()
name = 'projects/{}/locations/{}/keyRings/{}/cryptoKeys/{}'.format(
        kms_project_id, location_id, key_ring_id, crypto_key_id)

if args.mode =="sign":
  logging.info(">>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<")
  for x in range(5):

        logging.info("Rotating key")

        hh = HMACFunctions(encoded_key=None)
        sign_key = hh.getKey()
        logging.info(hh.printKeyInfo())
        logging.debug("Generated hmac: " + sign_key )
        logging.info("Starting KMS encryption API call")
        encrypt_response = kms_client.encrypt(
            request={'name': name, 'plaintext': sign_key.encode('utf-8'), 'additional_authenticated_data': tenantID.encode('utf-8')  })

        hh_encrypted =  base64.b64encode(encrypt_response.ciphertext).decode('utf-8')  

        logging.info("Wrapped hmac key: " +  hh_encrypted)
        logging.info("End KMS encryption API call")
        publisher = pubsub.PublisherClient()

        for x in range(5):
                cleartext_message = {
                        "data" : "foo".encode(),
                        "attributes" : {
                        'epoch_time':  int(time.time()),
                        'a': "aaa",
                        'c': "ccc",
                        'b': "bbb"
                        }
                }

                msg_hash = hh.hash(json.dumps(cleartext_message).encode('utf-8'))
                logging.debug("Generated Signature: " + msg_hash.decode('utf-8'))
                logging.debug("End signature")

                logging.info("Start PubSub Publish")

                topic_name = 'projects/{project_id}/topics/{topic}'.format(
                project_id=pubsub_project_id,
                topic=PUBSUB_TOPIC,
                )

                resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), kms_key=name, sign_key_wrapped=hh_encrypted, signature=msg_hash)
                logging.info("Published Message: " + str(cleartext_message))
                logging.info(" with key_id: " + name)
                logging.debug(" with wrapped signature key " + hh_encrypted )
                logging.info("Published MessageID: " + resp.result())

                logging.debug("End PubSub Publish")
                time.sleep(1)
  logging.info(">>>>>>>>>>> END <<<<<<<<<<<")

if args.mode =="encrypt":
    logging.info(">>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<")
    ## Send pubsub messages using two different symmetric keys
    ## Note, i'm not using the expiringdict here...i'm just picking a DEK, sending N messages using it
    ## then picking another DEK and sending N messages with that one.
    ## The subscriber will use a cache of DEK values.  If it detects a DEK in the metadata that doesn't 
    ## match whats in its cache, it will use KMS to try to decode it and then keep it in its cache.
    for x in range(5):
        logging.info("Rotating symmetric key")

        # create a new TINK AES DEK and encrypt it with KMS.
        #  (i.,e an encrypted tink keyset)
        cc = AESCipher(encoded_key=None)
        dek = cc.getKey()
        logging.info(cc.printKeyInfo())

        logging.debug("Generated dek: " + dek )
        logging.info("Starting KMS encryption API call")
        encrypt_response = kms_client.encrypt(
            request={'name': name, 'plaintext': dek.encode('utf-8'), 'additional_authenticated_data': tenantID.encode('utf-8')  })

        dek_encrypted =  base64.b64encode(encrypt_response.ciphertext).decode('utf-8')  

        logging.info("Wrapped dek: " +  dek_encrypted)
        logging.info("End KMS encryption API call")


        publisher = pubsub.PublisherClient()
        logging.info("Start PubSub Publish")
         ## Send 5 messages using the same symmetric key...
        for x in range(5):
                cleartext_message = {
                        "data" : "foo".encode(),
                        "attributes" : {
                                'epoch_time':  int(time.time()),
                                'a': "aaa",
                                'c': "ccc",
                                'b': "bbb"
                        }
                }
                logging.debug("Start AES encryption")
                encrypted_message = cc.encrypt(json.dumps(cleartext_message).encode('utf-8'),associated_data=tenantID)
                logging.debug("End AES encryption")
                logging.debug("Encrypted Message with dek: " + encrypted_message)

                topic_name = 'projects/{project_id}/topics/{topic}'.format(
                        project_id=pubsub_project_id,
                        topic=PUBSUB_TOPIC,
                )

                resp=publisher.publish(topic_name, data=encrypted_message.encode(), kms_key=name, dek_wrapped=dek_encrypted)
                logging.info("Published Message: " + encrypted_message)
                logging.info("Published MessageID: " + resp.result())
                time.sleep(1)
    logging.info("End PubSub Publish")
    logging.info(">>>>>>>>>>> END <<<<<<<<<<<")
