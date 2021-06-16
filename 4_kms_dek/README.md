

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


```bash
export PROJECT_ID=`gcloud config get-value core/project`
export PROJECT_NUMBER=`gcloud projects describe $PROJECT_ID --format='value(projectNumber)'`

gcloud pubsub topics create my-new-topic
gcloud pubsub subscriptions create my-new-subscriber --topic=my-new-topic

gcloud iam service-accounts create publisher
gcloud iam service-accounts create subscriber

gcloud kms keyrings create mykeyring  --location=us-central1
gcloud kms keys create key1 --keyring=mykeyring --purpose=encryption --location=us-central1
```

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
$ python publisher.py  --mode encrypt --kms_project_id $PROJECT_ID --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id $PROJECT_ID  --tenantID A

2021-06-16 09:32:44,049 INFO >>>>>>>>>>> Start Encryption with locally generated key.  <<<<<<<<<<<
2021-06-16 09:32:44,049 INFO Rotating symmetric key
2021-06-16 09:32:45,219 INFO Start PubSub Publish
2021-06-16 09:32:45,220 INFO Published Message: AQA7Q8zIH/v0rbXXBHkuUopH1eE6LeQv3Q5jirT8bazhGyKalHePPMG9XyZgEMon1pkR7EhVlruO/2fUMQivyVOQ07Wp5hVW6NEP/kEJkZRnnPmviD2DdAkQITwe8dQNItY0MP59kbeb4VF161/xOyrdF/2u73eAxSuDRoua
2021-06-16 09:32:45,421 INFO Published MessageID: 2543532745509447
2021-06-16 09:32:46,423 INFO Published Message: AQA7Q8zRlMlsZc6VIxb/GFnEZ5ij1R1svjX7DYfNqVzWqxTjlhPC/4fFlvSRJDYGU+r4eqBy34HWaCOULqZAWKBgGPs1yu9cl1rTYUPKPRF7C40aS8fNjhoAQ5UsjgavYEwi/0j/r/hoFaQRL3kzrfBcS7ClNDwzeLsSJxPn
2021-06-16 09:32:46,478 INFO Published MessageID: 2543532618513611
2021-06-16 09:32:47,480 INFO Published Message: AQA7Q8yvCL7TC2LdvrqxsbmryYzBSQ9tYCRlahO+AlGgSFgOQUPFj1OiASbk7EXaEsdZVmHTOoaPVKXh5RVu7hUCONlg6N7aMKCdRVxaWaXHNQG8wPI/svLo8NT0gzQwq10tEqIC9KpIUTaWfBdZyxLL0csJsk0UvbXZI2Wl
2021-06-16 09:32:47,529 INFO Published MessageID: 2543532819450540
2021-06-16 09:32:48,531 INFO Published Message: AQA7Q8yCRsGbz/qY3GZbCzmnT6zvZ+4oWgNd1NBSq8UR/ipinWTBjHzDvSDGJvDWmLLItsFxjCuBLBS2WKzOiHc8FmvDn/Jw5I9IvvByk6rBRd/8bYUmUVhe2nUnNdLCbIlou1/rD1dsbEc/Oiz+ZYnmEejZTIimNY51U+Yj
2021-06-16 09:32:48,577 INFO Published MessageID: 2543531497004157
2021-06-16 09:32:49,579 INFO Published Message: AQA7Q8xuWF3bkV+mcT9ZprI11dfJKH565KaHp/tWB6Nje+OyhhNBv+gur1ietzfAWQByOWXvYMNIRS6nEaC7ShzvW3/PuliBCGI77c5xTCdM7pYwngK/Uf45zepgsuMlB2pfNdXO0wTKnsKjzRXqArE8pXndaJ7wxHJgW01A
2021-06-16 09:32:49,627 INFO Published MessageID: 2543532150634205
2021-06-16 09:32:50,628 INFO Rotating symmetric key
2021-06-16 09:32:51,931 INFO Start PubSub Publish
2021-06-16 09:32:51,931 INFO Published Message: ATHNmLFm/w6albeGbDaUHbDat1tMG87QcosTA8zvokC3hikqUZS9wAP4tOIYnAVkfb28Trpt9FQNHMuCK9j7xGPfVrbgh68gBbG1nqmxQOZUirgBzd35Zs3Tdtg6i2NFxIVaVrO76svwW4XKTvcmigPQxNrPRN/kuUr3ELO5
2021-06-16 09:32:52,065 INFO Published MessageID: 2543583146526083
2021-06-16 09:32:53,066 INFO Published Message: ATHNmLHeHzvQ57ntSTeDKohkRTtBWfgU4pE27IWa40R+jxYGsslBlRZv7PtC+j2GzxkTOkl+ZRvSt3zgdRmTgyKsSsdht8WHlZxDgC/77acgQV21alTpZ2aUUFYeeddtIM6jd7z2Pao9bXkxvKWXRZQkOAOdbIH1LNrQoRtp
2021-06-16 09:32:53,116 INFO Published MessageID: 2543582755397991
2021-06-16 09:32:54,119 INFO Published Message: ATHNmLGD3JUW0kXrgCib0PlLZbsXSfY7y7C8D+i6Olw/dLk6M2R56w7em8e5n5hRoHMGXMYNAbINrA6TXZejYsHuiWBYlVx5COT6EyCOqllBvxM0WfMeDBGEMz2Zbn+J/HqmZfGSwPhxFhFrp/8QyzxYwkrmPnZ6jxpwD8kw
2021-06-16 09:32:54,171 INFO Published MessageID: 2543582693692704
2021-06-16 09:32:55,173 INFO Published Message: ATHNmLFX3rJGUIiSljXSuiJ+vkNkBMTSAdfaCbljwHcu9pOlEM9LKsPUjfGE46zZZb3QDa1xUruTNNoDAeGkAq1MyPujB23ak5osllARDIvD/WSVUquwDj17R0/MrlK8imdrgbxUTWMtF/MyCnZIsEOj0lrs8nph76hLrURf
2021-06-16 09:32:55,223 INFO Published MessageID: 2543582924946524
2021-06-16 09:32:56,225 INFO Published Message: ATHNmLFNQnEEa7Tixckr3YX57wrhvhIbk4DX2bcW4N+Hv/NdtnoG+Jr/Ym0N7MmrZHSRZoes2cvTR31FPBFVgDanbaWi/K9LLdfNy0fZGdvlCChM+SuVSijsGDDP7Ici2vHhM/63UJ9Izd9gTVcsKSpy7b2/+F86+cGVfSBG
2021-06-16 09:32:56,296 INFO Published MessageID: 2543532516578143

     KEY ROTATION
