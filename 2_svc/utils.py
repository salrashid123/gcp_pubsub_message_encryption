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
import binascii
import hashlib
import hmac
import io
import json
import os
import random
import string

import tink
from cryptography.exceptions import InvalidKey, InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac, padding
from cryptography.hazmat.primitives.asymmetric import dsa, rsa
from cryptography.hazmat.primitives.asymmetric.padding import MGF1, OAEP
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate
from tink import aead, cleartext_keyset_handle, core, mac, tink_config
from tink.integration import gcpkms
from tink.proto import common_pb2, tink_pb2


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
      if (encoded_key==None):
        self.keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
      else:
        reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))
        self.keyset_handle = cleartext_keyset_handle.read(reader)
      self.key=self.keyset_handle.keyset_info()
      self.aead_primitive = self.keyset_handle.primitive(aead.Aead)

    def printKeyInfo(self):
      stream = io.StringIO()
      writer = tink.JsonKeysetWriter(stream)    
      cleartext_keyset_handle.write(writer, self.keyset_handle)
      return stream.getvalue()

    def getKey(self):
      iostream = io.BytesIO()
      writer = tink.BinaryKeysetWriter(iostream)      
      cleartext_keyset_handle.write(writer, self.keyset_handle)
      encoded_key = base64.b64encode(iostream.getvalue()).decode('utf-8')
      return encoded_key

    def encrypt(self, plaintext, associated_data):
      ciphertext = self.aead_primitive.encrypt(plaintext, associated_data.encode('utf-8'))
      base64_bytes = base64.b64encode(ciphertext)
      return (base64_bytes.decode('utf-8'))  

    def decrypt(self, ciphertext, associated_data):
      plaintext = self.aead_primitive.decrypt(base64.b64decode(ciphertext), associated_data.encode('utf-8'))
      return(plaintext.decode('utf-8'))

