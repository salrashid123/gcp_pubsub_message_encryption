

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
```log
$ python publisher.py  --mode encrypt --kms_project_id mineral-minutia-820  --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id mineral-minutia-820 --tenantID A
2021-05-25 08:25:40,223 INFO >>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<
2021-05-25 08:25:40,224 INFO Rotating symmetric key
2021-05-25 08:25:41,498 INFO Start PubSub Publish
2021-05-25 08:25:42,006 INFO Published Message: AWsIhGdmF6XEqXcTWaCotxW5ydFd3eVFeEP6LicEgAXon1ys6txwMp0rr5N7VfC3n9B9jQ3gSLHVQ0W8nBUog7IlArwExlv0hEAEhU8wt6rm2pg4hphyXshuqOfRDn0j0sWJsvrVxcQMQo1vF4lc+28Ztib2yMUYQCVGWrtf
2021-05-25 08:25:42,427 INFO Published MessageID: 2473033678888338
2021-05-25 08:25:43,938 INFO Published Message: AWsIhGeynl387ioNNGt9f5M2ZiFBEgidUQ5oCp/izqSoa2yI2U3084AMiDuZoxorQDKXAXITIL8OO3iTVnERs0esFN7jcvcBZcKtuiPWhvrySrIHlRxf12eAd4bViNhcPxK+qg/6qWxplZcpw3vEUGbbcpgg5nevY56StPun
2021-05-25 08:25:44,373 INFO Published MessageID: 2473033795637422
2021-05-25 08:25:45,869 INFO Published Message: AWsIhGcSv3aLG/UX7DRlLsIomfZ399aeXsMpCpMCGfHzWkyzmqVTHLsWWy7yYMY2qjnAdcmOl/lO4Ieq5WEo/dd9ZNXiKSvYgYoGfcFQltOLf5NQiFGv6xJuNVHdCWerlntQUhRqVie9TJpBMLa6AU6jvsinY8SYXADQjgED
2021-05-25 08:25:46,077 INFO Published MessageID: 2473033947139049
2021-05-25 08:25:47,580 INFO Published Message: AWsIhGe00rJuJBFP5pCX1iuPc3l6mY24UCS/nJ8zn2ufe/rhRUyJnxlYgSkx5n3PBWekHDSlHakwxotOVUsrH9gijL4bdLZLaAC7gSyltXNP8mAVdsK3dOn4uaWngwt/a3Fade6drUEl+c1zK2qJoo9TrVC7mlWP+oEFd2Eu
2021-05-25 08:25:47,795 INFO Published MessageID: 826344344488244
2021-05-25 08:25:49,329 INFO Published Message: AWsIhGcQaTHQBF2yc3+46/5++CMs2EGwL/46Xt+3l1J6nCBblWwhpU4YtWpHR4IEUryrhi8YWt3SvBm9dzaq9Z4W3phHDlkxfJro+LDnHmg6HJ6IsdEKPW1GbmJy8gi9WQMzEucJDnHtuGf92DlgVOw0JnmHzuakhf2Eszts
2021-05-25 08:25:49,609 INFO Published MessageID: 2473033734571240


2021-05-25 08:25:50,610 INFO Rotating symmetric key           <<<<<<<<<<<<<<<<<<<<<<<<<<<<<

2021-05-25 08:25:51,807 INFO Start PubSub Publish
2021-05-25 08:25:52,326 INFO Published Message: AUw8g+xWClo5wUsg1dCDf+inOalTWoLMUQEShAIhNGadZlmJgNlqEGS577yJFXLiRwDHdf0bk5F+lnfRRs/IAtPpyq2Vhl2IbgCO/8DJndWF0fm9ZwxVrh4MVW1w4f2oDAz+6EuCr37WEqn7rWmHmZIvsva/3X61VOfLyqv+
2021-05-25 08:25:52,556 INFO Published MessageID: 2473033963508217
2021-05-25 08:25:54,066 INFO Published Message: AUw8g+zXVcu7hQZzwvpmlUL24BSgE7E3k2eNyttJNvrp0IcXD3FD4F7WylEYzsGz5Byc/lKMFiABCIN9l1OwKdjopOCR1lOaiYLGIu+KVyKy0Zf9mfNU9dyoto98+7/fSDs2I6azI/EPkNh6HG5sJTwv6Y+hc2CbO/w8PTS7
2021-05-25 08:25:54,257 INFO Published MessageID: 2473033528745375
2021-05-25 08:25:55,809 INFO Published Message: AUw8g+zCyBuE7HCWOJn2YBBAgSs11kgQa8Tj0KGBWBw5T2/7kEAThdfK4LuU+INFMTtnbe0gN2CxFaJSqM6Ghj+X9/2eyuyLrUEQOPETs0Hspqv9/xsnC3uiXZofqrOivr16cCUyQIZB42gKiBlYvIjrxjInMWKM15NnFrmO
2021-05-25 08:25:56,019 INFO Published MessageID: 2472966702915116
```

