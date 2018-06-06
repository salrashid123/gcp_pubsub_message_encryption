

# Message Payload Encryption in Google Cloud Pub/Sub (Part 4: Envelope Encryption with Google Key Management System and PubSub)

## Introduction


One option discussed here is using Google hosted key management system, [Cloud KMS](https://cloud.google.com/kms/docs/).  What KMS will do is provide a service to remotely encrypt and decrypt some text.   What that text actually is would not be the actual Pub/Sub message payload but rather a AES key used to encrypt the pubsub message itself.  (besides, you don't want to use KMS to encrypt the whole pubsub message which can be upto 10MB!).

What you're doing here is [Envelope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption) where what you're actually encrypting with KMS is the symmetric key you used to encrypt the PubsubMessage.  Once the key you used to encrypt your Pubsub data (data encryption key: DEK), you transmit the KMS-encrypted DEK along with the message itself.  

On the subscriber side, you get a KMS encrypted DEK and the message that is encrypted by the DEK.  You use KMS to unwrap the DEK and then finally use the plaintext DEK to decrypt the Pub/SubMessage.

There are several shortcomings to this whole approach: 1. is it necessary to do all this (it depends..most/almost all customers dont' need to).. and 2. what is the added latency, cost associated with this (there is some latency since we're making another round trip to KMS...and the costs of KMS operations too)

Anyway, lets move on.

---

### Encrypted message Formatter

Please refer to the first article on the series for the format basics.  The variation describe in this technique has a slight extension to account for the service_account:

What this technique does is encrypts that entirely as the message ```data``` and _then_ add ```kms_key=``` you used as well as the actual encrypted message (```dek_encrypted```).

the snippet in python is:
```python
publisher.publish(topic_name, data=encrypted_message.encode('utf-8'), kms_key=name, dek_wrapped=dek_encrypted)
```

### Signed message Formatter

Similar to the first article, we will be signing the message you users intended to send and then embedding the wrapped key as the ```key=``` attribute and the```signature=``` attributecontainig the corresponding signature

the snippet in python is:
```python
  publisher.publish(topic_name, data=json.dumps(cleartext_message), kms_key=name, sign_key_wrapped=sign_key_wrapped, signature=msg_hash)
```


## Simple message Encryption

Ok, Now that we're on the same field, lets run through a sample run.  


### Encryption

We're going to use the **SAME** service accounts as the publisher and subscriber already use as authorization to GCP.  You are ofcourse do not have to use the same ones..infact, for encryption, you can use the public key for any recipient on any project!

Anyway..

#### Output

- Publisher
```
$ python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1
2018-06-03 10:29:36,092 INFO >>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<
2018-06-03 10:29:36,092 INFO Generated dek: ZMZrRoXHTubd+GqBlV8C7B7QxrvvFEbryGyiDTW1I2A=
2018-06-03 10:29:36,092 INFO Starting AES encryption
2018-06-03 10:29:36,093 INFO End AES encryption
2018-06-03 10:29:36,093 INFO Encrypted Message with dek: 6aSUI7RZ812KBsEdvjgr7u/Jc2uUu1OiZ9bTpAYWlE1ySUxIdQ2J4ndeBe7NjzhNaU+lf2juVaKyI/8Yj53/SncMyWuAGi7aii6M9K+o2CuXSJb1RJYXE5Y9XzRc9jt5xvzlmfA7S/VeT10xuSr7hw==
2018-06-03 10:29:36,093 INFO Starting KMS encryption API call
2018-06-03 10:29:36,099 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:encrypt?alt=json
2018-06-03 10:29:36,101 DEBUG Making request: POST https://accounts.google.com/o/oauth2/token
2018-06-03 10:29:36,758 INFO End KMS encryption API call
2018-06-03 10:29:36,758 INFO Wrapped dek: CiQA+6RgJwqX7PRShVFQCtDi7pLuU12Sl0aXYg8qeNdBJ5DsZY4SSQBHSoJHNFWir+8b6SiACAXcJggsXOoWSRy0o15z9BYz55K9K9jbnSqI/8Pqa+eEperUwHitsZjjTEY1mFLrz9Zfcy2P1j3pkfA=
2018-06-03 10:29:36,759 INFO End KMS encryption API call
2018-06-03 10:29:36,759 INFO Start PubSub Publish
2018-06-03 10:29:36,785 INFO Published Message: 6aSUI7RZ812KBsEdvjgr7u/Jc2uUu1OiZ9bTpAYWlE1ySUxIdQ2J4ndeBe7NjzhNaU+lf2juVaKyI/8Yj53/SncMyWuAGi7aii6M9K+o2CuXSJb1RJYXE5Y9XzRc9jt5xvzlmfA7S/VeT10xuSr7hw==
2018-06-03 10:29:36,785 INFO End PubSub Publish
2018-06-03 10:29:36,786 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber:
```
$ python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1
2018-06-03 10:29:53,868 INFO URL being requested: GET https://www.googleapis.com/discovery/v1/apis/cloudkms/v1/rest
2018-06-03 10:29:54,419 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 10:29:56,245 INFO ********** Start PubsubMessage
2018-06-03 10:29:56,246 INFO Received message ID: 109223131542764
2018-06-03 10:29:56,246 INFO Received message publish_time: seconds: 1528046977 nanos: 353000000
2018-06-03 10:29:56,247 INFO Received message attributes["kms_key"]: projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2018-06-03 10:29:56,247 INFO Received message attributes["dek_wrapped"]: CiQA+6RgJwqX7PRShVFQCtDi7pLuU12Sl0aXYg8qeNdBJ5DsZY4SSQBHSoJHNFWir+8b6SiACAXcJggsXOoWSRy0o15z9BYz55K9K9jbnSqI/8Pqa+eEperUwHitsZjjTEY1mFLrz9Zfcy2P1j3pkfA=
2018-06-03 10:29:56,247 INFO Starting KMS decryption API call
2018-06-03 10:29:56,250 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:decrypt?alt=json
2018-06-03 10:29:56,256 DEBUG Handling 1 batched requests
2018-06-03 10:29:56,260 DEBUG Making request: POST https://accounts.google.com/o/oauth2/token
2018-06-03 10:29:56,312 DEBUG Sent request(s) over unary RPC.
2018-06-03 10:29:56,886 INFO End KMS decryption API call
2018-06-03 10:29:56,886 INFO Received aes_encryption_key : ZMZrRoXHTubd+GqBlV8C7B7QxrvvFEbryGyiDTW1I2A=
2018-06-03 10:29:56,887 INFO Starting AES decryption
2018-06-03 10:29:56,888 INFO End AES decryption
2018-06-03 10:29:56,888 INFO Decrypted data {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528046976}, "data": "foo"}
2018-06-03 10:29:56,889 INFO ACK message
2018-06-03 10:29:56,890 DEBUG Handling 1 batched requests
2018-06-03 10:29:56,890 INFO ********** End PubsubMessage
```

> The code all this can be found in the Appendix



### Signing

For signing, we do something similar where we're singing just what we would put into the ```data:``` field and placing that in a specific PubSubMessage.attribute called ```signature=``` with the signature of the data and other attributes as sturct.

#### Output

- Publisher

```
$ python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1

