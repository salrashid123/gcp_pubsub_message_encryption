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


def getKey(size=32, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


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


class AESCipher(object):

    key = None
    def __init__(self, key):
        self.bs = 32
        self.key = key

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(raw.encode()) + encryptor.finalize()
        return base64.b64encode(iv + ct)

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:16]
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return self._unpad(decryptor.update(enc[16:])) + decryptor.finalize()

    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]

class HMACFunctions(object):

    h = None
    hm_key = None

    def __init__(self, key=None):
      kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'foosalt', iterations=100000, backend=default_backend() )
      if (key is None):
        key = os.urandom(32)
        self.hm_key = kdf.derive(key)
      else:
       self.hm_key = key
      self.h = hmac.HMAC(self.hm_key, hashes.SHA256(), backend=default_backend())

    def getDerivedKey(self):
      return self.hm_key

    def hash(self, msg):
      self.h.update(msg.encode())
      tmp = self.h.copy()
      return base64.b64encode(tmp.finalize())

    def verify(self,signature):
      try:
        self.h.verify(signature)
        return True
      except InvalidSignature as e:
        return False