2021-06-16 09:32:57,297 INFO Rotating symmetric key
2021-06-16 09:32:58,522 INFO Start PubSub Publish
2021-06-16 09:32:58,523 INFO Published Message: ATQiFotx85pCkcQZQSOVWo8JBOlfh5Y9jLFHCNTAmjpoF7zq2avhPnEoj8B6ThueqQrleH/kYNWeidTc/KtfSeoafzulpydsAzpwhzAQLgVQ58Fp2mM8wD/qtuuUSC5Zs/tXeHmT+xmnj7dIsgLRFSMUrV5l7PlEMTxfZQ1c
2021-06-16 09:32:58,679 INFO Published MessageID: 2543582867303335
```

- Subscriber:
```log
$ python subscriber.py  --mode decrypt  --pubsub_project_id $PROJECT_ID  --kms_project_id $PROJECT_ID \
    --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --tenantID A

2021-06-16 09:32:37,128 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-06-16 09:32:37,130 INFO Listening for messages on projects/pubsub-msg/subscriptions/my-new-subscriber
2021-06-16 09:32:45,463 INFO ********** Start PubsubMessage 
2021-06-16 09:32:45,463 INFO Received message ID: 2543532745509447
2021-06-16 09:32:45,464 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call
2021-06-16 09:32:45,834 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850365, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:45,834 INFO ********** End PubsubMessage 
2021-06-16 09:32:46,519 INFO ********** Start PubsubMessage 
2021-06-16 09:32:46,520 INFO Received message ID: 2543532618513611
2021-06-16 09:32:46,520 INFO Using Cached DEK
2021-06-16 09:32:46,520 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850366, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:46,520 INFO ********** End PubsubMessage 
2021-06-16 09:32:47,560 INFO ********** Start PubsubMessage 
2021-06-16 09:32:47,561 INFO Received message ID: 2543532819450540
2021-06-16 09:32:47,561 INFO Using Cached DEK
2021-06-16 09:32:47,561 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850367, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:47,562 INFO ********** End PubsubMessage 
2021-06-16 09:32:48,610 INFO ********** Start PubsubMessage 
2021-06-16 09:32:48,610 INFO Received message ID: 2543531497004157
2021-06-16 09:32:48,610 INFO Using Cached DEK
2021-06-16 09:32:48,610 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850368, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:48,610 INFO ********** End PubsubMessage 
2021-06-16 09:32:49,675 INFO ********** Start PubsubMessage 
2021-06-16 09:32:49,675 INFO Received message ID: 2543532150634205
2021-06-16 09:32:49,676 INFO Using Cached DEK
2021-06-16 09:32:49,676 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850369, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:49,676 INFO ********** End PubsubMessage 
2021-06-16 09:32:52,101 INFO ********** Start PubsubMessage 
2021-06-16 09:32:52,101 INFO Received message ID: 2543583146526083
2021-06-16 09:32:52,101 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call
2021-06-16 09:32:52,360 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850371, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:52,361 INFO ********** End PubsubMessage 
2021-06-16 09:32:53,147 INFO ********** Start PubsubMessage 
2021-06-16 09:32:53,147 INFO Received message ID: 2543582755397991
2021-06-16 09:32:53,147 INFO Using Cached DEK
2021-06-16 09:32:53,147 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850373, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:53,148 INFO ********** End PubsubMessage 
2021-06-16 09:32:54,205 INFO ********** Start PubsubMessage 
2021-06-16 09:32:54,205 INFO Received message ID: 2543582693692704
2021-06-16 09:32:54,206 INFO Using Cached DEK
2021-06-16 09:32:54,206 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850374, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:54,206 INFO ********** End PubsubMessage 
2021-06-16 09:32:55,257 INFO ********** Start PubsubMessage 
2021-06-16 09:32:55,257 INFO Received message ID: 2543582924946524
2021-06-16 09:32:55,257 INFO Using Cached DEK
2021-06-16 09:32:55,257 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850375, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:55,257 INFO ********** End PubsubMessage 
2021-06-16 09:32:56,322 INFO ********** Start PubsubMessage 
2021-06-16 09:32:56,322 INFO Received message ID: 2543532516578143
2021-06-16 09:32:56,322 INFO Using Cached DEK
2021-06-16 09:32:56,322 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850376, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:56,322 INFO ********** End PubsubMessage 
2021-06-16 09:32:58,706 INFO ********** Start PubsubMessage 
2021-06-16 09:32:58,706 INFO Received message ID: 2543582867303335

          KEY ROTATION