- Subscriber:
```log
$ python subscriber.py  --mode decrypt  --pubsub_project_id mineral-minutia-820 --kms_project_id mineral-minutia-820 \
    --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --tenantID A

2021-05-25 08:25:33,495 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-05-25 08:25:33,497 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-05-25 08:25:43,462 INFO ********** Start PubsubMessage 
2021-05-25 08:25:43,462 INFO Received message ID: 2473033678888338
2021-05-25 08:25:43,462 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call                                  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
2021-05-25 08:25:43,740 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945541, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:43,740 INFO ********** End PubsubMessage 
2021-05-25 08:25:45,331 INFO ********** Start PubsubMessage 
2021-05-25 08:25:45,331 INFO Received message ID: 2473033795637422
2021-05-25 08:25:45,332 INFO Using Cached DEK
2021-05-25 08:25:45,332 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945543, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:45,332 INFO ********** End PubsubMessage 
2021-05-25 08:25:46,115 INFO ********** Start PubsubMessage 
2021-05-25 08:25:46,115 INFO Received message ID: 2473033947139049
2021-05-25 08:25:46,116 INFO Using Cached DEK
2021-05-25 08:25:46,116 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945545, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:46,116 INFO ********** End PubsubMessage 
2021-05-25 08:25:47,830 INFO ********** Start PubsubMessage 
2021-05-25 08:25:47,831 INFO Received message ID: 826344344488244
2021-05-25 08:25:47,831 INFO Using Cached DEK
2021-05-25 08:25:47,831 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945547, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:47,831 INFO ********** End PubsubMessage 
2021-05-25 08:25:50,613 INFO ********** Start PubsubMessage 
2021-05-25 08:25:50,613 INFO Received message ID: 2473033734571240
2021-05-25 08:25:50,614 INFO Using Cached DEK
2021-05-25 08:25:50,614 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945548, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:50,614 INFO ********** End PubsubMessage 
2021-05-25 08:25:52,591 INFO ********** Start PubsubMessage 
2021-05-25 08:25:52,591 INFO Received message ID: 2473033963508217


2021-05-25 08:25:52,591 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call                                  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
2021-05-25 08:25:52,976 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945551, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:52,976 INFO ********** End PubsubMessage 
2021-05-25 08:25:54,298 INFO ********** Start PubsubMessage 
2021-05-25 08:25:54,299 INFO Received message ID: 2473033528745375
2021-05-25 08:25:54,299 INFO Using Cached DEK
2021-05-25 08:25:54,299 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945553, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:54,299 INFO ********** End PubsubMessage 
2021-05-25 08:25:56,060 INFO ********** Start PubsubMessage 
2021-05-25 08:25:56,060 INFO Received message ID: 2472966702915116
2021-05-25 08:25:56,060 INFO Using Cached DEK
2021-05-25 08:25:56,061 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1621945555, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-05-25 08:25:56,061 INFO ********** End PubsubMessage
```

> The code all this can be found in the Appendix



### Signing

For signing, we do something similar where we're singing just what we would put into the ```data:``` field and placing that in a specific PubSubMessage.attribute called ```signature=``` with the signature of the data and other attributes as sturct.

#### Output

- Publisher

```log
$ python publisher.py  --mode sign --kms_project_id mineral-minutia-820  --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id mineral-minutia-820 --tenantID A

2021-05-25 08:45:15,239 INFO >>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<

2021-05-25 08:45:15,239 INFO Rotating key<<<<<<<<<<<<

2021-05-25 08:45:16,557 INFO Start PubSub Publish
2021-05-25 08:45:16,558 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946716, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:16,558 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:17,071 INFO Published MessageID: 826344803268096
2021-05-25 08:45:17,072 INFO Start PubSub Publish
2021-05-25 08:45:17,073 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946717, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:17,073 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:17,123 INFO Published MessageID: 2473034819508588
2021-05-25 08:45:17,124 INFO Start PubSub Publish
2021-05-25 08:45:17,125 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946717, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:17,125 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:17,174 INFO Published MessageID: 826344897257698
2021-05-25 08:45:17,174 INFO Start PubSub Publish
2021-05-25 08:45:17,176 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946717, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:17,176 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:17,329 INFO Published MessageID: 826344946739900
2021-05-25 08:45:17,330 INFO Start PubSub Publish
2021-05-25 08:45:17,331 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946717, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:17,331 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:17,475 INFO Published MessageID: 826345331298126

2021-05-25 08:45:17,475 INFO Rotating key  <<<<<<<<<<<<

2021-05-25 08:45:18,649 INFO Start PubSub Publish
2021-05-25 08:45:18,650 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946718, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:18,650 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:18,832 INFO Published MessageID: 2473035463018475
2021-05-25 08:45:18,833 INFO Start PubSub Publish
2021-05-25 08:45:18,834 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946718, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:18,834 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:19,011 INFO Published MessageID: 2473035405443005
2021-05-25 08:45:19,012 INFO Start PubSub Publish
2021-05-25 08:45:19,013 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946719, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:19,013 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:19,061 INFO Published MessageID: 2473034719755701
2021-05-25 08:45:19,062 INFO Start PubSub Publish
2021-05-25 08:45:19,063 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946719, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:19,063 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:19,105 INFO Published MessageID: 2473034819505100
2021-05-25 08:45:19,106 INFO Start PubSub Publish
2021-05-25 08:45:19,107 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1621946719, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-05-25 08:45:19,107 INFO  with key_id: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:19,154 INFO Published MessageID: 2473035348079877
```

