# Message Payload Encryption in Google Cloud Pub/Sub

## Introduction

This is the first in a series of articles covering techniques to encrypt and sign the metadata and payload for a [Google Cloud PubSub](https://cloud.google.com/pubsub/) Message. While almost in every case you use [Pub/Sub IAM access control](https://cloud.google.com/pubsub/docs/access-control#permissions) to limit who can push/pull messages on Topics and Subscriptions, there are situations where you would want to fortify the message data with encryption for confidentiality or sign it to ensure integrity and authentication.

Lets cover IAM briefly.  Google's IAM system allows administrators to assign roles with specific permissions at the resource level to identities.  In the context for PubSub, an
administrator cay say "Allow Alice access to put messages on Topic T1 and allow Bob access to create Subscriptions to pull messages from Topic T1".  With those rules, you have controlled access to resources (Topics, Subscriptions).   When Alice or Bob uses Pub/Sub, the [transport is always secure](https://cloud.google.com/pubsub/docs/faq#security) and any message stored on Google that are pending is persisted with encryption.  

This works great for almost all usecases but the message _payload_ as received by any Subscriber is not encrypted.  What I mean by that is once Bob get a message, the data itself is not encrypted.  Why would we want to encrypt or sign the data? Well, there are several reasons:  

* You have multiple subscriptions on a Topic and you don't want all Subscribers access to the message payload.  For example, Topic T1 has Subscriptions created by both Bob and Eve.  Alice wants to send a Pub/Sub message such that only Bob can use it but not Eve. One way is if Alice encrypts the message data and metadata with a Key that only Bob has access to.  once Bob gets the message he decrypts or verifies the message from Alice. This type of single Topic with multiple subscriptions comes up if you use Pub/Sub as a type of common message bus.

* You need message authentication and integrity checks but not confidentiality.  Suppose you allow Carol to also put messages on Topic T1 and Bob is the only subscriber.  One way to do that is to sign some of the critical data in the PubSub message using a unique key for Alice and another for Carol.  When Alice decides to send a message, she uses her key to sign the message, then attach the signature as an attribute and send it on the topic.  Both Bob and Even can get this message but they can use a shared secret or public key to verify the integrity of the message data and at the same time know Alice send the message

* You enable Pubsub "Snapshot and Seek" feature that allows users to replay historical messages.  Suppose you Alice is placing unencrypted messages on Topic T1 and Bob is the only subscriber.  Everything is working great but later on you remove Bob and add Eve.  You don't want Eve to read Bob's messages ever.  If a snapshot and replay ever spans over Bobs timeline for subscriptions, Even will now receive unencrypted messages that originally only Bob should see.

* You need to persist Messages with encryption for Compliance reasons or enhanced security.

* You use PubSub Push subscriptions and you want want the webhook server to verify the message came from a particular source.  Normally, you use a pre-determined static token appended to the webhook to verify (eg ```?token=application-secret.``` as described in the [PubSub FAQ](https://cloud.google.com/pubsub/docs/faq#security)).  With message signatures, you now have a stronger signal accept or reject a message authenticity claim.

As a last note, in these situations where you need access complete tenant isolation, you would normally create two Topics, T1,T2 and create IAM rules for each for Bob and Eve to create appropriate subscriptions.  The rest of this article covers techniques if you need to construct a common message bus where multiple topics are not feasible.


The git repo here is broken down into four parts with code samples:

- 1: Pure symmetric encryption/signing
- 2: Using GCP service accounts to sign and encrypt
- 3: Using GCP Key Management System (KMS) alone
- 4: Using GCP KMS to wrap data encryption keys and signing keys

## Disclaimer

The techniques and code contained here is not supported by google and is provided as-is (the corresponding git repo is under Apache license). It seeks to provide some options you can investigate, evaluate and employ if you choose to.

(as of 6/30/20, this repo and the code there has been tested with Python 3.7.  

>> in any of these samples, please flush the pubsub queue if you want to test other modes (i.,e messages intended for `sign` cannot be processed by subscribers configured for `decrypt`)