2021-06-16 09:32:58,706 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call
2021-06-16 09:32:59,005 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850378, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:59,005 INFO ********** End PubsubMessage 
2021-06-16 09:32:59,764 INFO ********** Start PubsubMessage 
2021-06-16 09:32:59,764 INFO Received message ID: 2543532915342246
2021-06-16 09:32:59,764 INFO Using Cached DEK
2021-06-16 09:32:59,764 INFO Decrypted data {"data": "foo", "attributes": {"epoch_time": 1623850379, "a": "aaa", "c": "ccc", "b": "bbb"}}
2021-06-16 09:32:59,764 INFO ********** End PubsubMessage
```

> The code all this can be found in the Appendix



### Signing

For signing, we do something similar where we're singing just what we would put into the ```data:``` field and placing that in a specific PubSubMessage.attribute called ```signature=``` with the signature of the data and other attributes as sturct.

#### Output

- Publisher

```log
$ python publisher.py  --mode sign --kms_project_id $PROJECT_ID  --pubsub_topic my-new-topic   --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --pubsub_project_id $PROJECT_ID --tenantID A

2021-06-16 09:35:25,837 INFO >>>>>>>>>>> Start Sign with with locally generated key. <<<<<<<<<<<
2021-06-16 09:35:25,837 INFO Rotating key
2021-06-16 09:35:26,994 INFO Start PubSub Publish
2021-06-16 09:35:26,995 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850526, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:26,995 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:27,419 INFO Published MessageID: 2543533077819253
2021-06-16 09:35:27,419 INFO Start PubSub Publish
2021-06-16 09:35:27,420 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850527, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:27,421 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:27,471 INFO Published MessageID: 2543532581718611
2021-06-16 09:35:27,472 INFO Start PubSub Publish
2021-06-16 09:35:27,473 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850527, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:27,473 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:27,523 INFO Published MessageID: 2543582807778265
2021-06-16 09:35:27,524 INFO Start PubSub Publish
2021-06-16 09:35:27,525 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850527, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:27,525 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:27,577 INFO Published MessageID: 2543532930940451
2021-06-16 09:35:27,577 INFO Start PubSub Publish
2021-06-16 09:35:27,582 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850527, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:27,582 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:27,631 INFO Published MessageID: 2543582846019830

    KEY ROTATION
