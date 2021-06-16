

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
  "project_id": "mineral-minutia-820",
  "private_key_id": "54927b54123e5b00f5e7ca6e290b3823d545eeb2",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADAXgIU=\n-----END PRIVATE KEY-----\n",
  "client_email": "publisher@mineral-minutia-820.iam.gserviceaccount.com",
  "client_id": "108529726503327553286",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/publisher%40mineral-minutia-820.iam.gserviceaccount.com"
}
```

which has the public key available at a well-known URL (```client_x509_cert_url```):

- x509:
    - [https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@mineral-minutia-820.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@mineral-minutia-820.iam.gserviceaccount.com)
- JWK
    - [https://www.googleapis.com/service_accounts/v1/jwk/publisher@publisher@mineral-minutia-820.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/jwk/publisher@mineral-minutia-820.iam.gserviceaccount.com)


Since the subscriber can download these certs to verify a message, the issue of key-distribution is a bit easier.

Wait....we've got a public key on our hands now...we can use that for encryption too.   In this mode, the publisher uses the public key for the for the _subscriber__ to encrypt a message  (in our case, one of the available keys [here](https://www.googleapis.com/service_accounts/v1/metadata/x509/subscriber@mineral-minutia-820.iam.gserviceaccount.com)).  The subscriber on the other end must have in possession or have the ability to verify the message.  With this technique, you are ensuring confidentiality by encrypting the payload using public/private keys

## Using Service Account Token Creator Role

What we've done here is use a service account to sign the payload. GCP has another mechanism where one service account can _impersonate_ another and sign data on its behalf.  This is useful if you want to mint a message on behalf of another service account.   If you want more information on this variation and code samples, see:

- [Service Account impersonation](https://github.com/salrashid123/gcpsamples/tree/master/auth/tokens)
- [iam.signJwt()](https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts/signJwt)
- [iam.signBlob()](https://cloud.google.com/iam/reference/rest/v1/projects.serviceAccounts/signBlob)

### Encrypted message Formatter

Please refer to the first article on the series for the format basics.  The variation describe in this technique has a slight extension to account for the service_account:

What this technique does is encrypts that entirely as the message ```data``` and _then_ add the service_account the message is intended for  (```service_account=args.recipient```) as well ask hint for the ```key_id`` used.

the snippet in python is:
```python
publisher.publish(topic_name, data=encrypted_payload.encode(), service_account=args.recipient, key_id=args.recipient_key_id)
```

### Signed message Formatter

Similar to the first article, we will be signing the message you users intended to send and then embedding the signature in a Pub/Sub Message attribute called ```signature=```:

the snippet in python is:
```python
  publisher.publish(topic_name, data=json.dumps(plaintext_message), key_id=key_id, service_account=service_account, signature=data_signed)
```

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

## Simple message Encryption

Ok, Now that we're on the same field, lets run through a sample run.  

### Encryption

We're going to use the **DIFFERENT** service accounts as the publisher and subscriber already use as authorization to GCP. 

#### Output

- Publisher

