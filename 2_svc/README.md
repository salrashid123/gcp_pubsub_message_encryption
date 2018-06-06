

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
  "project_id": "esp-demo-197318",
  "private_key_id": "2cb5244527b4f013a73b2c717ae74d762ac3af2c",
  "private_key": "-----BEGIN PRIVATE KEY----- /redacted/-----END PRIVATE KEY-----\n",
  "client_email": "publisher@esp-demo-197318.iam.gserviceaccount.com",
  "client_id": "117270909525656450684",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://accounts.google.com/o/oauth2/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/publisher%40esp-demo-197318.iam.gserviceaccount.com"
}
```

which has the public key available at a well-known URL (```client_x509_cert_url```):

- x509:
    - [https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@esp-demo-197318.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/metadata/x509/publisher@esp-demo-197318.iam.gserviceaccount.com)
- JWK
    - [https://www.googleapis.com/service_accounts/v1/jwk/publisher@esp-demo-197318.iam.gserviceaccount.com](https://www.googleapis.com/service_accounts/v1/jwk/publisher@esp-demo-197318.iam.gserviceaccount.com)


Since the subscriber can download these certs to verify a message, the issue of key-distribution is a bit easier.

Wait....we've got a public key on our hands now...we can use that for encryption too.   In this mode, the publisher uses the public key for the for the _subscriber__ to encrypt a message  (in our case, one of the available keys [here](https://www.googleapis.com/service_accounts/v1/metadata/x509/subscriber@esp-demo-197318.iam.gserviceaccount.com)).  The subscriber on the other end must have in possession or have the ability to verify the message.  With this technique, you are ensuring confidentiality by encrypting the payload using public/private keys

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


## Simple message Encryption

Ok, Now that we're on the same field, lets run through a sample run.  

### Encryption

We're going to use the **SAME** service accounts as the publisher and subscriber already use as authorization to GCP.  You are ofcourse do not have to use the same ones..infact, for encryption, you can use the public key for any recipient on any project!

Anyway..

#### Output

- Publisher
```
$ python publisher.py  --mode encrypt --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic --recipient subscriber@esp-demo-197318.iam.gserviceaccount.com --recipient_key_id f4425f395a815f54379421d8279d8477e70fc189
2018-06-03 08:05:48,733 INFO >>>>>>>>>>> Start Encrypt with Service Account Public Key Reference <<<<<<<<<<<
2018-06-03 08:05:48,734 INFO   Using remote public key_id = f4425f395a815f54379421d8279d8477e70fc189
2018-06-03 08:05:48,734 INFO   For service account at: https://www.googleapis.com/service_accounts/v1/metadata/x509/f4425f395a815f54379421d8279d8477e70fc189
2018-06-03 08:05:48,923 INFO Start PubSub Publish
2018-06-03 08:05:48,927 INFO Published Message: hw6e6QBazBVJMxKnKA3Z6Sv4D5m9G+x4mvc2xJKRzcMZRPNBtqOx/uYL1YgTysPRRfiBDcZTBIygHgv8VwgLwOeKoi55WYDtfhN768+MNCi2oo44JxkL/n1XuCWLrxcsW5RGGX8OAa4NozI+GHeZdauyKmyv7lcjDBXISfoNm3auOAOdDUsiNptTuKR0d+zNQJsR3YQ0X030Xu5UY+oJfnIJ00YC7emb1nzEnyJs6jD9jF0cN9t5vefepm8OpV4/NcBHKwXSSQnloBveWd/jk8cv3W0VJjOsFCMYwu/8S1mSwvhu1Ej9pxsnApdIuOasDXP78pUzPkMUU9PgqDrqnw==
2018-06-03 08:05:48,927 INFO End PubSub Publish
2018-06-03 08:05:48,927 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber:
```
$ python subscriber.py  --mode decrypt --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2018-06-03 08:05:52,951 INFO ********** Start PubsubMessage
2018-06-03 08:05:52,952 DEBUG waiting for recv.
2018-06-03 08:05:52,953 INFO Received message ID: 109133289012824
2018-06-03 08:05:52,954 INFO Received message publish_time: seconds: 1528038349 nanos: 380000000
2018-06-03 08:05:52,954 INFO Attempting to decrypt message: hw6e6QBazBVJMxKnKA3Z6Sv4D5m9G+x4mvc2xJKRzcMZRPNBtqOx/uYL1YgTysPRRfiBDcZTBIygHgv8VwgLwOeKoi55WYDtfhN768+MNCi2oo44JxkL/n1XuCWLrxcsW5RGGX8OAa4NozI+GHeZdauyKmyv7lcjDBXISfoNm3auOAOdDUsiNptTuKR0d+zNQJsR3YQ0X030Xu5UY+oJfnIJ00YC7emb1nzEnyJs6jD9jF0cN9t5vefepm8OpV4/NcBHKwXSSQnloBveWd/jk8cv3W0VJjOsFCMYwu/8S1mSwvhu1Ej9pxsnApdIuOasDXP78pUzPkMUU9PgqDrqnw==
2018-06-03 08:05:52,955 INFO   Using service_account/key_id: subscriber@esp-demo-197318.iam.gserviceaccount.com f4425f395a815f54379421d8279d8477e70fc189
2018-06-03 08:05:52,964 INFO Decrypted Message payload: {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528038348}, "data": "foo"}
2018-06-03 08:05:52,965 INFO ********** End PubsubMessage
```