2021-06-16 09:35:27,631 INFO Rotating key
2021-06-16 09:35:28,867 INFO Start PubSub Publish
2021-06-16 09:35:28,868 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850528, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:28,868 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,108 INFO Published MessageID: 2543582698062561
2021-06-16 09:35:29,109 INFO Start PubSub Publish
2021-06-16 09:35:29,110 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850529, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:29,110 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,159 INFO Published MessageID: 2543582671552107
2021-06-16 09:35:29,159 INFO Start PubSub Publish
2021-06-16 09:35:29,160 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850529, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:29,161 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,209 INFO Published MessageID: 2543582582039585
2021-06-16 09:35:29,210 INFO Start PubSub Publish
2021-06-16 09:35:29,211 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850529, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:29,211 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,259 INFO Published MessageID: 2543532351799816
2021-06-16 09:35:29,259 INFO Start PubSub Publish
2021-06-16 09:35:29,260 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850529, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:29,261 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,306 INFO Published MessageID: 2543582536543905
2021-06-16 09:35:29,306 INFO Rotating key
2021-06-16 09:35:30,468 INFO Start PubSub Publish
2021-06-16 09:35:30,469 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850530, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:30,469 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:30,738 INFO Published MessageID: 2543582862655097
2021-06-16 09:35:30,738 INFO Start PubSub Publish
2021-06-16 09:35:30,739 INFO Published Message: {'data': b'foo', 'attributes': {'epoch_time': 1623850530, 'a': 'aaa', 'c': 'ccc', 'b': 'bbb'}}
2021-06-16 09:35:30,740 INFO  with key_id: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:30,791 INFO Published MessageID: 2543583002368912
```

- Subscriber
```log
$ python subscriber.py  --mode verify  --pubsub_project_id $PROJECT_ID --kms_project_id $PROJECT_ID \
   --pubsub_topic my-new-topic --pubsub_subscription my-new-subscriber --kms_location us-central1 --kms_key_ring_id mykeyring --kms_key_id key1 --tenantID A

