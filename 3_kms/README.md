

# Message Payload Encryption in Google Cloud PubSub (Part 3: Google Key Management System exclusively)

## Introduction

This is the third in a series exploring how to encrypt the message data payload within a Google Pub/Sub message.  This will not go into any real detail on the situations _why_ you want to ensure confidentiality or integrity of a given message but many of them were discussed in the first part of the series.   If you haven't already, please do read atleat the introduction section in the first part.

Anyway, what we've covered so far is a form of simple symmetric encryption where the sender and receiver are both using a static key.  We've also explored one way to use Google Cloud's service account public/private keys to sign and encrypt a message.   There are some advantages and disadvantages to these approaches as was outlined in those article.  We're here to see if we can improve on it or develop a different technique using Google's managed [Key Management System](https://cloud.google.com/kms/).

So, instead of sharing a symmetric key or overriding a PKI system, can we use the KMS system to encrypt the data itself?

## What exactly are we encrypting and signing?

This technique relies on the publisher having access to a KMS key to encrypt and the subscriber access to the __same__ key to decrypt a message.  We will be encrypting the *entire* message with KMS so there are not encryption keys in transit.  

We will be using this to encrypt and HMAC sign for confidentiality and integrity/authentication (respectively).

As mentioned, in-terms of what we're encrypting and signing, its the whole message done entirely on KMS (no local key generation or using a service accounts certificate/keys).  There several disadvantages to this as outlined at the end but lets go through this anyway.

### Encrypted message Formatter

For encrypted message, we need to transmit the message itself with the signature. For verification, we need will extract the signature in the header and compare. As was the case with encryption, we are verifying the payload within the ```data``` field.  As above, there maybe a variation between the Pub/SubMessage attributes and the attributes embedded in the data payload:

```json
_json_message = {
    "data": "foo",
    "attributes": {
      "attribute1": "value1",
      "attribute2": "value2"    
    }
  }
```

So as transmitted Pub/SubMessage would be:

```json
data:  encrypted(json_message)
attributes:  
    kms_key: (kms_keyid)
```

## Encryption

Ok, so how does this work?  Its pretty straight forward:

- Take the message you intended to send and make an KMS API call to encrypt it.
- Send the encrypted message in the Pub/Sub ```data:``` field and optionally specify a reference to the KMS key_id to use as a hint to the subscriber.

Easy enough, right?  Yes its too easy but has some severe practical limitations for high-volume, high-frequency PubSub messages


## Signing

We use KMS MAC keys to sign and verify,.

The signed message looks like this

```json
data:  _json_message
attributes:  
    kms_key: (kms_keyid)
    signature: hmac(sha256(json_message))
```


## Setup


```bash
export PROJECT_ID=`gcloud config get-value core/project`
export PROJECT_NUMBER=`gcloud projects describe $PROJECT_ID --format='value(projectNumber)'`

gcloud pubsub topics create my-new-topic
gcloud pubsub subscriptions create my-new-subscriber --topic=my-new-topic

gcloud iam service-accounts create publisher
gcloud iam service-accounts create subscriber

gcloud kms keyrings create mykeyring  --location=us-central1
gcloud kms keys create key1 --keyring=mykeyring --purpose=encryption --location=us-central1
gcloud kms keys create key2 --keyring=mykeyring --purpose=mac --default-algorithm=hmac-sha256 --location=us-central1
```

### Output

The following sample assumes you have IAM permissions to

* a. publish to topic `my-new-topic`
* b. subscribe on `my-new-subscriber`
* c. encrypt/hmac with kms `key1`
* d. decrypt/verify with kms `key2`

If you want to run using the two service accounts created above, you should grant the `publisher` permissions `a` and `c` while the `subscriber` should have permissions `b`, `d`.
##### Encryption

- Publisher
```log
$ python publisher.py  --mode=encrypt --project_id $PROJECT_ID --pubsub_topic my-new-topic  --kms_location_id us-central1 --kms_key_ring_id mykeyring --kms_crypto_key_id key1

2021-11-14 09:17:42,482 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-11-14 09:17:42,965 INFO Start KMS encryption API call
2021-11-14 09:17:43,412 INFO End KMS encryption API call
2021-11-14 09:17:43,413 INFO Start PubSub Publish
2021-11-14 09:17:43,414 INFO Published Message: CiUAmT+VVQyCYfCbVH0OWPeWSvBcYEXPFbEH30SG6AI/nq7mxWMPEoYBABBpW9AoUe2HrcpurOdup0CoZF8QlNocdgK+NgLAB2VOu3cpAoWLmGSxcljmGRI9NzJGtu2Tt/GUWxPoT6NLRBpky8umMGPv20gpgtKyEPbhorjNZvD4WGrNRhwrifl25U1UWgRKUEfTqUJkFPaGFdszbP0Krt6rg0+dO6GGc30XohhDe0o=
2021-11-14 09:17:43,801 INFO Published MessageID: 3343866587961712
2021-11-14 09:17:43,801 INFO End PubSub Publish
2021-11-14 09:17:43,801 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```log
$ python subscriber.py  --mode decrypt --project_id $PROJECT_ID --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber 