> The code all this can be found in the Appendix

### Signing

For signing, we do something similar where we're singing just what we would put into the 'data:' field and placing that in a specific PubSubMessage.attribute called ```signature=```

#### Output

- Publisher

```
$ python publisher.py  --mode sign --service_account '../svc-publisher.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic
2018-06-03 08:08:12,768 INFO >>>>>>>>>>> Start Sign with Service Account json KEY <<<<<<<<<<<
2018-06-03 08:08:12,770 INFO Signature: nkPKBBM3QicP3gvAbOJRlIyz8zV6+2bdBxSM7MXPYFCN+mnZRrKSYBRybOAY5FRYYphaNrYj1coV
SPl14VL3spcMaABgJL8O4cn8EYUJNwuAuflIx1dSCIcBNAG+0Wdy4A+bGymIpeUOqjP2BVdKyQWU
pWtKHn3xsESC83eLw5mz8irD1r5zuuWnYEuVSSshZ8NHu8c6d+qcvgJwOLhb0lout0rybc4F+vgL
9j/xUEvJiawZfulOtiSAZhoAd9FW7rpOUWn5YNTQQyRv6szPovyXcDhSuVCx0UU5tOswwZyheelH
oW0GH5X1OY8ENhfnlvmUr+p8J1i0/wsKswuPfQ==
2018-06-03 08:08:12,770 INFO Start PubSub Publish
2018-06-03 08:08:12,774 INFO Published Message: {'attributes': {'a': 'aaa', 'c': 'ccc', 'b': 'bbb', 'epoch_time': 1528038492}, 'data': 'foo'}
2018-06-03 08:08:12,774 INFO End PubSub Publish
2018-06-03 08:08:12,774 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```
$ python subscriber.py  --mode verify --service_account '../svc-subscriber.json' --project_id esp-demo-197318 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber
2018-06-03 08:08:16,429 INFO ********** Start PubsubMessage
2018-06-03 08:08:16,430 INFO Received message ID: 109134363647105
2018-06-03 08:08:16,431 INFO Received message publish_time: seconds: 1528038493 nanos: 218000000
2018-06-03 08:08:16,431 INFO Attempting to verify message: {"attributes": {"a": "aaa", "c": "ccc", "b": "bbb", "epoch_time": 1528038492}, "data": "foo"}
2018-06-03 08:08:16,432 INFO Verify message with signature: nkPKBBM3QicP3gvAbOJRlIyz8zV6+2bdBxSM7MXPYFCN+mnZRrKSYBRybOAY5FRYYphaNrYj1coV
SPl14VL3spcMaABgJL8O4cn8EYUJNwuAuflIx1dSCIcBNAG+0Wdy4A+bGymIpeUOqjP2BVdKyQWU
pWtKHn3xsESC83eLw5mz8irD1r5zuuWnYEuVSSshZ8NHu8c6d+qcvgJwOLhb0lout0rybc4F+vgL
9j/xUEvJiawZfulOtiSAZhoAd9FW7rpOUWn5YNTQQyRv6szPovyXcDhSuVCx0UU5tOswwZyheelH
oW0GH5X1OY8ENhfnlvmUr+p8J1i0/wsKswuPfQ==
2018-06-03 08:08:16,433 INFO   Using service_account/key_id: publisher@esp-demo-197318.iam.gserviceaccount.com 2cb5244527b4f013a73b2c717ae74d762ac3af2c
2018-06-03 08:08:16,438 DEBUG Starting new HTTPS connection (1): www.googleapis.com
2018-06-03 08:08:16,439 DEBUG Handling 1 batched requests
2018-06-03 08:08:16,498 DEBUG Sent request(s) over unary RPC.
2018-06-03 08:08:16,596 DEBUG https://www.googleapis.com:443 "GET /service_accounts/v1/metadata/x509/publisher@esp-demo-197318.iam.gserviceaccount.com HTTP/1.1" 200 2339
2018-06-03 08:08:16,605 INFO Message integrity verified
2018-06-03 08:08:16,606 INFO ********** End PubsubMessage
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
