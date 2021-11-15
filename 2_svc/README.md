

# Message Payload Encryption in Google Cloud Pub/Sub (Part 2: Service Account Public Keys)

## Introduction

This is the second in a series exploring how to encrypt the message data payload within a Google PubSub message.  This will not go into any real detail on the situations _why_ you want to ensure confidentiality or integrity of a given message but many of them were discussed in the first part of the series.   If you haven't already, please do read atleast the introduction section in the first part.

Anyway, what we've covered so far is a form of simple symmetric encryption where the sender and receiver are both using a static key   There are clear drawbacks to this which was outlined in that article.  We're here to see if we can improve on it or develop a different technique.

So, instead of sharing a symmetric key, can we use the public/private key pairs *already* provided by google as part of their [Service Account Credential](https://cloud.google.com/compute/docs/access/service-accounts)?

## What exactly are we encrypting and signing?

This technique relies on the publisher have a [service_account private key](https://cloud.google.com/iam/docs/service-accounts#service_account_keys) in JSON format.  What that will allow you to do is sign a message payload locally for integrity/authentication.  The public key  for most GCP service accounts is available externally for any recipient to verify with.   For example, here is a snippet for a private key json:

```json
{
  "type": "service_account",
  "project_id": "pubsub-msg",
  "private_key_id": "54927b54123e5b00f5e7ca6e290b3823d545eeb2",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADAXgIU=\n-----END PRIVATE KEY-----\n",
  "client_email": "publisher@pubsub-msg.iam.gserviceaccount.com",
  "client_id": "108529726503327553286",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/publisher%40pubsub-msg.iam.gserviceaccount.com"
}
```

which has the public key available at a well-known URL (```client_x509_cert_url```):

- x509:
    - [https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@pubsub-msg.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@pubsub-msg.iam.gserviceaccount.com)
- JWK
    - [https://www.googleapis.com/service_accounts/v1/jwk/publisher@publisher@pubsub-msg.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/jwk/publisher@pubsub-msg.iam.gserviceaccount.com)


Since the subscriber can download these certs to verify a message, the issue of key-distribution is a bit easier.

Wait....we've got a public key on our hands now...we can use that for encryption too.   In this mode, the publisher uses the public key for the for the _subscriber__ to encrypt a message  (in our case, one of the available keys [here](https://www.googleapis.com/service_accounts/v1/metadata/x509/subscriber@pubsub-msg.iam.gserviceaccount.com)).  The subscriber on the other end must have in possession or have the ability to verify the message (i.,e have the private key).  With this technique, you are ensuring confidentiality by encrypting the payload using public/private keys

## Using Service Account Token Creator Role

What we've done here is use a service account to sign the payload. GCP has another mechanism where one service account can _impersonate_ another and sign data on its behalf.  This is useful if you want to mint a message on behalf of another service account.   If you want more information on this variation and code samples, see:

- [Service Account impersonation](https://github.com/salrashid123/gcpsamples/tree/master/auth/tokens)
- [iam.signJwt()](https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts/signJwt)
- [iam.signBlob()](https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts/signBlob)

To use this mode, specify the `--impersonated_service_account` flag
### Encrypted message Formatter

There are two layers of encryption involved with this:  a data encryption key (DEK) and a Key Encryption Key (KEK).

The DEK is a one-time key generated using TINK which is used to encrypt the actual pubsub message.  The KEK is the subscriber service account's public key used to encrypt the DEK.

so, its

1. create an AES DEK using TINK
2. encrypt the pubsub message using DEK
3. use the public key for the subscriber to encrypt the DEK
4. transmit the encrypted message and encrypted DEK to pubsub

The pubsub message would be of the form

```python
resp=publisher.publish(topic_name, data=encrypted_payload.encode('utf-8'), service_account=args.recipient, key_id=args.recipient_key_id, dek_wrapped=dek_wrapped)
```

The subscriber will use the private key to decrypt the DEK and then use the decrypted DEK to decrypt the message.

Note, the the `key_id` and `service_account` attributes trasmitted isn't really necessary here (since in this example, the subscriber only has one key).  Its possible to use
these fields to pull only messages applicable for decryption

### Signed message Formatter

The signing does not use a DEK but uses the private key for the subscriber directly:

If the subscriber wants to sign message `M`

1. create a hash of `M`
2. use publishers's private key to sign `M`
3. Transmit the message hash and message

The pubsub message would be in the form

```python
resp=publisher.publish(topic_name, data=json.dumps(cleartext_message).encode('utf-8'), key_id=key_id, service_account=service_account, signature=base64.b64encode(data_signed))  
```

The subscriber will use the `key_id` and `service_account` to recall the public key for the signer...then use that to verify the signature.

## Setup


```bash
export PROJECT_ID=`gcloud config get-value core/project`
export PROJECT_NUMBER=`gcloud projects describe $PROJECT_ID --format='value(projectNumber)'`

gcloud pubsub topics create my-new-topic
gcloud pubsub subscriptions create my-new-subscriber --topic=my-new-topic

gcloud iam service-accounts create publisher
gcloud iam service-accounts create subscriber
```

Create keys and download them.  Note, owning keys locally is risky...i'm only doing this here as ademo

```bash
gcloud iam service-accounts keys create publisher.json --iam-account=publisher@$PROJECT_ID.iam.gserviceaccount.com
  created key [b3745702cb47d267c232f609a2614ba274ddf788] of type [json] as [publisher.json] for [publisher@pubsub-msg.iam.gserviceaccount.com]
gcloud iam service-accounts keys create subscriber.json --iam-account=subscriber@$PROJECT_ID.iam.gserviceaccount.com
  created key [9193775e9cae64eb62404875a20c05d44ab4c0bf] of type [json] as [subscriber.json] for [subscriber@pubsub-msg.iam.gserviceaccount.com]
```

Make note of the KeyIDs `b3745702cb47d267c232f609a2614ba274ddf788`, `9193775e9cae64eb62404875a20c05d44ab4c0bf`

Note, you can use use impersonation for the publisher but not subscriber for signing only. This is simply because impersonated service account credentials only supports [signBlob()](https://cloud.google.com/iam/docs/reference/credentials/rest/v1/projects.serviceAccounts/signBlob)  (there is no such thing as `iamcredentials.decryptBlob()`).  Since you can only sign, only the publisher can emit a message for message signature verification
```

To enable this, allow the current user to sign
```bash
  gcloud iam service-accounts  add-iam-policy-binding   --role=roles/iam.serviceAccountTokenCreator \
    --member=user:`gcloud config get-value core/account` publisher@$PROJECT_ID.iam.gserviceaccount.com  
```
If you use impersonation, do not specify the `--cert_service_account` parameter and instead set `--impersonated_service_account=`

## Simple message Encryption

Ok, Now that we're on the same field, lets run through a sample run.  

### Encryption

#### Output

- Publisher

```log
$ python publisher.py  --mode encrypt --project_id $PROJECT_ID --pubsub_topic my-new-topic \
   --recipient subscriber@$PROJECT_ID.iam.gserviceaccount.com --recipient_key_id 3e3afe31e14b530f98b5239cffc3f7808fe983fe

2021-11-14 09:13:44,301 INFO >>>>>>>>>>> Start Encrypt with Service Account Public Key Reference <<<<<<<<<<<
2021-11-14 09:13:44,301 INFO   Using remote public key_id = 3e3afe31e14b530f98b5239cffc3f7808fe983fe
2021-11-14 09:13:44,301 INFO   For service account at: https://www.googleapis.com/service_accounts/v1/metadata/x509/subscriber@mineral-minutia-820.iam.gserviceaccount.com
2021-11-14 09:13:44,679 INFO Generated DEK: {
  "primaryKeyId": 1251169772,
  "key": [
    {
      "keyData": {
        "typeUrl": "type.googleapis.com/google.crypto.tink.AesGcmKey",
        "value": "GiCi767uwFsZ8YhF05g2vcpaHiqI8bENe0fK6MsuJVZSow==",
        "keyMaterialType": "SYMMETRIC"
      },
      "status": "ENABLED",
      "keyId": 1251169772,
      "outputPrefixType": "TINK"
    }
  ]
}
2021-11-14 09:13:44,679 INFO DEK Encrypted Message: AUqTVew3kOVexYZT9yKBCyJJaZnWwU2Oj98PzrUMCtDv4bLuiZW8v/2HWybjAVen0obeVMBSPLQR4p7gTDu4SCmrA90G8UHLczhLKSe22PbukHOY1HciyM0oDGHIlqN3C6TMtifPs32drYFwuTiKLVKHl/Xq+ukFwFMd12zq
2021-11-14 09:13:44,680 INFO Wrapped DEK d2jbxVxug3yfUVfY/2B82mr6JbrGtCS5XAg7aB5vUPaHJFYE/dys+Vy/1H6oXpfOuztBKiPF3f/je3rioEQhiBpMYm/0prRfHZ0FWoBuKGtcD+xeIob3RZNVc3apaFQAJPWQggs6rflKJacnLQTbQFpysd6aaO1NiCu09pdzO0weNtyGp/R3kbV52aKhptuPitw+uewjMcJVwhGA+C52+QgpyGWRq4TLXOdkF2BxYsTBkDR/KYzNtp+MsUdU7ONyDuHo/O5/UjwhODN/SPjyy/dvz6jsYXsT4FcuAKb+pChVGVlYiMIgFd5E4CJLwwMPcSIwk0FOOor/FO2c2Xtonw==
2021-11-14 09:13:44,681 INFO Start PubSub Publish
2021-11-14 09:13:44,681 INFO Published Message: AUqTVew3kOVexYZT9yKBCyJJaZnWwU2Oj98PzrUMCtDv4bLuiZW8v/2HWybjAVen0obeVMBSPLQR4p7gTDu4SCmrA90G8UHLczhLKSe22PbukHOY1HciyM0oDGHIlqN3C6TMtifPs32drYFwuTiKLVKHl/Xq+ukFwFMd12zq
2021-11-14 09:13:45,107 INFO Published MessageID: 3343866723754397
2021-11-14 09:13:45,107 INFO End PubSub Publish
2021-11-14 09:13:45,107 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

Note, we are specifying the `key_id` and email for the **subscriber** (`3e3afe31e14b530f98b5239cffc3f7808fe983fe`)


- Subscriber:

```log
$ python subscriber.py  --mode decrypt --cert_service_account 'subscriber.json' --project_id $PROJECT_ID \
  --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-11-14 09:13:31,369 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-11-14 09:13:46,026 INFO ********** Start PubsubMessage 
2021-11-14 09:13:46,026 INFO Received message ID: 3343866723754397
2021-11-14 09:13:46,026 INFO Received message publish_time: 2021-11-14 14:13:45.007000+00:00
2021-11-14 09:13:46,027 INFO Attempting to decrypt message: b'AUqTVew3kOVexYZT9yKBCyJJaZnWwU2Oj98PzrUMCtDv4bLuiZW8v/2HWybjAVen0obeVMBSPLQR4p7gTDu4SCmrA90G8UHLczhLKSe22PbukHOY1HciyM0oDGHIlqN3C6TMtifPs32drYFwuTiKLVKHl/Xq+ukFwFMd12zq'
2021-11-14 09:13:46,027 INFO   Using service_account/key_id: subscriber@mineral-minutia-820.iam.gserviceaccount.com 3e3afe31e14b530f98b5239cffc3f7808fe983fe
2021-11-14 09:13:46,039 INFO Wrapped DEK d2jbxVxug3yfUVfY/2B82mr6JbrGtCS5XAg7aB5vUPaHJFYE/dys+Vy/1H6oXpfOuztBKiPF3f/je3rioEQhiBpMYm/0prRfHZ0FWoBuKGtcD+xeIob3RZNVc3apaFQAJPWQggs6rflKJacnLQTbQFpysd6aaO1NiCu09pdzO0weNtyGp/R3kbV52aKhptuPitw+uewjMcJVwhGA+C52+QgpyGWRq4TLXOdkF2BxYsTBkDR/KYzNtp+MsUdU7ONyDuHo/O5/UjwhODN/SPjyy/dvz6jsYXsT4FcuAKb+pChVGVlYiMIgFd5E4CJLwwMPcSIwk0FOOor/FO2c2Xtonw==
2021-11-14 09:13:46,040 INFO Decrypted DEK COyrzdQEEmQKWAowdHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuQWVzR2NtS2V5EiIaIKLvru7AWxnxiEXTmDa9yloeKojxsQ17R8royy4lVlKjGAEQARjsq83UBCAB
2021-11-14 09:13:46,040 INFO {
  "primaryKeyId": 1251169772,
  "key": [
    {
      "keyData": {
        "typeUrl": "type.googleapis.com/google.crypto.tink.AesGcmKey",
        "value": "GiCi767uwFsZ8YhF05g2vcpaHiqI8bENe0fK6MsuJVZSow==",
        "keyMaterialType": "SYMMETRIC"
      },
      "status": "ENABLED",
      "keyId": 1251169772,
      "outputPrefixType": "TINK"
    }
  ]
}
2021-11-14 09:13:46,040 INFO Decrypted Message payload: {"data": "foo", "attributes": {"epoch_time": 1636899224, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-11-14 09:13:46,040 INFO ********** End PubsubMessage
```


> The code all this can be found in the Appendix

### Signing

For signing, we do something similar where we're singing just what we would put into the 'data:' field and placing that in a specific PubSubMessage.attribute called ```signature=```

#### Output

- Publisher

Note, we are using the rec

```log
$ python publisher.py  --mode sign --cert_service_account 'publisher.json' --project_id $PROJECT_ID --pubsub_topic my-new-topic \
  --recipient subscriber@$PROJECT_ID.iam.gserviceaccount.com 

2021-11-14 09:14:41,573 INFO >>>>>>>>>>> Start Sign with Service Account <<<<<<<<<<<
2021-11-14 09:14:41,573 INFO data_to_sign +QvtZSuz6v60cQDFz9ngRC19a09Qh6NS2EPntBUWhUE=
2021-11-14 09:14:41,580 INFO Signature: pVAGKt4YO5yOj8SjidPAtnLLENjfOnBnPU4wmmYbnvZY5fVcwv/ZKQ67mFL2IkQnn9+dDzpUgSa3lKNYUw9cI4ElWIP9k76XE8pyyoCSPoYzkBmaKSVoA3BcD0yrp9Ids0DpRP0tYxPdYYKne+H9DJeYofvuiZ4mG2JaGNuUCNJYoCtY+zDzxipj0+4hyjU8gCNA5ehre+d8EIpdT0N1JaFbdJE3MnMnfxdBYbEMBbeKJ5ordzsTeuRxGQxtwauow+dz1/pz1bRyxrlpkvugO4XaBn7y1PwWcw9jCE6T7NeY4O4MxjUJhrtW/tQfs0EDcFA0FzUtjwae+g1eAKe7LQ==
2021-11-14 09:14:41,580 INFO key_id 0e447c01d19c8288743ec73edee55b137891a43c
2021-11-14 09:14:41,580 INFO service_account publisher@mineral-minutia-820.iam.gserviceaccount.com
2021-11-14 09:14:41,580 INFO Start PubSub Publish
2021-11-14 09:14:42,048 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1636899281, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-11-14 09:14:42,261 INFO Published MessageID: 3343866893326339
2021-11-14 09:14:42,261 INFO End PubSub Publish
2021-11-14 09:14:42,261 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```log
$ python subscriber.py  --mode verify --cert_service_account 'subscriber.json' --project_id $PROJECT_ID \
  --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-11-14 09:14:32,075 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-11-14 09:14:43,306 INFO ********** Start PubsubMessage 
2021-11-14 09:14:43,307 INFO Received message ID: 3343866893326339
2021-11-14 09:14:43,307 INFO Received message publish_time: 2021-11-14 14:14:42.256000+00:00
2021-11-14 09:14:43,308 INFO Attempting to verify message: b'{"data": "foo", "attributes": {"epoch_time": 1636899281, "a": "aaa", "c": "ccc", "b": "bbb"}}'
2021-11-14 09:14:43,308 INFO data_to_verify +QvtZSuz6v60cQDFz9ngRC19a09Qh6NS2EPntBUWhUE=
2021-11-14 09:14:43,308 INFO Verify message with signature: pVAGKt4YO5yOj8SjidPAtnLLENjfOnBnPU4wmmYbnvZY5fVcwv/ZKQ67mFL2IkQnn9+dDzpUgSa3lKNYUw9cI4ElWIP9k76XE8pyyoCSPoYzkBmaKSVoA3BcD0yrp9Ids0DpRP0tYxPdYYKne+H9DJeYofvuiZ4mG2JaGNuUCNJYoCtY+zDzxipj0+4hyjU8gCNA5ehre+d8EIpdT0N1JaFbdJE3MnMnfxdBYbEMBbeKJ5ordzsTeuRxGQxtwauow+dz1/pz1bRyxrlpkvugO4XaBn7y1PwWcw9jCE6T7NeY4O4MxjUJhrtW/tQfs0EDcFA0FzUtjwae+g1eAKe7LQ==
2021-11-14 09:14:43,308 INFO   Using service_account/key_id: publisher@mineral-minutia-820.iam.gserviceaccount.com 0e447c01d19c8288743ec73edee55b137891a43c
2021-11-14 09:14:43,355 INFO Message integrity verified
2021-11-14 09:14:43,356 INFO ********** End PubsubMessage
```

If you wanted to use impersonation for the publisher

```log
python publisher.py  --mode sign --impersonated_service_account publisher@$PROJECT_ID.iam.gserviceaccount.com \
  --project_id $PROJECT_ID --pubsub_topic my-new-topic \
  --recipient subscriber@$PROJECT_ID.iam.gserviceaccount.com 
```

then on the subscriber

```log
python subscriber.py  --mode verify --cert_service_account 'subscriber.json' \
    --project_id $PROJECT_ID --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber
```
### the good and the bad   

Ok, now that we went using GCP -provided service account public/private keys

- Plus:
    + Doesn't involve full key distribution; only requires key access at one end of the operation
    + If using local ```.json``` certificate, there is no network round-trip just to sign; everything is done locally
    + IAM impersonation can allow a publisher to sign as a different service_account.
    + Signed messages can be always verified since the public key is available online and referenceable.

- Minus
      - Atleast one participant needs to acquire a key remotely (eg. on verify, download public cert; on encrypt for publisher, acquire public cert at subscriber).  Adds some network latency.
      - Asymmetric key verification is slightly slower than symmetric for verification and decryption
      - Requires coordination publisher publisher and subscriber on which public ```key_id`` to use for encryption; Signing key_id can be transmitted in line.
      - Have to coordinate Key distribution for the ```json``` certificate file.
      - Possible to encrypt or sign a message using a key that has been revoked on the GCP console.   If you have a key ```json``` file in possession, you can use that to sign a message still even if that specific key was revoked on the GCP console and not valid for GCP-API authentication.
      - Possible to encrypt a message using the wrong service account public key.
      - Message attributes are not encrypted or signed (you can work around this by signing recreated canonical json format of the message)
      - RSA messages are larger than symmetric keys (note, Pub/Sub maximum message size is 10MB)

## Conclusion

This is a more complex way to encrypt or sign your messages using GCP's PKI for service accounts. Its nothing new and quite obvious, its basically encrypting an arbitrary message with a specific scheme.  There are clear drawbacks as outlined above among several others.

Can we improve on this?  Lets see if using GCP's [Key Management System (KMS)](https://cloud.google.com/kms/docs/) helps with this in the next set of articles in the series

## Appendix

### References

- [Kinesis Message Payload Encryption with AWS KMS ](https://aws.amazon.com/blogs/big-data/encrypt-and-decrypt-amazon-kinesis-records-using-aws-kms/)
- [Server-Side Encryption with AWS Kinesis](https://aws.amazon.com/blogs/big-data/under-the-hood-of-server-side-encryption-for-amazon-kinesis-streams/)
- [Envelope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption)
- [Python Cryptography](https://cryptography.io/en/latest/)
- [Pub/Sub Message proto](https://github.com/googleapis/googleapis/blob/master/google/pubsub/v1/pubsub.proto#L292)

### Config/Setup

Here is the setup i used in the screenshots below and testing

- Project:  ```esp-demo-197318```
- Service Accounts with JSON certificates
    - Publisher identity:   ```publisher@esp-demo-197318.iam.gserviceaccount.com```
    - Subscriber identity: ```subscriber@esp-demo-197318.iam.gserviceaccount.com```
- KeyRing+Key:  ```projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1```
- PubSub:
    - PUBSUB_TOPIC:  ```projects/esp-demo-197318/topics/my-new-topic```
    - PUBSUB_SUBSCRIPTION ```projects/esp-demo-197318/subscriptions/my-new-subscriber```