2018-06-03 11:43:09,885 INFO >>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<
2018-06-03 11:43:09,885 INFO Generated signing key: 1ljStq5QoMgfMonu4bqinUeM1czefzqi
2018-06-03 11:43:09,885 INFO Starting signature
2018-06-03 11:43:09,970 INFO Generated Signature: stVBJi1RFpAf4nBd7wVIB0zJUImVe5CWEJbGQOdqAX8=
2018-06-03 11:43:09,970 INFO End signature
2018-06-03 11:43:09,970 INFO Starting KMS encryption API call
2018-06-03 11:43:09,976 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:encrypt?alt=json
2018-06-03 11:43:09,977 DEBUG Making request: POST https://accounts.google.com/o/oauth2/token
2018-06-03 11:43:10,654 INFO End KMS encryption API call
2018-06-03 11:43:10,654 INFO Start PubSub Publish
2018-06-03 11:43:10,684 INFO Published Message: {'attributes': {'a': 'aaa', 'c': 'ccc', 'b': 'bbb', 'epoch_time': 1528051389}, 'data': 'foo'}
2018-06-03 11:43:10,684 INFO  with key_id: projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2018-06-03 11:43:10,684 INFO  with wrapped signature key CiQA+6RgJ2xTuO7dq0HR/TU+K4dsRcdRaO1AiHkyjTQMwNmyxA8SSQBHSoJH2JmuE3H68F411K4vNiulIALgQ3Kg2m499ykK+aI0grk68AgnwXlk6x+0d7rz1nTmV08ESRbhgWM3OwyhkfQxO1x7yBI=
2018-06-03 11:43:10,684 INFO End PubSub Publish
2018-06-03 11:43:10,684 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```
$ python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1

2018-06-03 11:43:06,213 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 11:43:11,726 INFO ********** Start PubsubMessage
2018-06-03 11:43:11,727 DEBUG waiting for recv.
2018-06-03 11:43:11,727 INFO Received message ID: 109270966005226
2018-06-03 11:43:11,728 INFO Received message publish_time: seconds: 1528051391 nanos: 123000000
2018-06-03 11:43:11,728 INFO Received message attributes["kms_key"]: projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2018-06-03 11:43:11,729 INFO Received message attributes["hmac_wrapped"]: CiQA+6RgJ2xTuO7dq0HR/TU+K4dsRcdRaO1AiHkyjTQMwNmyxA8SSQBHSoJH2JmuE3H68F411K4vNiulIALgQ3Kg2m499ykK+aI0grk68AgnwXlk6x+0d7rz1nTmV08ESRbhgWM3OwyhkfQxO1x7yBI=
2018-06-03 11:43:11,729 INFO Received message attributes["signature"]: stVBJi1RFpAf4nBd7wVIB0zJUImVe5CWEJbGQOdqAX8=
2018-06-03 11:43:11,729 INFO Starting KMS decryption API call
2018-06-03 11:43:11,731 INFO URL being requested: POST https://cloudkms.googleapis.com/v1/projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1:decrypt?alt=json
2018-06-03 11:43:11,736 DEBUG Making request: POST https://accounts.google.com/o/oauth2/token
2018-06-03 11:43:11,737 DEBUG Handling 1 batched requests
2018-06-03 11:43:11,782 DEBUG Sent request(s) over unary RPC.
2018-06-03 11:43:12,398 INFO End KMS decryption API call
2018-06-03 11:43:12,399 INFO Received signature : MWxqU3RxNVFvTWdmTW9udTRicWluVWVNMWN6ZWZ6cWk=
2018-06-03 11:43:12,399 INFO Verify message: {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528051389}, "data": "foo"}
2018-06-03 11:43:12,400 INFO   With HMAC: stVBJi1RFpAf4nBd7wVIB0zJUImVe5CWEJbGQOdqAX8=
2018-06-03 11:43:12,400 INFO   With unwrapped key: 1ljStq5QoMgfMonu4bqinUeM1czefzqi
2018-06-03 11:43:12,499 INFO Message authenticity verified
2018-06-03 11:43:12,499 INFO ********** End PubsubMessage
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
    - Need to stay under PubSub maximum message size of 10GB
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