2021-06-16 09:35:17,089 INFO >>>>>>>>>>> Start <<<<<<<<<<<
2021-06-16 09:35:17,091 INFO Listening for messages on projects/pubsub-msg/subscriptions/my-new-subscriber
2021-06-16 09:35:28,299 INFO ********** Start PubsubMessage 
2021-06-16 09:35:28,300 INFO Received message ID: 2543533077819253
2021-06-16 09:35:28,300 INFO Received message publish_time: 2021-06-16 13:35:27.328000+00:00
2021-06-16 09:35:28,302 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:28,303 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIIePDJoxTzWQaM9qzNe26qGPUJnjl9Y2U6XyexcWWVcSmQEACLNrX2GeO2a8Ri2rQFI9xvBRN7vdO99g3ZISEvTRcbSsPbsPJFQKpA+VC/vWD08M/kULCVBi4IJrw+bbNBVghACJRQjvrvsQxDlFP1NCBF2lsO1iPw8/SLzwAR1FamlFPAL4Xp8YvQz5vyPCyt+hBQ1RWvXPa/JVuQ5qWJRVU4nj7Zz6wZLK48pCZprLiZ2fIr7vQZb6TqQaQgipwvz8BhI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYqcL8/AYgAQ==
2021-06-16 09:35:28,303 INFO Received message attributes["signature"]: AW+fISnS5H3ZlH5+rurTE/QxoQElFY7kkv9PQl9L2YrmAvzYAQ==
2021-06-16 09:35:28,304 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call
2021-06-16 09:35:28,646 INFO End KMS decryption API call
2021-06-16 09:35:28,647 INFO Message authenticity verified
2021-06-16 09:35:28,647 INFO ********** Start PubsubMessage 
2021-06-16 09:35:28,647 INFO ********** Start PubsubMessage 
2021-06-16 09:35:28,648 INFO ********** Start PubsubMessage 
2021-06-16 09:35:28,648 INFO Received message ID: 2543532581718611
2021-06-16 09:35:28,648 INFO ********** Start PubsubMessage 
2021-06-16 09:35:28,648 INFO Received message ID: 2543582807778265
2021-06-16 09:35:28,648 INFO Received message publish_time: 2021-06-16 13:35:27.515000+00:00
2021-06-16 09:35:28,648 INFO Received message publish_time: 2021-06-16 13:35:27.467000+00:00
2021-06-16 09:35:28,648 INFO Received message ID: 2543582846019830
2021-06-16 09:35:28,649 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:28,648 INFO Received message ID: 2543532930940451
2021-06-16 09:35:28,649 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:28,649 INFO Received message publish_time: 2021-06-16 13:35:27.626000+00:00
2021-06-16 09:35:28,649 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIIePDJoxTzWQaM9qzNe26qGPUJnjl9Y2U6XyexcWWVcSmQEACLNrX2GeO2a8Ri2rQFI9xvBRN7vdO99g3ZISEvTRcbSsPbsPJFQKpA+VC/vWD08M/kULCVBi4IJrw+bbNBVghACJRQjvrvsQxDlFP1NCBF2lsO1iPw8/SLzwAR1FamlFPAL4Xp8YvQz5vyPCyt+hBQ1RWvXPa/JVuQ5qWJRVU4nj7Zz6wZLK48pCZprLiZ2fIr7vQZb6TqQaQgipwvz8BhI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYqcL8/AYgAQ==
2021-06-16 09:35:28,649 INFO Received message publish_time: 2021-06-16 13:35:27.571000+00:00
2021-06-16 09:35:28,649 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIIePDJoxTzWQaM9qzNe26qGPUJnjl9Y2U6XyexcWWVcSmQEACLNrX2GeO2a8Ri2rQFI9xvBRN7vdO99g3ZISEvTRcbSsPbsPJFQKpA+VC/vWD08M/kULCVBi4IJrw+bbNBVghACJRQjvrvsQxDlFP1NCBF2lsO1iPw8/SLzwAR1FamlFPAL4Xp8YvQz5vyPCyt+hBQ1RWvXPa/JVuQ5qWJRVU4nj7Zz6wZLK48pCZprLiZ2fIr7vQZb6TqQaQgipwvz8BhI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYqcL8/AYgAQ==
2021-06-16 09:35:28,649 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:28,649 INFO Received message attributes["signature"]: AW+fISlMX2vPDr5vfPJErF9ReWN8jzsZ14h1QM0hZDtKMAAeqA==
2021-06-16 09:35:28,649 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:28,649 INFO Received message attributes["signature"]: AW+fISlMX2vPDr5vfPJErF9ReWN8jzsZ14h1QM0hZDtKMAAeqA==
2021-06-16 09:35:28,649 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIIePDJoxTzWQaM9qzNe26qGPUJnjl9Y2U6XyexcWWVcSmQEACLNrX2GeO2a8Ri2rQFI9xvBRN7vdO99g3ZISEvTRcbSsPbsPJFQKpA+VC/vWD08M/kULCVBi4IJrw+bbNBVghACJRQjvrvsQxDlFP1NCBF2lsO1iPw8/SLzwAR1FamlFPAL4Xp8YvQz5vyPCyt+hBQ1RWvXPa/JVuQ5qWJRVU4nj7Zz6wZLK48pCZprLiZ2fIr7vQZb6TqQaQgipwvz8BhI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYqcL8/AYgAQ==
2021-06-16 09:35:28,649 INFO Using Cached DEK
2021-06-16 09:35:28,649 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIIePDJoxTzWQaM9qzNe26qGPUJnjl9Y2U6XyexcWWVcSmQEACLNrX2GeO2a8Ri2rQFI9xvBRN7vdO99g3ZISEvTRcbSsPbsPJFQKpA+VC/vWD08M/kULCVBi4IJrw+bbNBVghACJRQjvrvsQxDlFP1NCBF2lsO1iPw8/SLzwAR1FamlFPAL4Xp8YvQz5vyPCyt+hBQ1RWvXPa/JVuQ5qWJRVU4nj7Zz6wZLK48pCZprLiZ2fIr7vQZb6TqQaQgipwvz8BhI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYqcL8/AYgAQ==
2021-06-16 09:35:28,649 INFO Using Cached DEK
2021-06-16 09:35:28,649 INFO Received message attributes["signature"]: AW+fISlMX2vPDr5vfPJErF9ReWN8jzsZ14h1QM0hZDtKMAAeqA==
2021-06-16 09:35:28,649 INFO Message authenticity verified
2021-06-16 09:35:28,649 INFO Received message attributes["signature"]: AW+fISlMX2vPDr5vfPJErF9ReWN8jzsZ14h1QM0hZDtKMAAeqA==
2021-06-16 09:35:28,649 INFO Message authenticity verified
2021-06-16 09:35:28,649 INFO Using Cached DEK
2021-06-16 09:35:28,650 INFO Using Cached DEK
2021-06-16 09:35:28,650 INFO Message authenticity verified
2021-06-16 09:35:28,650 INFO Message authenticity verified
2021-06-16 09:35:29,137 INFO ********** Start PubsubMessage 
2021-06-16 09:35:29,138 INFO Received message ID: 2543582698062561
2021-06-16 09:35:29,138 INFO Received message publish_time: 2021-06-16 13:35:29.102000+00:00
2021-06-16 09:35:29,138 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,139 INFO Received message attributes["sign_key_wrapped"]: EsABCiQArw4RIN6kBC2k28YV+7nTCpNEAdHooZj6U1Ug/3o8DFPlYuoSlwEACLNrX+ge6eZW8mmSMoo9v7Pdyx+0ssy4Jxb1ul0OHsFcFL/Pg3+WYdY0yo/nAbSPYegDwEA4wrna5z9yeBV9vaESogFrLlrV2YKB9PnNE2TQwBHvvzkz4aO4Son+r+JnKZF9cEx94bP4uHb/FS3NLmdXZOKuJ5ef/7F0xn8kiB1pwzw6y2AR3G4TZ7Z8R1SNgyK1EAzZGkAIm/nfCxI5Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYm/nfCyAB
2021-06-16 09:35:29,139 INFO Received message attributes["signature"]: AQF3/Jt3WnnGowT9662Y6cM8vyO9lGYYfhzidFTU0/LUEyi3pg==
2021-06-16 09:35:29,139 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call

    KEY ROTATION