```log
$ python publisher.py  --mode encrypt --project_id $PROJECT_ID --pubsub_topic my-new-topic \
   --recipient subscriber@$PROJECT_ID.iam.gserviceaccount.com --recipient_key_id 9193775e9cae64eb62404875a20c05d44ab4c0bf

2021-06-16 08:55:35,110 INFO >>>>>>>>>>> Start Encrypt with Service Account Public Key Reference <<<<<<<<<<<
2021-06-16 08:55:35,110 INFO   Using remote public key_id = 9193775e9cae64eb62404875a20c05d44ab4c0bf
2021-06-16 08:55:35,110 INFO   For service account at: https://www.googleapis.com/service_accounts/v1/metadata/x509/subscriber@pubsub-msg.iam.gserviceaccount.com
2021-06-16 08:55:35,113 DEBUG Starting new HTTPS connection (1): www.googleapis.com:443
2021-06-16 08:55:35,176 DEBUG https://www.googleapis.com:443 "GET /service_accounts/v1/metadata/x509/subscriber@pubsub-msg.iam.gserviceaccount.com HTTP/1.1" 200 1699
2021-06-16 08:55:35,181 INFO Start PubSub Publish
2021-06-16 08:55:35,182 DEBUG Checking None for explicit credentials as part of auth process...
2021-06-16 08:55:35,183 DEBUG Checking Cloud SDK credentials as part of auth process...
2021-06-16 08:55:35,735 INFO Published Message: b'WSP8L7zeKm+hpHq9kT0XYID7vQfsd0MRPlvWX2uosSZGKfBPhZOSAU+tfSGh3Ro/5GaWzpGr/wY9qLWZJG1zrgthBwcr1r4Jl/VVq5ew4mmsFWqBCFT2WO8UUQdnKHSSSPCAPSsxu/QjOBeXMtTV3gIeZBA5MZMuwCXEFSU/M55sQOsAp4s0nDvYgDMFj4IbCZxusdkNqx4YXvfEcNxQ7U+UiPO6f8kpLMUEKX5e2EsBgxsIpY85XY1Daya+1kkwHhsFm+n6pBo2nOWFLUxjr2U94+CZyOiyEIMSp6gsTvJR8rsL/NN42rQtocHkbkugp1zFSTX0zncaPzQzx+kmDg=='
2021-06-16 08:55:35,745 DEBUG Commit thread is waking up
2021-06-16 08:55:35,789 DEBUG Making request: POST https://oauth2.googleapis.com/token
2021-06-16 08:55:35,790 DEBUG Starting new HTTPS connection (1): oauth2.googleapis.com:443
2021-06-16 08:55:35,895 DEBUG https://oauth2.googleapis.com:443 "POST /token HTTP/1.1" 200 None
2021-06-16 08:55:36,152 DEBUG gRPC Publish took 0.40624403953552246 seconds.
2021-06-16 08:55:36,154 INFO Published MessageID: 2543298155594522
2021-06-16 08:55:36,154 INFO End PubSub Publish
2021-06-16 08:55:36,154 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

Note, we are specifying the `key_id` and email for the **subscriber** (`9193775e9cae64eb62404875a20c05d44ab4c0bf`)


- Subscriber:

```log
$ python subscriber.py  --mode decrypt --cert_service_account '../subscriber.json' --project_id $PROJECT_ID --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-06-16 08:51:36,454 INFO Listening for messages on projects/pubsub-msg/subscriptions/my-new-subscriber
2021-06-16 08:55:37,120 INFO ********** Start PubsubMessage 
2021-06-16 08:55:37,121 INFO Received message ID: 2543298155594522
2021-06-16 08:55:37,121 INFO Received message publish_time: 2021-06-16 12:55:36.123000+00:00
2021-06-16 08:55:37,121 INFO Attempting to decrypt message: b'"WSP8L7zeKm+hpHq9kT0XYID7vQfsd0MRPlvWX2uosSZGKfBPhZOSAU+tfSGh3Ro/5GaWzpGr/wY9qLWZJG1zrgthBwcr1r4Jl/VVq5ew4mmsFWqBCFT2WO8UUQdnKHSSSPCAPSsxu/QjOBeXMtTV3gIeZBA5MZMuwCXEFSU/M55sQOsAp4s0nDvYgDMFj4IbCZxusdkNqx4YXvfEcNxQ7U+UiPO6f8kpLMUEKX5e2EsBgxsIpY85XY1Daya+1kkwHhsFm+n6pBo2nOWFLUxjr2U94+CZyOiyEIMSp6gsTvJR8rsL/NN42rQtocHkbkugp1zFSTX0zncaPzQzx+kmDg=="'
2021-06-16 08:55:37,123 INFO   Using service_account/key_id: subscriber@pubsub-msg.iam.gserviceaccount.com 9193775e9cae64eb62404875a20c05d44ab4c0bf
2021-06-16 08:55:37,130 INFO Decrypted Message payload: {"data": "foo", "attributes": {"epoch_time": 1623848135, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 08:55:37,131 INFO ********** End PubsubMessage 
```


> The code all this can be found in the Appendix

### Signing

For signing, we do something similar where we're singing just what we would put into the 'data:' field and placing that in a specific PubSubMessage.attribute called ```signature=```

#### Output

- Publisher

Note, we are using the rec
```log
$ python publisher.py  --mode sign --cert_service_account '../publisher.json' --project_id $PROJECT_ID --pubsub_topic my-new-topic \
  --recipient subscriber@$PROJECT_ID.iam.gserviceaccount.com 

2021-06-16 09:08:25,179 INFO >>>>>>>>>>> Start Sign with Service Account json KEY <<<<<<<<<<<
2021-06-16 09:08:25,184 INFO Signature: U7mmIY+sY96TjH3SE/PB61NTLcctyQuuOQgbONtoo+98DEH1YEjlL+0HzznqsXktM0l61rO+ALZ9XLGX+bJN73adop16a8ih0YMOrL+26IhZLQzOsaYA+YXMbkB9/DyarQ1odnYzstNewR1ZQHNVncq2hiX+OwjIaa04GnV7p5XPOeFJcLRvWSiuXDAp69Mh3+VMNCPkX65UedkVbl3q5qL9gUFx8ZGAyx+Y7kaqmEjJJu1G0Y4OhNrxBjQv1zwj3Fna/6GykuwvhoI8Or9yRhlt39RhVA72QMfNCVwPDhkZcqOohFwMOoPk6tmoTKjS7pkaJ62T4XAlYWM4T0A8ng==
2021-06-16 09:08:25,184 INFO Start PubSub Publish
2021-06-16 09:08:25,184 DEBUG Checking None for explicit credentials as part of auth process...
2021-06-16 09:08:25,184 DEBUG Checking Cloud SDK credentials as part of auth process...
2021-06-16 09:08:25,708 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623848905, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:08:25,718 DEBUG Commit thread is waking up
2021-06-16 09:08:25,754 DEBUG Making request: POST https://oauth2.googleapis.com/token
2021-06-16 09:08:25,763 DEBUG Starting new HTTPS connection (1): oauth2.googleapis.com:443
2021-06-16 09:08:25,910 DEBUG https://oauth2.googleapis.com:443 "POST /token HTTP/1.1" 200 None
2021-06-16 09:08:26,021 DEBUG gRPC Publish took 0.3017094135284424 seconds.
2021-06-16 09:08:26,022 INFO Published MessageID: 2543421296695615
2021-06-16 09:08:26,022 INFO End PubSub Publish
2021-06-16 09:08:26,022 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```log
$ python subscriber.py  --mode verify --cert_service_account '../subscriber.json' --project_id $PROJECT_ID --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-06-16 09:08:08,791 INFO Listening for messages on projects/pubsub-msg/subscriptions/my-new-subscriber
2021-06-16 09:08:26,063 INFO ********** Start PubsubMessage 
2021-06-16 09:08:26,064 INFO Received message ID: 2543421296695615
2021-06-16 09:08:26,064 INFO Received message publish_time: 2021-06-16 13:08:26.015000+00:00
2021-06-16 09:08:26,064 INFO Attempting to verify message: b'{"data": "foo", "attributes": {"epoch_time": 1623848905, "a": "aaa", "c": "ccc", "b": "bbb"}}'
2021-06-16 09:08:26,064 INFO Verify message with signature: U7mmIY+sY96TjH3SE/PB61NTLcctyQuuOQgbONtoo+98DEH1YEjlL+0HzznqsXktM0l61rO+ALZ9XLGX+bJN73adop16a8ih0YMOrL+26IhZLQzOsaYA+YXMbkB9/DyarQ1odnYzstNewR1ZQHNVncq2hiX+OwjIaa04GnV7p5XPOeFJcLRvWSiuXDAp69Mh3+VMNCPkX65UedkVbl3q5qL9gUFx8ZGAyx+Y7kaqmEjJJu1G0Y4OhNrxBjQv1zwj3Fna/6GykuwvhoI8Or9yRhlt39RhVA72QMfNCVwPDhkZcqOohFwMOoPk6tmoTKjS7pkaJ62T4XAlYWM4T0A8ng==
2021-06-16 09:08:26,064 INFO   Using service_account/key_id: publisher@pubsub-msg.iam.gserviceaccount.com b3745702cb47d267c232f609a2614ba274ddf788
2021-06-16 09:08:26,118 INFO Message integrity verified
2021-06-16 09:08:26,118 INFO ********** End PubsubMessage 
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

### Code


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
