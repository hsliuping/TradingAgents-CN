# Copyright (c) Alibaba, Inc. and its affiliates.
import base64
import json
from dataclasses import dataclass
import os
from typing import Optional

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

import dashscope
from dashscope.common.constants import ENCRYPTION_AES_SECRET_KEY_BYTES, ENCRYPTION_AES_IV_LENGTH
from dashscope.common.logging import logger


class Encryption:
    def __init__(self):
        self.pub_key_id: str = ''
        self.pub_key_str: str = ''
        self.aes_key_bytes: bytes = b''
        self.encrypted_aes_key_str: str = ''
        self.iv_bytes: bytes = b''
        self.base64_iv_str: str = ''
        self.valid: bool = False

    def initialize(self):
        public_keys = self._get_public_keys()
        if not public_keys:
            return

        public_key_str = public_keys.get('public_key')
        public_key_id = public_keys.get('public_key_id')
        if not public_key_str or not public_key_id:
            logger.error("public keys data not valid")
            return

        aes_key_bytes = self._generate_aes_secret_key()
        iv_bytes = self._generate_iv()

        encrypted_aes_key_str = self._encrypt_aes_key_with_rsa(aes_key_bytes, public_key_str)
        base64_iv_str = base64.b64encode(iv_bytes).decode('utf-8')

        self.pub_key_id = public_key_id
        self.pub_key_str = public_key_str
        self.aes_key_bytes = aes_key_bytes
        self.encrypted_aes_key_str = encrypted_aes_key_str
        self.iv_bytes = iv_bytes
        self.base64_iv_str = base64_iv_str

        self.valid = True

    def encrypt(self, dict_plaintext):
        return self._encrypt_text_with_aes(json.dumps(dict_plaintext, ensure_ascii=False),
                                           self.aes_key_bytes, self.iv_bytes)

    def decrypt(self, base64_ciphertext):
        return self._decrypt_text_with_aes(base64_ciphertext, self.aes_key_bytes, self.iv_bytes)

    def is_valid(self):
        return self.valid

    def get_pub_key_id(self):
        return self.pub_key_id

    def get_encrypted_aes_key_str(self):
        return self.encrypted_aes_key_str

    def get_base64_iv_str(self):
        return self.base64_iv_str

    @staticmethod
    def _get_public_keys():
        url = dashscope.base_http_api_url + '/public-keys/latest'
        headers = {
            "Authorization": f"Bearer {dashscope.api_key}"
        }

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            logger.error("exceptional public key response: %s" % response)
            return None

        json_resp = response.json()
        response_data = json_resp.get('data')

        if not response_data:
            logger.error("no valid data in public key response")
            return None

        return response_data

    @staticmethod
    def _generate_aes_secret_key():
        return os.urandom(ENCRYPTION_AES_SECRET_KEY_BYTES)

    @staticmethod
    def _generate_iv():
        return os.urandom(ENCRYPTION_AES_IV_LENGTH)

    @staticmethod
    def _encrypt_text_with_aes(plaintext, key, iv):
        """使用AES-GCM加密数据"""

        # 创建AES-GCM加密器
        aes_gcm = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag=None),
            backend=default_backend()
        ).encryptor()

        # 关联数据设为空（根据需求可调整）
        aes_gcm.authenticate_additional_data(b'')

        # 加密数据
        ciphertext = aes_gcm.update(plaintext.encode('utf-8')) + aes_gcm.finalize()

        # 获取认证标签
        tag = aes_gcm.tag

        # 组合密文和标签
        encrypted_data = ciphertext + tag

        # 返回Base64编码结果
        return base64.b64encode(encrypted_data).decode('utf-8')

    @staticmethod
    def _decrypt_text_with_aes(base64_ciphertext, aes_key, iv):
        """使用AES-GCM解密响应"""

        # 解码Base64数据
        encrypted_data = base64.b64decode(base64_ciphertext)

        # 分离密文和标签（标签长度16字节）
        ciphertext = encrypted_data[:-16]
        tag = encrypted_data[-16:]

        # 创建AES-GCM解密器
        aes_gcm = Cipher(
            algorithms.AES(aes_key),
            modes.GCM(iv, tag),
            backend=default_backend()
        ).decryptor()

        # 验证关联数据（与加密时一致）
        aes_gcm.authenticate_additional_data(b'')

        # 解密数据
        decrypted_bytes = aes_gcm.update(ciphertext) + aes_gcm.finalize()

        # 明文
        plaintext = decrypted_bytes.decode('utf-8')

        return json.loads(plaintext)

    @staticmethod
    def _encrypt_aes_key_with_rsa(aes_key, public_key_str):
        """使用RSA公钥加密AES密钥"""

        # 解码Base64格式的公钥
        public_key_bytes = base64.b64decode(public_key_str)

        # 加载公钥
        public_key = serialization.load_der_public_key(
            public_key_bytes,
            backend=default_backend()
        )

        base64_aes_key = base64.b64encode(aes_key).decode('utf-8')

        # 使用RSA加密
        encrypted_bytes = public_key.encrypt(
            base64_aes_key.encode('utf-8'),
            padding.PKCS1v15()
        )

        return base64.b64encode(encrypted_bytes).decode('utf-8')
