from warnings import warn as warnings_warn

try:
    from nacl.utils import EncryptedMessage
except ImportError:
    pass

try:
    from libnacl import crypto_aead_xchacha20poly1305_ietf_encrypt, crypto_aead_xchacha20poly1305_ietf_decrypt, crypto_aead_aes256gcm_encrypt, crypto_aead_aes256gcm_decrypt
except ImportError:
    warnings_warn('libnacl is not installed, AES support is disabled')


class AEScrypt:
    """
    BECAUSE PYNACL REFUSES TO DO IT WITH THEIR TERRIBLE SELF-RIGHTEOUS PRACTICES
    """
    def __init__(self, key: bytes, ciper: str):
        self._key = key
        self.cipher = ciper
        return

    def __bytes__(self) -> bytes:
        return self._key

    def encrypt(self, plaintext: bytes, nonce: bytes, aad: bytes) -> bytes:
        if self.cipher == 'aead_xchacha20_poly1305_rtpsize':
            payload = crypto_aead_xchacha20poly1305_ietf_encrypt(message=plaintext, aad=aad, nonce=nonce, key=self._key)
        else:
            payload = crypto_aead_aes256gcm_encrypt(message=plaintext, aad=aad, nonce=nonce, key=self._key)
        return EncryptedMessage._from_parts(nonce, payload, nonce + payload)

    def decrypt(self, ciphertext: bytes, nonce: bytes, aad: bytes) -> bytes:
        if self.cipher == 'aead_xchacha20_poly1305_rtpsize':
            return crypto_aead_xchacha20poly1305_ietf_decrypt(ctxt=ciphertext, aad=aad, nonce=nonce, key=self._key)
        else:
            return crypto_aead_aes256gcm_decrypt(ctxt=ciphertext, aad=aad, nonce=nonce, key=self._key)