- Subscriber
```log
$ python subscriber.py  --mode verify  --pubsub_project_id mineral-minutia-820 --kms_project_id mineral-minutia-820 \
   --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --tenantID A

2021-05-25 08:45:24,790 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-05-25 08:45:24,793 INFO Listening for messages on projects/mineral-minutia-820/subscriptions/my-new-subscriber
2021-05-25 08:45:26,116 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,116 INFO Received message ID: 826345331298126
2021-05-25 08:45:26,117 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,117 INFO Received message publish_time: 2021-05-25 12:45:17.470000+00:00
2021-05-25 08:45:26,119 INFO Received message ID: 2473034819505100
2021-05-25 08:45:26,120 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:26,120 INFO Received message publish_time: 2021-05-25 12:45:19.103000+00:00
2021-05-25 08:45:26,121 INFO Received message attributes["sign_key_wrapped"]: EsMBCiUAmT+VVbTb+/mvNz5VOqGoQMoJfkJQkiZXHYSKiXDcfFNVgXllEpkBACsKZVKYe7S1R/4TWYsFbai8I617Je3B/Yk3wWDcvQTmIZ31LFXR1ZZkOOSliSsoqGPbxbfy+jgcF/rFTco5Eco2wNPjl2yK+gtY5FqLyTCVGhvqow2TwifGzqzqpRqpO+DQ4I/RAjRjRf0l7TdFJ9d4QVYzDiG5ZdAXzXkXYNyxRAZJ81kq01MAO0kqv/e92g//l0cf/9dBGkIIs5H1vgESOgoudHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuSG1hY0tleRABGLOR9b4BIAE=
2021-05-25 08:45:26,121 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:26,121 INFO Received message attributes["signature"]: ARfdSLM+fmeUtWnFwv4vzOfye/DF8+Z7aTIUpThMsyCAwOwNxw==
2021-05-25 08:45:26,122 INFO Received message attributes["sign_key_wrapped"]: EsMBCiUAmT+VVe+UyoltoBGrQXL7ezfjQDQivHtpN1LvtCYiYlDjemQPEpkBACsKZVK/39cf9chgTxCnDAEQy7tdJ+2bFXSZcwCGY51H/z4hLptEyXFgAqQTgukTmCt6tSzU8+SLcQe629ShhXDM7eaAXsqpCL0iht6ZFV3amVmeSFLvIrhHPaEa1WxDuzNAdRYqR5wHKrl4EyzSSrWM6PzM0XFZkqsrBRnSW1xNb47a56dvP3G8H67VpgoFKfjo78Pm5QyvGkIIwsjpkAcSOgoudHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuSG1hY0tleRABGMLI6ZAHIAE=

2021-05-25 08:45:26,122 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call

2021-05-25 08:45:26,122 INFO Received message attributes["signature"]: AXIaZEIBrxUFxhlnh4vkRXTeXvddNjAmNOa1Vn62ocKM41lReg==
2021-05-25 08:45:26,486 INFO End KMS decryption API call
2021-05-25 08:45:26,489 INFO Message authenticity verified


2021-05-25 08:45:26,488 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call  <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<


2021-05-25 08:45:26,488 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,896 INFO End KMS decryption API call
2021-05-25 08:45:26,897 INFO Received message ID: 826344946739900
2021-05-25 08:45:26,898 INFO Received message publish_time: 2021-05-25 12:45:17.326000+00:00
2021-05-25 08:45:26,898 INFO Message authenticity verified
2021-05-25 08:45:26,898 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:26,899 INFO Received message attributes["sign_key_wrapped"]: EsMBCiUAmT+VVbTb+/mvNz5VOqGoQMoJfkJQkiZXHYSKiXDcfFNVgXllEpkBACsKZVKYe7S1R/4TWYsFbai8I617Je3B/Yk3wWDcvQTmIZ31LFXR1ZZkOOSliSsoqGPbxbfy+jgcF/rFTco5Eco2wNPjl2yK+gtY5FqLyTCVGhvqow2TwifGzqzqpRqpO+DQ4I/RAjRjRf0l7TdFJ9d4QVYzDiG5ZdAXzXkXYNyxRAZJ81kq01MAO0kqv/e92g//l0cf/9dBGkIIs5H1vgESOgoudHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuSG1hY0tleRABGLOR9b4BIAE=
2021-05-25 08:45:26,899 INFO Received message attributes["signature"]: ARfdSLM+fmeUtWnFwv4vzOfye/DF8+Z7aTIUpThMsyCAwOwNxw==
2021-05-25 08:45:26,900 INFO Using Cached DEK
2021-05-25 08:45:26,900 INFO Message authenticity verified
2021-05-25 08:45:26,933 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,933 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,934 INFO Received message ID: 826344803268096
2021-05-25 08:45:26,937 INFO Received message ID: 2473034819508588
2021-05-25 08:45:26,939 INFO Received message publish_time: 2021-05-25 12:45:17.034000+00:00
2021-05-25 08:45:26,940 INFO Received message publish_time: 2021-05-25 12:45:17.119000+00:00
2021-05-25 08:45:26,940 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:26,941 INFO Received message attributes["kms_key"]: projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-05-25 08:45:26,941 INFO Received message attributes["sign_key_wrapped"]: EsMBCiUAmT+VVbTb+/mvNz5VOqGoQMoJfkJQkiZXHYSKiXDcfFNVgXllEpkBACsKZVKYe7S1R/4TWYsFbai8I617Je3B/Yk3wWDcvQTmIZ31LFXR1ZZkOOSliSsoqGPbxbfy+jgcF/rFTco5Eco2wNPjl2yK+gtY5FqLyTCVGhvqow2TwifGzqzqpRqpO+DQ4I/RAjRjRf0l7TdFJ9d4QVYzDiG5ZdAXzXkXYNyxRAZJ81kq01MAO0kqv/e92g//l0cf/9dBGkIIs5H1vgESOgoudHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuSG1hY0tleRABGLOR9b4BIAE=
2021-05-25 08:45:26,941 INFO Received message attributes["sign_key_wrapped"]: EsMBCiUAmT+VVbTb+/mvNz5VOqGoQMoJfkJQkiZXHYSKiXDcfFNVgXllEpkBACsKZVKYe7S1R/4TWYsFbai8I617Je3B/Yk3wWDcvQTmIZ31LFXR1ZZkOOSliSsoqGPbxbfy+jgcF/rFTco5Eco2wNPjl2yK+gtY5FqLyTCVGhvqow2TwifGzqzqpRqpO+DQ4I/RAjRjRf0l7TdFJ9d4QVYzDiG5ZdAXzXkXYNyxRAZJ81kq01MAO0kqv/e92g//l0cf/9dBGkIIs5H1vgESOgoudHlwZS5nb29nbGVhcGlzLmNvbS9nb29nbGUuY3J5cHRvLnRpbmsuSG1hY0tleRABGLOR9b4BIAE=
2021-05-25 08:45:26,941 INFO Received message attributes["signature"]: ARfdSLPO5oao9GMD7ibULrlH+Hxas7yUDuZ9QJSI2qOInTuXEw==
2021-05-25 08:45:26,942 INFO Received message attributes["signature"]: ARfdSLM+fmeUtWnFwv4vzOfye/DF8+Z7aTIUpThMsyCAwOwNxw==
2021-05-25 08:45:26,942 INFO Using Cached DEK
2021-05-25 08:45:26,942 INFO Using Cached DEK
2021-05-25 08:45:26,942 INFO Message authenticity verified
2021-05-25 08:45:26,943 INFO Message authenticity verified
2021-05-25 08:45:26,975 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,975 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,976 INFO Received message ID: 826344897257698
2021-05-25 08:45:26,976 INFO ********** Start PubsubMessage 
2021-05-25 08:45:26,978 INFO Received message ID: 2473035463018475
2021-05-25 08:45:26,979 INFO Received message publish_time: 2021-05-25 12:45:17.170000+00:00
2021-05-25 08:45:26,979 INFO Received message ID: 2473035348079877
2021-05-25 08:45:26,979 INFO Received message publish_time: 2021-05-25 12:45:18.830000+00:00
...
...
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
