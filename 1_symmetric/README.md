

# Message Payload Encryption in Google Cloud PubSub (Part 1: Shared Secret)

This is the first part in the series which describes using a symmetric key to encrypt a Pub/Sub message.  We use AES256 and HMAC for encryption and signing.

## What exactly are we encrypting and signing?

Well, lets look at a (PubSub Message .proto](https://github.com/googleapis/googleapis/blob/master/google/pubsub/v1/pubsub.proto).  An actual wire message looks like this:
```proto
message PubsubMessage {
  The message payload.
  bytes data = 1;

 Optional attributes for this message.
  map<string, string> attributes = 2;

  // ID of this message, assigned by the server when the message is published.
  // Guaranteed to be unique within the topic. This value may be read by a
  // subscriber that receives a `PubsubMessage` via a `Pull` call or a push
  // delivery. It must not be populated by the publisher in a `Publish` call.
  string message_id = 3;

  // The time at which the message was published, populated by the server when
  // it receives the `Publish` call. It must not be populated by the
  // publisher in a `Publish` call.
  google.protobuf.Timestamp publish_time = 4;
}
```

If you look carefully, we cant encrypt the PubSubMessage entirely because some fields are generate after a message is submitted and more importantly, we need a place to save the encrypted message or signature data itself with the message.  One compromise is to crate a new field along with the data.  

That is, if the message you were going to submit looks like this:

```
message PubsubMessage {
   data = "foo"
   attributes = {
     "attribute1": "value1",
     "attribute2": "value2"
   }
}
```

### Encrypted message Formatter

Then what we're going to encrypt is a JSON struct for the message representation
```json
{
  "data": "foo",
  "attributes": {
    "attribute1": "value1",
    "attribute2": "value2"    
  }
}
```

So as transmitted PubSub Message:
```json
data:  <encrypted_message>
attributes: <null>
```

Note: we are encrypting and decrypting just the ```data:``` field with a json struct and embedding attributes within it.  What that means is the attributes within the  PubSubMessage may differ from the attributes placed within the encrypted message

### Signed message Formatter

For signed message, we need to transmit the message itself with the signature. For verification, we need will extract the signature in the header and compare. As was the case with encryption, we are verifying the payload within the ```data``` field.  As above, there maybe a variation between the PubSubMessage attributes and the attributes embedded in the data payload:

```json
_json_message = {
    "data": "foo",
    "attributes": {
      "attribute1": "value1",
      "attribute2": "value2"    
    }
  }
```

So as transmitted PubSubMessage would be:

```json
data:  _json_message
attributes:
   "signature": hmac(_json_message)
```

Note: what this means is you can't use any attribute within the PubSubMessage for integrity checks; you must use the embedded attributes within the data: that we signed.  


## Simple message Encryption

Ok, Now that we're on the same field, lets run through the encryption.  There are may ways to do this and this will some of them starting off with basic ones and then moving on to using managed GCP services.

So..Whats the easiest way to sign or encrypt a message?  Symmetric key, right? ok, lets see what we can do.

We're going to setup and and distribute a symmetric key between Alice and Bob where each will keep that key available to the service pushing and pulling messages.  Basically, its a shared secret where the actual distribution of the key happened out of bad earlier.


### Encryption

We're going to use ```AES256``` key to encrypt out message.  We will first take a json field like this:

```
cleartext_message = {
    "data" : "foo".encode(),
    "attributes" : {
        'epoch_time':  int(time.time()),
        'a': "aaa",
        'c': "ccc",
        'b': "bbb"
    }
```

we will initialize a shared key, encrypt it and finally transmit the encrypted message as the ```data``` field

Once the subscriber get this message, we will reverse it by extracting the message data and then decrypting it with our shared key:

#### output

- Publisher
```
$ python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic   --key mBBdNyW0rXX475opSTpK9s6P6jSAhFNT
2018-06-03 07:12:23,428 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 07:12:23,429 INFO Starting AES encryption
2018-06-03 07:12:23,429 INFO End AES encryption
2018-06-03 07:12:23,429 INFO Start PubSub Publish
2018-06-03 07:12:23,429 INFO Published Message: b4kt+rAEvuWHpXHEiuzU4omPA4Wam+7aizmhCZAFHnHjQdaTC1KkXd+565sAgq4dSg7qUA13VsBPDsSOW/ujK4A9IwbihMdkB2WqLCgWr8YoNc/J6TL0qo98OnTHHpfrzVQ6h75d/l0cyK2cSjnDiw==
2018-06-03 07:12:23,429 INFO End PubSub Publish
2018-06-03 07:12:23,429 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber:
```
$ $ python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_subscription my-new-subscriber --key mBBdNyW0rXX475opSTpK9s6P6jSAhFNT
2018-06-03 07:12:20,815 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 07:12:20,840 INFO Listening for messages on projects/esp-demo-197318/subscriptions/my-new-subscriber
2018-06-03 07:12:24,540 INFO ********** Start PubsubMessage
2018-06-03 07:12:24,540 INFO Received message ID: 109100106575710
2018-06-03 07:12:24,541 INFO Received message publish_time: seconds: 1528035143 nanos: 920000000
2018-06-03 07:12:24,541 INFO Decrypted data {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528035143}, "data": "foo"}
2018-06-03 07:12:24,541 INFO ACK message
2018-06-03 07:12:24,542 INFO End AES decryption
2018-06-03 07:12:24,542 INFO ********** End PubsubMessage
```

> The code all this can be found in the Appendix

### Signing

For signing, we do something similar where we're singing just what we would put into the 'data:' field and placing that in a specific PubSubMessage.attribute called ```signature=```.  In other words, we are HMAC signing the byte format of:
```json
message = {
    "data" : "foo".encode(),
    "attributes" : {
        "epoch_time':  int(time.time()),
        "a": "aaa",
        "c": "ccc",
        "b": "bbb"
    }
}
```

#### Output

Here is a sample run:

- Publisher

```
$ python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --salt mysalt --key mBBdNyW0rXX475opSTpK9s6P6jSAhFNT
2018-06-03 07:13:55,022 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 07:13:55,022 INFO Starting hmac
2018-06-03 07:13:55,099 INFO End hmac
2018-06-03 07:13:55,099 INFO Start PubSub Publish
2018-06-03 07:13:55,099 INFO Published Message: {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528035235}, "data": "foo"}
2018-06-03 07:13:55,099 INFO   with hmac: uaQmDxBM/B+ud0Tp19Z49G2nBdXdWjukFLapTKbuMMc=
2018-06-03 07:13:55,099 INFO End PubSub Publish
2018-06-03 07:13:55,099 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber

