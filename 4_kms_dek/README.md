

# Message Payload Encryption in Google Cloud Pub/Sub (Part 4: Envelope Encryption with Google Key Management System and PubSub)

## Introduction

In this mode, each pubsub message is encrypted by a symmetric key which is itself wrapped by a KMS key reference.

That is, if the original pubsub message looks like:

```json
_json_message = {
    "data": "foo",
    "attributes": {
      "attribute1": "value1",
      "attribute2": "value2"    
    }
  }
```

The wrapped message delivered to each subscriber would be:


```json
_json_message = {
    "data": "tjnGOdgyWib3qdrg4Hn+5OAStpq52Gaaz74MyrfewXbKE2BCleROKsUDQxmxUDbpLEAXg2DF15mzrkQe65358KM4uj/tS/",
    "attributes": {
      "kms_key": "projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1",
      "dek_wrapped": "aaseMYA+6QqoVVl7+qs3H10qyp5eSzvz4EAib998s2M="    
    }
  }
```


Basically, this is another layer of [Envelope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption) where what you're actually encrypting with KMS is the symmetric key you used to encrypt the PubsubMessage.  Once the key you used to encrypt your Pubsub data (data encryption key: DEK), you transmit the KMS-encrypted DEK along with the message itself.  

On the subscriber side, you get a KMS encrypted DEK and the message that is encrypted by the DEK.  You use KMS to unwrap the DEK and then finally use the plaintext DEK to decrypt the Pub/SubMessage.

One variation is that the DEK itself can be rotated by the publisher while the subscriber can expire its cache of known keys.

The publisher can pick a DEK for say 100 messages, transmit them and then create a new DEK.   Since the wrapped KMSEncrypted(DEK) is a message attribute, the subscriber can setup a local cache of KMSEncrypted(DEK)-> decrypted(DEK) map.  If it sees a wrapped DEK that it has in cache, it can "just decrypt' the message data.  If it does not see the wrapped dek in cache, it can make a KMS call to decrypt the new key and then save it in cache.



### Encryption

We're going to use the **SAME** service accounts as the publisher and subscriber already use as authorization to GCP.  You are ofcourse do not have to use the same ones..infact, for encryption, you can use the public key for any recipient on any project!


To recap how to use this mode:

First ensure you have two service accounts JSON files handy as `publisher.json` and `subscriber.json`:

`publisher@PROJECT.iam.gserviceaccount.com`, `subscriber@PROJECT.iam.gserviceaccount.com`

A topic and a subscriber on that topic:
topic: `my-new-topic`
subscription: `my-new-subscriber`

```
$ gcloud pubsub topics list-subscriptions my-new-topic
---
  projects/PROJECT/subscriptions/my-new-subscriber
```

Set IAM bindings 
```
$ gcloud pubsub topics get-iam-policy my-new-topic
bindings:
- members:
  - serviceAccount:publisher@PROJECT.iam.gserviceaccount.com

$ gcloud pubsub subscriptions get-iam-policy my-new-subscriber
bindings:
- members:
  - serviceAccount:subscriber@PROJECT.iam.gserviceaccount.com
  role: roles/pubsub.subscriber
```

The KMS keyring `mykeyring` with an Encrption/Decrption key, `key`:

```
$ gcloud kms keys get-iam-policy --keyring mykeyring --location us-central1 key1
bindings:
- members:
  - serviceAccount:subscriber@PROJECT.iam.gserviceaccount.com
  role: roles/cloudkms.cryptoKeyDecrypter
- members:
  - serviceAccount:publisher@PROJECT.iam.gserviceaccount.com
  role: roles/cloudkms.cryptoKeyEncrypter

```

Anyway..

#### Output for Encryption

- Publisher
```bash
$ python publisher.py  --mode encrypt --service_account publisher.json --kms_project_id mineral-minutia-820  --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id mineral-minutia-820

2020-03-23 14:31:26,297 INFO URL being requested: GET https://www.googleapis.com/discovery/v1/apis/cloudkms/v1/rest
2020-03-23 14:31:26,434 INFO >>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<
2020-03-23 14:31:26,434 INFO Rotating symmetric key
2020-03-23 14:31:26,434 INFO Starting KMS encryption API call
2020-03-23 14:31:26,449 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:encrypt?alt=json
2020-03-23 14:31:26,682 INFO End KMS encryption API call
2020-03-23 14:31:26,683 INFO Start PubSub Publish
2020-03-23 14:31:26,698 INFO Published Message: tjnGOdgyWib3qdrg4Hn+5OAStpq52Gaaz74MyrfewXbKE2BCleROKsUDQxmxUDbpLEAXg2DF15mzrkQe65358KM4uj/tS/0r96RaoSqGCmqNisDuTAv0cOMcB8Aglxf6roTXlhwiDyCJQqGrs6AA+w==
2020-03-23 14:31:26,699 INFO End PubSub Publish
2020-03-23 14:31:26,699 INFO >>>>>>>>>>> END <<<<<<<<<<<

```

