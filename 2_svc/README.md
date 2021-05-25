

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


## Simple message Encryption

Ok, Now that we're on the same field, lets run through a sample run.  

### Encryption

We're going to use the **SAME** service accounts as the publisher and subscriber already use as authorization to GCP.  You are ofcourse do not have to use the same ones..infact, for encryption, you can use the public key for any recipient on any project!

Anyway..

#### Output

- Publisher

```log
$ python publisher.py  --mode encrypt --cert_service_account '../svc-publisher.json' --project_id mineral-minutia-820 --pubsub_topic my-new-topic \
   --recipient subscriber@mineral-minutia-820.iam.gserviceaccount.com --recipient_key_id 2686a5da403e2e3f24d9abad9b37a42fbca45c13

2021-05-25 07:31:26,656 INFO >>>>>>>>>>> Start Encrypt with Service Account Public Key Reference <<<<<<<<<<<
2021-05-25 07:31:26,656 INFO   Using remote public key_id = 2686a5da403e2e3f24d9abad9b37a42fbca45c13
2021-05-25 07:31:26,656 INFO   For service account at: https://www.googleapis.com/service_accounts/v1/metadata/x509/2686a5da403e2e3f24d9abad9b37a42fbca45c13
2021-05-25 07:31:26,657 DEBUG Starting new HTTPS connection (1): www.googleapis.com:443
2021-05-25 07:31:26,703 DEBUG https://www.googleapis.com:443 "GET /service_accounts/v1/metadata/x509/subscriber@mineral-minutia-820.iam.gserviceaccount.com HTTP/1.1" 200 1718
2021-05-25 07:31:26,709 INFO Start PubSub Publish
2021-05-25 07:31:26,710 DEBUG Checking None for explicit credentials as part of auth process...
2021-05-25 07:31:26,711 DEBUG Checking Cloud SDK credentials as part of auth process...
2021-05-25 07:31:27,242 INFO Published Message: b'dU0P3A7q300mVcGcVj+PFqPxcKgl7fJEZMpr7hV8GuvaCVJK6cR8vMf3b1ZCVLPGry3aeaPpSl3oA4b0VbNNNOFjjo4meOfxDkF+b2On2hSOc7btR+yjOGANne1xyn81SodqV2354tLWWMle3fbFpnxzLq8OEqs9yq4rLuTxCz7kGoSFjKb3iM/L++IctsCAo/65pnI41c2e5J7wMKA3f0xEKZ8ibAX23A1A4md/hfP1cWP/Di2tlL9n9Wbf1JOGpwAtNMQVgasWWagi99AisbcubXXBo+O+1ad0VjHLMrTcIBRSg8sUCh3qtt6y9gF7h9/eK7Xw3jw9gdgLGdIOpA=='
2021-05-25 07:31:27,252 DEBUG Commit thread is waking up
2021-05-25 07:31:27,287 DEBUG Making request: POST https://oauth2.googleapis.com/token
2021-05-25 07:31:27,291 DEBUG Starting new HTTPS connection (1): oauth2.googleapis.com:443
2021-05-25 07:31:27,420 DEBUG https://oauth2.googleapis.com:443 "POST /token HTTP/1.1" 200 None
2021-05-25 07:31:27,689 DEBUG gRPC Publish took 0.43643641471862793 seconds.
2021-05-25 07:31:27,690 INFO Published MessageID: 2472841570701784
2021-05-25 07:31:27,691 INFO End PubSub Publish
2021-05-25 07:31:27,691 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

Note, we are specifying the `private_key_id` andemail for the **subscriber** (i.,e `svc-subscriber.json`)
```json
{
  "type": "service_account",
  "project_id": "mineral-minutia-820",
  "private_key_id": "2686a5da403e2e3f24d9abad9b37a42fbca45c13",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvA
  "client_email": "subscriber@mineral-minutia-820.iam.gserviceaccount.com",
  "client_id": "107652679676712969698",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/subscriber%40mineral-minutia-820.iam.gserviceaccount.com"
}
```

- Subscriber:

```log
$ python subscriber.py  --mode decrypt --cert_service_account '../svc-subscriber.json' --project_id mineral-minutia-820 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-05-25 07:31:20,773 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-05-25 07:31:28,761 INFO ********** Start PubsubMessage 
2021-05-25 07:31:28,762 INFO Received message ID: 2472841570701784
2021-05-25 07:31:28,762 INFO Received message publish_time: 2021-05-25 11:31:27.646000+00:00
2021-05-25 07:31:28,763 INFO Attempting to decrypt message: b'"dU0P3A7q300mVcGcVj+PFqPxcKgl7fJEZMpr7hV8GuvaCVJK6cR8vMf3b1ZCVLPGry3aeaPpSl3oA4b0VbNNNOFjjo4meOfxDkF+b2On2hSOc7btR+yjOGANne1xyn81SodqV2354tLWWMle3fbFpnxzLq8OEqs9yq4rLuTxCz7kGoSFjKb3iM/L++IctsCAo/65pnI41c2e5J7wMKA3f0xEKZ8ibAX23A1A4md/hfP1cWP/Di2tlL9n9Wbf1JOGpwAtNMQVgasWWagi99AisbcubXXBo+O+1ad0VjHLMrTcIBRSg8sUCh3qtt6y9gF7h9/eK7Xw3jw9gdgLGdIOpA=="'
2021-05-25 07:31:28,764 INFO   Using service_account/key_id: subscriber@mineral-minutia-820.iam.gserviceaccount.com 2686a5da403e2e3f24d9abad9b37a42fbca45c13
2021-05-25 07:31:28,775 INFO Decrypted Message payload: {"data": "foo", "attributes": {"epoch_time": 1621942286, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 07:31:28,775 INFO ********** End PubsubMessage 
```


> The code all this can be found in the Appendix

### Signing

For signing, we do something similar where we're singing just what we would put into the 'data:' field and placing that in a specific PubSubMessage.attribute called ```signature=```

#### Output

- Publisher

```log
$ python publisher.py  --mode sign --cert_service_account '../svc-publisher.json' --project_id mineral-minutia-820 --pubsub_topic my-new-topic \
  --recipient subscriber@mineral-minutia-820.iam.gserviceaccount.com --recipient_key_id 2686a5da403e2e3f24d9abad9b37a42fbca45c13

2021-05-25 07:34:44,362 INFO >>>>>>>>>>> Start Sign with Service Account json KEY <<<<<<<<<<<
2021-05-25 07:34:44,367 INFO Signature: g4L0Ob1HBFxvTE6KequtAoHdTX1FFFaRD2OrSIJZaVaWQHa3T7q171d71R+JhywNwtniY6gF7LstWvKRcDo0gXNSU98BPCyahY8Ub6uCQHHfZzjft7fcWDGcUcn75fSumIkZakQz4NWicDq4253sOL33qsR/ltCyo4GOX0XxY3V/mZJuP4xVPghaLepSLlfH/0s8AupK3mXJlMPfrTb1BbeSbVZMREqskQOkbDzo1+FfE/wM/n7CbJxiEQXspVB+arRXlwcjPMPH26R2CkmRskUjX0oEkm1Uil+RoYD1u7Y2XLBti7I+viiUVOKcxtXAX19QdERKOFiYQ8RUI3/ubw==
2021-05-25 07:34:44,367 INFO Start PubSub Publish
2021-05-25 07:34:44,368 DEBUG Checking None for explicit credentials as part of auth process...
2021-05-25 07:34:44,368 DEBUG Checking Cloud SDK credentials as part of auth process...
2021-05-25 07:34:44,865 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621942484, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 07:34:44,875 DEBUG Commit thread is waking up
2021-05-25 07:34:44,915 DEBUG Making request: POST https://oauth2.googleapis.com/token
2021-05-25 07:34:44,921 DEBUG Starting new HTTPS connection (1): oauth2.googleapis.com:443
2021-05-25 07:34:45,038 DEBUG https://oauth2.googleapis.com:443 "POST /token HTTP/1.1" 200 None
2021-05-25 07:34:45,330 DEBUG gRPC Publish took 0.4541797637939453 seconds.
2021-05-25 07:34:45,331 INFO Published MessageID: 2472841329883188
2021-05-25 07:34:45,331 INFO End PubSub Publish
2021-05-25 07:34:45,331 INFO >>>>>>>>>>> END <<<<<<<<<<<
```

- Subscriber
```log
$ python subscriber.py  --mode verify --cert_service_account '../svc-subscriber.json' --project_id mineral-minutia-820 --pubsub_topic my-new-topic  --pubsub_subscription my-new-subscriber

2021-05-25 07:34:37,604 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-05-25 07:34:46,148 INFO ********** Start PubsubMessage 
2021-05-25 07:34:46,149 INFO Received message ID: 2472841329883188
2021-05-25 07:34:46,149 INFO Received message publish_time: 2021-05-25 11:34:45.255000+00:00
2021-05-25 07:34:46,150 INFO Attempting to verify message: b'{"data": "foo", "attributes": {"epoch_time": 1621942484, "a": "aaa", "c": "ccc", "b": "bbb"}}'
2021-05-25 07:34:46,150 INFO Verify message with signature: g4L0Ob1HBFxvTE6KequtAoHdTX1FFFaRD2OrSIJZaVaWQHa3T7q171d71R+JhywNwtniY6gF7LstWvKRcDo0gXNSU98BPCyahY8Ub6uCQHHfZzjft7fcWDGcUcn75fSumIkZakQz4NWicDq4253sOL33qsR/ltCyo4GOX0XxY3V/mZJuP4xVPghaLepSLlfH/0s8AupK3mXJlMPfrTb1BbeSbVZMREqskQOkbDzo1+FfE/wM/n7CbJxiEQXspVB+arRXlwcjPMPH26R2CkmRskUjX0oEkm1Uil+RoYD1u7Y2XLBti7I+viiUVOKcxtXAX19QdERKOFiYQ8RUI3/ubw==
2021-05-25 07:34:46,150 INFO   Using service_account/key_id: publisher@mineral-minutia-820.iam.gserviceaccount.com 54927b54123e5b00f5e7ca6e290b3823d545eeb2
2021-05-25 07:34:46,226 INFO Message integrity verified
2021-05-25 07:34:46,226 INFO ********** End PubsubMessage 
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