2021-11-14 09:17:35,643 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-11-14 09:17:43,876 INFO ********** Start PubsubMessage 
2021-11-14 09:17:43,877 INFO Received message ID: 3343866587961712
2021-11-14 09:17:43,877 INFO Received message publish_time: 2021-11-14 14:17:43.653000+00:00
2021-11-14 09:17:43,877 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-11-14 09:17:43,877 INFO Starting KMS decryption API call
2021-11-14 09:17:44,276 INFO End KMS decryption API call
2021-11-14 09:17:44,276 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1636899462, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-11-14 09:17:44,277 INFO ACK message
2021-11-14 09:17:44,277 INFO End AES decryption
2021-11-14 09:17:44,277 INFO ********** End PubsubMessage 
```


##### Signing

```log
$ python publisher.py  --mode=sign --project_id $PROJECT_ID --pubsub_topic my-new-topic  \
  --kms_location_id us-central1 --kms_key_ring_id mykeyring --kms_crypto_key_id key2 --kms_crypto_key_version=1

2021-11-14 09:18:16,702 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-11-14 09:18:17,187 INFO Start KMS mac API call
2021-11-14 09:18:17,188 INFO data_to_sign e3Tz5WJQcnnZJjiI+WHWPuqikqrY51TAzaZQPxXk5Ig=
2021-11-14 09:18:17,591 INFO End KMS mac API call
2021-11-14 09:18:17,591 INFO MAC: FMNvird1CWtHikzwLyr3hOE91RgG08+S9wTDhRCkD0E=
2021-11-14 09:18:17,591 INFO Start PubSub Publish
2021-11-14 09:18:18,006 INFO Published MessageID: 3343867410411934
2021-11-14 09:18:18,006 INFO End PubSub Publish
2021-11-14 09:18:18,006 INFO >>>>>>>>>>> END <<<<<<<<<<<
```


```log
$ python subscriber.py  --mode verify --project_id $PROJECT_ID --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-11-14 09:18:19,000 INFO ********** Start PubsubMessage 
2021-11-14 09:18:19,001 INFO Received message ID: 3343867410411934
2021-11-14 09:18:19,001 INFO Received message publish_time: 2021-11-14 14:18:17.908000+00:00
2021-11-14 09:18:19,001 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key2/cryptoKeyVersions/1
2021-11-14 09:18:19,001 INFO Starting HMAC
2021-11-14 09:18:19,002 INFO Verify message: b'{"data": "foo", "attributes": {"epoch_time": 1636899496, "a": "aaa", "c": "ccc", "b": "bbb"}}'
2021-11-14 09:18:19,002 INFO data_to_verify e3Tz5WJQcnnZJjiI+WHWPuqikqrY51TAzaZQPxXk5Ig=
2021-11-14 09:18:19,002 INFO   With HMAC: FMNvird1CWtHikzwLyr3hOE91RgG08+S9wTDhRCkD0E=
2021-11-14 09:18:19,434 INFO MAC verified 
2021-11-14 09:18:19,435 INFO ********** End PubsubMessage
```


### the good and the bad

Ok, now that we went through all this...what are the issues with this approach:

- Plus:
    + All encryption is done on GCP; no need
    + No need for key distribution; key rotation, key management.
    + Access to encrypt/decrypt functions is configurable with IAM policies alone

- Minus
    - Extra network call to encrypt and decrypt (adds latency)
    - Additional costs with KMS api operations.
    - KMS is configured by [regions](https://cloud.google.com/kms/docs/locations). You may need to account for latency in remote API calls from the producer or subscriber.
    - Need to stay under PubSub maximum message size of 10GB
    - Dependency on the availably of another Service (in this case KMS)

## Conclusion

This is a simple way to encrypt or sign your messages with GCP's [Key Management System (KMS)](https://cloud.google.com/kms/docs/).  Its not doing anything particularly novel but shows you how to use KMS alone to encrypt/decrypt.

Ultimately, this isn't feasible or practical: for a service like pub/sub where latency is important, why add on this extra network dependency?

Right...so is there anyway we can iterate on this idea?   Yep, we can mitigate some of the network issues by using another technique that is a hybrid of the ones cited in the previous thread.  We'll cover that in the next and final article

## Appendix

### Code


### References

- [Kinesis Message Payload Encryption with AWS KMS ](https://aws.amazon.com/blogs/big-data/encrypt-and-decrypt-amazon-kinesis-records-using-aws-kms/)
- [Server-Side Encryption with AWS Kinesis](https://aws.amazon.com/blogs/big-data/under-the-hood-of-server-side-encryption-for-amazon-kinesis-streams/)
- [Envelope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption)
- [Python Cryptography](https://cryptography.io/en/latest/)
- [PubSub Message proto](https://github.com/googleapis/googleapis/blob/master/google/pubsub/v1/pubsub.proto#L292)
---


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