- Subscriber:
```bash
$ python subscriber.py  --mode decrypt --service_account subscriber.json --pubsub_project_id mineral-minutia-820 --kms_project_id mineral-minutia-820 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 

ImportError: file_cache is unavailable when using oauth2client >= 4.0.0 or google-auth
2020-03-23 14:31:23,467 INFO URL being requested: GET https://www.googleapis.com/discovery/v1/apis/cloudkms/v1/rest
2020-03-23 14:31:23,632 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2020-03-23 14:31:23,634 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2020-03-23 14:31:27,632 INFO ********** Start PubsubMessage 
2020-03-23 14:31:27,632 INFO Received message ID: 444703597866455
2020-03-23 14:31:27,633 INFO Starting KMS decryption API call
2020-03-23 14:31:27,636 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:decrypt?alt=json
2020-03-23 14:31:27,898 INFO End KMS decryption API call
2020-03-23 14:31:27,899 INFO Decrypted data {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1584988286}, "data": "foo"}
2020-03-23 14:31:27,899 INFO ********** End PubsubMessage 

```

> The code all this can be found in the Appendix



### Signing

For signing, we do something similar where we're singing just what we would put into the ```data:``` field and placing that in a specific PubSubMessage.attribute called ```signature=``` with the signature of the data and other attributes as sturct.

#### Output

- Publisher

```bash
$ python publisher.py  --mode sign --service_account publisher.json --kms_project_id mineral-minutia-820  --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id mineral-minutia-820

2020-03-23 14:32:33,110 INFO URL being requested: GET https://www.googleapis.com/discovery/v1/apis/cloudkms/v1/rest
2020-03-23 14:32:33,269 INFO >>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<
2020-03-23 14:32:33,269 INFO Rotating key
2020-03-23 14:32:33,331 INFO Starting KMS encryption API call
2020-03-23 14:32:33,335 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:encrypt?alt=json
2020-03-23 14:32:33,564 INFO End KMS encryption API call
2020-03-23 14:32:33,565 INFO Start PubSub Publish
2020-03-23 14:32:33,577 INFO Published Message: {'attributes': {'a': 'aaa', 'c': 'ccc', 'b': 'bbb', 'epoch_time': 1584988353}, 'data': 'foo'}
2020-03-23 14:32:33,577 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2020-03-23 14:32:33,578 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```
$  python subscriber.py  --mode verify --service_account subscriber.json --pubsub_project_id mineral-minutia-820 --kms_project_id mineral-minutia-820 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 

2020-03-23 14:32:25,342 INFO URL being requested: GET https://www.googleapis.com/discovery/v1/apis/cloudkms/v1/rest
2020-03-23 14:32:25,670 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2020-03-23 14:32:25,673 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2020-03-23 14:32:34,090 INFO ********** Start PubsubMessage 
2020-03-23 14:32:34,090 INFO Received message ID: 444703370594175
2020-03-23 14:32:34,091 INFO Starting KMS decryption API call
2020-03-23 14:32:34,094 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:decrypt?alt=json
2020-03-23 14:32:34,331 INFO End KMS decryption API call
2020-03-23 14:32:34,332 INFO Message authenticity verified