```
$ python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_subscription my-new-subscriber --key mBBdNyW0rXX475opSTpK9s6P6jSAhFNT
2018-06-03 07:13:52,160 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2018-06-03 07:13:52,187 INFO Listening for messages on projects/esp-demo-197318/subscriptions/my-new-subscriber
2018-06-03 07:13:55,937 INFO ********** Start PubsubMessage
2018-06-03 07:13:55,938 INFO Received message ID: 109099665628729
2018-06-03 07:13:55,938 INFO Received message publish_time: seconds: 1528035235 nanos: 554000000
2018-06-03 07:13:55,938 INFO Starting HMAC
2018-06-03 07:13:55,939 INFO Verify message: {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528035235}, "data": "foo"}
2018-06-03 07:13:55,939 INFO   With HMAC: uaQmDxBM/B+ud0Tp19Z49G2nBdXdWjukFLapTKbuMMc=
2018-06-03 07:13:56,043 INFO Message authenticity verified
2018-06-03 07:13:56,043 INFO ********** End PubsubMessage
```

### The good and the bad

Ok, now that we went through all this...what are the issues with this approach:

- Plus:
    + Its faster than asymmetric keys.
    + Allows for confidentiality (encryption) and authentication/integrity (signatures)
    + There is no network round-trip just to encrypt; everything is done locally
    + Symmetric key is less CPU intensive compared to other schemes (eg. RSA)

- Minus
    - Its a shared secret; you have to accept risks of secret compromise.
    - Key compromise will allow decryption of all messages
    - Key Rotation requires a lot coordination between participant and maybe impractical.
    - Key distribution is an issue with large number of subscribers
    - Message attributes are not encrypted or signed though you can work around this by signing recreated canonical json format of the message.

The issues with symmetric keys like this should be clear and numerous.

## Conclusion

This is a simple way to encrypt or sign your messages. Its nothing new and quite obvious, its basically encrypting an arbitrary message with a specific scheme.  There are clear drawbacks as outlined above among several others.

Can we improve on this?  Lets see if using the [Service Account](https://cloud.google.com/storage/docs/authentication#service_accounts) private key we have locally helps with this in the next set of articles in the series

## Appendix

### Code


## PubSub Service Account Configuration

The following describes the service account permissions needed to access the Topic and Subscription as a service account


- Project:  ```esp-demo-197318```
- Service Accounts with JSON certificates
    - Publisher identity:   ```publisher@esp-demo-197318.iam.gserviceaccount.com```
    - Subscriber identity: ```subscriber@esp-demo-197318.iam.gserviceaccount.com```
- KeyRing+Key:  ```projects/esp-demo-197318/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1```
- PubSub:
    - PUBSUB_TOPIC:  ```projects/esp-demo-197318/topics/my-new-topic```
    - PUBSUB_SUBSCRIPTION ```projects/esp-demo-197318/subscriptions/my-new-subscriber```



- Publisher
![images/topic_permission.png](images/topic_permissions.png)

- Subscriber
![images/subscription_permission.png](images/subscription_permissions.png)

### References

- [Kinesis Message Payload Encryption with AWS KMS ](https://aws.amazon.com/blogs/big-data/encrypt-and-decrypt-amazon-kinesis-records-using-aws-kms/)
- [Server-Side Encryption with AWS Kinesis](https://aws.amazon.com/blogs/big-data/under-the-hood-of-server-side-encryption-for-amazon-kinesis-streams/)
- [Enveope Encryption](https://cloud.google.com/kms/docs/envelope-encryption#how_to_encrypt_data_using_envelope_encryption)
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
