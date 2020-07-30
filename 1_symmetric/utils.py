#!/bin/python

# Copyright 2018 Google Inc. All rights reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import hashlib
import hmac
import binascii

import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding, hmac
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidKey

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dsa, rsa
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from cryptography.x509 import load_pem_x509_certificate
from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1
from cryptography.exceptions import InvalidSignature
import string
import random
import json

import base64
import io
import tink
from tink import aead
from tink import tink_config
from tink import mac
from tink.proto import tink_pb2
from tink.proto import common_pb2
from tink import core

from tink import cleartext_keyset_handle


class RSACipher(object):

   public_key = None
   private_key = None

   def __init__(self, public_key_pem = None, private_key = None):
     if public_key_pem  is not None:
       self.public_key = load_pem_x509_certificate(public_key_pem.encode(), backend=default_backend()).public_key()
     if private_key is not None:
       self.private_key = private_key

   def encrypt(self, raw):
     return  base64.b64encode(self.public_key.encrypt(
       raw, OAEP( mgf=MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),label=None)))

   def decrypt(self, raw):
     return  self.private_key.decrypt(base64.b64decode(raw), OAEP( mgf=MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(), label=None )).decode('utf-8').strip()


tink_config.register()
aead.register()
mac.register()

class AESCipher(object):

    def __init__(self, encoded_key):
      tink_config.register()
      aead.register()

      if (encoded_key==None):
        self.keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
      else:
        reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))
        self.keyset_handle = cleartext_keyset_handle.read(reader)
      self.key=self.keyset_handle.keyset_info()
      self.aead_primitive = self.keyset_handle.primitive(aead.Aead)

    def printKey(self):
      print(self.keyset_handle.keyset_info())

    def getKey(self):
      iostream = io.BytesIO()
      writer = tink.BinaryKeysetWriter(iostream)
      writer.write(self.keyset_handle._keyset)
      encoded_key = base64.b64encode(iostream.getvalue()).decode('utf-8')
      return base64.b64encode(iostream.getvalue()).decode('utf-8')
      

    def encrypt(self, plaintext, associated_data):
      ciphertext = self.aead_primitive.encrypt(plaintext, associated_data.encode('utf-8'))
      base64_bytes = base64.b64encode(ciphertext)
      return (base64_bytes.decode('utf-8'))  

    def decrypt(self, ciphertext, associated_data):
      plaintext = self.aead_primitive.decrypt(base64.b64decode(ciphertext), associated_data.encode('utf-8'))
      return(plaintext.decode('utf-8'))

class HMACFunctions(object):

    def __init__(self, encoded_key=None):
      if encoded_key == None:
        self.keyset_handle = tink.new_keyset_handle(mac.mac_key_templates.HMAC_SHA256_256BITTAG)
      else:
        reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))
        self.keyset_handle = cleartext_keyset_handle.read(reader)
      self.mac = self.keyset_handle.primitive(mac.Mac)

    def printKey(self):
      print(self.keyset_handle.keyset_info())

    def getKey(self):
      iostream = io.BytesIO()
      writer = tink.BinaryKeysetWriter(iostream)
      writer.write(self.keyset_handle._keyset)
      encoded_key = base64.b64encode(iostream.getvalue()).decode('utf-8')
      return base64.b64encode(iostream.getvalue()).decode('utf-8')

    def hash(self, msg):
      tag = self.mac.compute_mac(msg)
      return base64.b64encode(tag)

    def verify(self,data, signature):
      try:
        self.mac.verify_mac(signature, data)
        return True
      except tink.TinkError as e:
        return False
 