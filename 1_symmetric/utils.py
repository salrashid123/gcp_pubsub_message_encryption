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
import io
import tink
from tink import aead
from tink import tink_config
from tink import mac
from tink.proto import tink_pb2
from tink.proto import common_pb2
from tink.integration import gcpkms
from tink import core

from tink import cleartext_keyset_handle

tink_config.register()
aead.register()
mac.register()


class AESCipher(object):

    def __init__(self, encoded_key, key_uri=None):
      self.gcp_aead = None
      if key_uri != None:
        gcp_client = gcpkms.GcpKmsClient(key_uri=key_uri,credentials_path="")
        self.gcp_aead = gcp_client.get_aead(key_uri)
        if (encoded_key==None):
          self.keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
        else:
          reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))          
          self.keyset_handle = tink.KeysetHandle.read(reader, self.gcp_aead)
      else:
        if (encoded_key==None):
          self.keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
        else:
          reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))
          self.keyset_handle = cleartext_keyset_handle.read(reader)        

      self.key=self.keyset_handle.keyset_info()
      self.aead_primitive = self.keyset_handle.primitive(aead.Aead)

    def getKey(self):
      iostream = io.BytesIO()
      writer = tink.BinaryKeysetWriter(iostream)      
      if self.gcp_aead != None:
        self.keyset_handle.write(writer,self.gcp_aead)
      else:
        writer.write(self.keyset_handle._keyset)
      encoded_key = base64.b64encode(iostream.getvalue()).decode('utf-8')
      return base64.b64encode(iostream.getvalue()).decode('utf-8')

    def printKeyInfo(self):
      stream = io.StringIO()
      writer = tink.JsonKeysetWriter(stream)    
      cleartext_keyset_handle.write(writer, self.keyset_handle)
      return stream.getvalue()

    def encrypt(self, plaintext, associated_data):
      try:
        ciphertext = self.aead_primitive.encrypt(plaintext, associated_data.encode('utf-8'))
        base64_bytes = base64.b64encode(ciphertext)
        return (base64_bytes.decode('utf-8'))  
      except tink.TinkError as e:
        raise e

    def decrypt(self, ciphertext, associated_data):
      try:
        plaintext = self.aead_primitive.decrypt(base64.b64decode(ciphertext), associated_data.encode('utf-8'))
        return(plaintext.decode('utf-8'))
      except tink.TinkError as e:
        raise e

class HMACFunctions(object):

    def __init__(self, encoded_key, key_uri=None):
      self.gcp_aead = None
      if key_uri != None:
        gcp_client = gcpkms.GcpKmsClient(key_uri=key_uri,credentials_path="")
        self.gcp_aead = gcp_client.get_aead(key_uri)
        if (encoded_key==None):
          self.keyset_handle = tink.new_keyset_handle(mac.mac_key_templates.HMAC_SHA256_256BITTAG)
        else:
          reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))          
          self.keyset_handle = tink.KeysetHandle.read(reader, self.gcp_aead)
      else:
        if (encoded_key==None):
          self.keyset_handle = tink.new_keyset_handle(mac.mac_key_templates.HMAC_SHA256_256BITTAG)
        else:
          reader = tink.BinaryKeysetReader(base64.b64decode(encoded_key))
          self.keyset_handle = cleartext_keyset_handle.read(reader)        
      self.mac = self.keyset_handle.primitive(mac.Mac)

    def printKeyInfo(self):
      stream = io.StringIO()
      writer = tink.JsonKeysetWriter(stream)    
      cleartext_keyset_handle.write(writer, self.keyset_handle)
      return stream.getvalue()

    def getKey(self):
      iostream = io.BytesIO()
      writer = tink.BinaryKeysetWriter(iostream)      
      if self.gcp_aead != None:
        self.keyset_handle.write(writer,self.gcp_aead)
      else:
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
        raise e

## example of using kms encrypted keysets...
# keyURI="gcp-kms://projects/mineral-minutia-820/locations/us-central1/keyRings/mykeyring/cryptoKeys/key1"

# print("AES")
# cc = AESCipher(encoded_key=None,key_uri=keyURI)
# k = cc.getKey()
# print(cc.printKeyInfo())


# cc = AESCipher(encoded_key=k,key_uri=keyURI)
# enc=cc.encrypt("foo".encode('utf-8'),"none")
# print(enc)
# dec = cc.decrypt(enc,"none")
# print(dec)

# print("HMAC")

# h = HMACFunctions(encoded_key=None,key_uri=keyURI)
# k = h.getKey()
# print(h.printKeyInfo())

# h = HMACFunctions(encoded_key=k,key_uri=keyURI)
# dd = "dsfas"
# hashed=h.hash(dd.encode('utf-8'))
# print(base64.b64encode(hashed).decode('utf-8'))
# print(h.verify(dd.encode('utf-8'),base64.b64decode(hashed)))