2021-06-16 09:35:29,370 INFO End KMS decryption API call
2021-06-16 09:35:29,371 INFO Message authenticity verified
2021-06-16 09:35:29,402 INFO ********** Start PubsubMessage 
2021-06-16 09:35:29,402 INFO Received message ID: 2543582671552107
2021-06-16 09:35:29,403 INFO Received message publish_time: 2021-06-16 13:35:29.153000+00:00
2021-06-16 09:35:29,403 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,403 INFO Received message attributes["sign_key_wrapped"]: EsABCiQArw4RIN6kBC2k28YV+7nTCpNEAdHooZj6U1Ug/3o8DFPlYuoSlwEACLNrX+ge6eZW8mmSMoo9v7Pdyx+0ssy4Jxb1ul0OHsFcFL/Pg3+WYdY0yo/nAbSPYegDwEA4wrna5z9yeBV9vaESogFrLlrV2YKB9PnNE2TQwBHvvzkz4aO4Son+r+JnKZF9cEx94bP4uHb/FS3NLmdXZOKuJ5ef/7F0xn8kiB1pwzw6y2AR3G4TZ7Z8R1SNgyK1EAzZGkAIm/nfCxI5Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYm/nfCyAB
2021-06-16 09:35:29,403 INFO Received message attributes["signature"]: AQF3/JsRcFlud+18dvTsxpGlFQ4aZX0BfKacY5OHM3JfNjdrQw==
2021-06-16 09:35:29,403 INFO Using Cached DEK
2021-06-16 09:35:29,404 INFO Message authenticity verified
2021-06-16 09:35:29,437 INFO ********** Start PubsubMessage 
2021-06-16 09:35:29,438 INFO Received message ID: 2543582582039585
2021-06-16 09:35:29,439 INFO Received message publish_time: 2021-06-16 13:35:29.203000+00:00
2021-06-16 09:35:29,442 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,442 INFO Received message attributes["sign_key_wrapped"]: EsABCiQArw4RIN6kBC2k28YV+7nTCpNEAdHooZj6U1Ug/3o8DFPlYuoSlwEACLNrX+ge6eZW8mmSMoo9v7Pdyx+0ssy4Jxb1ul0OHsFcFL/Pg3+WYdY0yo/nAbSPYegDwEA4wrna5z9yeBV9vaESogFrLlrV2YKB9PnNE2TQwBHvvzkz4aO4Son+r+JnKZF9cEx94bP4uHb/FS3NLmdXZOKuJ5ef/7F0xn8kiB1pwzw6y2AR3G4TZ7Z8R1SNgyK1EAzZGkAIm/nfCxI5Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYm/nfCyAB
2021-06-16 09:35:29,442 INFO Received message attributes["signature"]: AQF3/JsRcFlud+18dvTsxpGlFQ4aZX0BfKacY5OHM3JfNjdrQw==
2021-06-16 09:35:29,442 INFO Using Cached DEK
2021-06-16 09:35:29,443 INFO Message authenticity verified
2021-06-16 09:35:29,475 INFO ********** Start PubsubMessage 
2021-06-16 09:35:29,475 INFO Received message ID: 2543532351799816
2021-06-16 09:35:29,476 INFO Received message publish_time: 2021-06-16 13:35:29.251000+00:00
2021-06-16 09:35:29,477 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,477 INFO Received message attributes["sign_key_wrapped"]: EsABCiQArw4RIN6kBC2k28YV+7nTCpNEAdHooZj6U1Ug/3o8DFPlYuoSlwEACLNrX+ge6eZW8mmSMoo9v7Pdyx+0ssy4Jxb1ul0OHsFcFL/Pg3+WYdY0yo/nAbSPYegDwEA4wrna5z9yeBV9vaESogFrLlrV2YKB9PnNE2TQwBHvvzkz4aO4Son+r+JnKZF9cEx94bP4uHb/FS3NLmdXZOKuJ5ef/7F0xn8kiB1pwzw6y2AR3G4TZ7Z8R1SNgyK1EAzZGkAIm/nfCxI5Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYm/nfCyAB
2021-06-16 09:35:29,477 INFO Received message attributes["signature"]: AQF3/JsRcFlud+18dvTsxpGlFQ4aZX0BfKacY5OHM3JfNjdrQw==
2021-06-16 09:35:29,477 INFO Using Cached DEK
2021-06-16 09:35:29,478 INFO Message authenticity verified
2021-06-16 09:35:29,511 INFO ********** Start PubsubMessage 
2021-06-16 09:35:29,511 INFO Received message ID: 2543582536543905
2021-06-16 09:35:29,511 INFO Received message publish_time: 2021-06-16 13:35:29.301000+00:00
2021-06-16 09:35:29,512 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:29,512 INFO Received message attributes["sign_key_wrapped"]: EsABCiQArw4RIN6kBC2k28YV+7nTCpNEAdHooZj6U1Ug/3o8DFPlYuoSlwEACLNrX+ge6eZW8mmSMoo9v7Pdyx+0ssy4Jxb1ul0OHsFcFL/Pg3+WYdY0yo/nAbSPYegDwEA4wrna5z9yeBV9vaESogFrLlrV2YKB9PnNE2TQwBHvvzkz4aO4Son+r+JnKZF9cEx94bP4uHb/FS3NLmdXZOKuJ5ef/7F0xn8kiB1pwzw6y2AR3G4TZ7Z8R1SNgyK1EAzZGkAIm/nfCxI5Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYm/nfCyAB
2021-06-16 09:35:29,512 INFO Received message attributes["signature"]: AQF3/JsRcFlud+18dvTsxpGlFQ4aZX0BfKacY5OHM3JfNjdrQw==
2021-06-16 09:35:29,512 INFO Using Cached DEK
2021-06-16 09:35:29,512 INFO Message authenticity verified
2021-06-16 09:35:30,772 INFO ********** Start PubsubMessage 
2021-06-16 09:35:30,773 INFO Received message ID: 2543582862655097
2021-06-16 09:35:30,773 INFO Received message publish_time: 2021-06-16 13:35:30.726000+00:00
2021-06-16 09:35:30,773 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:30,773 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIJl0e+2uu8Uy9xsK4KtCAtAC4yH/AgCXNG3oH9ZOsNsSmQEACLNrX5MfAj68EA44j+rNIjm4qwjffzcEP7p/7PxZWOSZ43O1pUObZvnqJkc1xvhE4N0TP77QOmCkMl6SdJhgly+Xf99ukCnfOgmxODYMgGAs4fAXlvryVp6lskk2mqaJUOztAf4ad5BbVmslwiNeA9JVO6nbaFRCjx3ToTyo8g8irzsUpbi2X3Wt0+ktp5gFgiazfSaZ0hwaQgiVyMzIARI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYlcjMyAEgAQ==
2021-06-16 09:35:30,773 INFO Received message attributes["signature"]: ARkTJBUwch20ciXOEL1vuzT/+4j1Rxo9Tv+mANrw/5lP0cDrJQ==
2021-06-16 09:35:30,773 INFO >>>>>>>>>>>>>>>>   Starting KMS decryption API call
2021-06-16 09:35:31,021 INFO End KMS decryption API call
2021-06-16 09:35:31,021 INFO Message authenticity verified
2021-06-16 09:35:31,027 INFO ********** Start PubsubMessage 
2021-06-16 09:35:31,027 INFO Received message ID: 2543583002368912
2021-06-16 09:35:31,027 INFO Received message publish_time: 2021-06-16 13:35:30.786000+00:00
2021-06-16 09:35:31,027 INFO Received message attributes["kms_key"]: projects/pubsub-msg/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1
2021-06-16 09:35:31,027 INFO Received message attributes["sign_key_wrapped"]: EsIBCiQArw4RIJl0e+2uu8Uy9xsK4KtCAtAC4yH/AgCXNG3oH9ZOsNsSmQEACLNrX5MfAj68EA44j+rNIjm4qwjffzcEP7p/7PxZWOSZ43O1pUObZvnqJkc1xvhE4N0TP77QOmCkMl6SdJhgly+Xf99ukCnfOgmxODYMgGAs4fAXlvryVp6lskk2mqaJUOztAf4ad5BbVmslwiNeA9JVO6nbaFRCjx3ToTyo8g8irzsUpbi2X3Wt0+ktp5gFgiazfSaZ0hwaQgiVyMzIARI6Ci50eXBlLmdvb2dsZWFwaXMuY29tL2dvb2dsZS5jcnlwdG8udGluay5IbWFjS2V5EAEYlcjMyAEgAQ==
2021-06-16 09:35:31,028 INFO Received message attributes["signature"]: ARkTJBUwch20ciXOEL1vuzT/+4j1Rxo9Tv+mANrw/5lP0cDrJQ==
2021-06-16 09:35:31,028 INFO Using Cached DEK
2021-06-16 09:35:31,028 INFO Message authenticity verified
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