```

## Execution Latency

I ran the full end to end tests here on a GCE instance and on my laptop from home.  I did this to compare the latency it took to run the KMS operation and intentionally did not pay attention to the time for  the pubsub calls or  local key generation.

The reasons are fairly obvious: I wanted to gauge the relative network latency (even for one single call over a laptop/home connection).

What the output below shows is the subscriber side when a message is received.  It shows the pubsub message, the KMS decryption and then the AES decryption.

> Note, all this is empirical and the numbers cited is just for one single API call.

### GCE

On GCE, the latency it took to unwrap the AES key from the KMS call was:

- ```Encrypt```:

19:16:08,596 --> 19:16:08,715  about  10ms

- ```Decrypt```:

19:16:11,033 --> 19:16:11,149 about 10ms

### Local

On my laptop from home, the latency it took to unwrap the AES key from the KMS call was:

- ```Encrypt```:

14:46:54,308 --> 14:46:54,930 about 60ms

- ```Decrypt```:

14:46:59,438 --> 14:47:00,159 about 70ms

## Local Encryption and Cached Keys

There is going to be added network latency and other costs of using KMS.  One way to reduce the costs is to cache a symmetric key and expire it every now and then.   That is, the publisher can generate a symmetric key, use KMS to wrap it and keep using it for N seconds.   The subscriber would have to be notified of the expiration and lifetime but what that minimizes KMS api calls and also gives you fast symmetric key operations!

Basically, you are creating key, using KMS to wrap the key and save it in an ```ExpiringDict``` as shown below.

```python
from expiringdict import ExpiringDict

cache = ExpiringDict(max_len=100, max_age_seconds=60)
```

When you need to invoke a pubsub message, just use that cached key locally: no need for KMS.  Once the key expires, regenerate the key again and wrap it into the dict.  Rinse and Repeat.



## KMS wrapped encryption key on GCS

You are also free to use [GCS to store KMS wrapped secrets](https://medium.com/google-cloud/gcs-kms-and-wrapped-secrets-e5bde6b0c859).  As described in that article, you can save a symmetric key on GCS, secure it via GCS IAM rules and allow publisher and subscriber to encrypt/decrypt as normal.  Its not really going to buy you much here since you also now have to use GCS to download the key.   You're also back to the symmetric key issue:  you've just added in more step to make that harder...and since there are several more steps in the process now (and more things to break), its likely the key rotation wont' happen as frequently.   I wouldn't now recommend this variation for this usecase.

### the good and the bad

Ok, now that we went through all this...what are the issues with this approach:

- Plus:
    + All encryption is done on GCP; no need
    + No need for key distribution; key rotation, key management.
    + Access to encrypt/decrypt functions is configurable with IAM policies alone

- Minus
    - Extra network call to encrypt and decrypt.
    - Additional costs with KMS api operations.
    - Slower (due to network hops).
    - KMS is configured by [regions](https://cloud.google.com/kms/docs/locations). You may need to account for latency in remote API calls from the producer or subscriber.     
    - Need to stay under PubSub maximum message size of 10MB
    - Dependency on the availability of another Service (in this case KMS)



## Conclusion

I've covered four techniques to encrypt your PubSub messages; some ideas are basic, some are good, some are bad.  I attempted to explain the pro/cons of each just to document.  My 2c is try going with kms+cache+symmetric keys as described here if the publisher and subscriber agree to a protocol..  You will reap the benefits of KMS entirely and provide a mechanism to ensure integrity and confidentially.  One obvious thing is the protocol for the message payload is something i just made up (i.e, saving the signature in a specific message attribute).  You are ofcourse welcome to use any scheme you want.



## Appendix

### Code

### References

- [Kinesis Message Payload Encryption with AWS KMS ](https://aws.amazon.com/blogs/big-data/encrypt-and-decrypt-amazon-kinesis-records-using-aws-kms/)
- [Server-Side Encryption with AWS Kinesis](https://aws.amazon.com/blogs/big-data/under-the-hood-of-server-side-encryption-for-amazon-kinesis-streams/)
- [Envelope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption)
- [Python Cryptography](https://cryptography.io/en/latest/)
- [PubSub Message proto](https://github.com/googleapis/googleapis/blob/master/google/pubsub/v1/pubsub.proto#L292)

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

### Cloud KMS

The following describes the KMS setup in this article.  The steps outline how to create a KMS keyring, key and then set IAM permissions on that key so that the publisher can encrypt and the
subscriber can decrypt.  For this test, we enable IAM permission such that

- ```publisher@esp-demo-197318.iam.gserviceaccount.com``` can Encrypt
- ```subscriber@esp-demo-197318.iam.gserviceaccount.com``` can Decrypt

![images/kms_permissions.png](images/kms_permissions.png)

### PubSub

We do a similar configuration on the Pubsub side

setup a topic which to which you grant ```publisher@esp-demo-197318.iam.gserviceaccount.com``` the ability to post messages

![images/topic_permissions.png](images/topic_permissions.png)

and a subscription against that topic where ```projects/esp-demo-197318/subscriptions/my-new-subscriber``` can pull messages.

![images/subscription_permissions.png](images/subscription_permissions.png)
