try:
    from libnacl import crypto_aead_xchacha20poly1305_ietf_encrypt, crypto_aead_xchacha20poly1305_ietf_decrypt, crypto_aead_aes256gcm_encrypt, crypto_aead_aes256gcm_decrypt
except ImportError:
    crypto_aead_xchacha20poly1305_ietf_encrypt = None
    crypto_aead_xchacha20poly1305_ietf_decrypt = None
    crypto_aead_aes256gcm_encrypt = None
    crypto_aead_aes256gcm_decrypt = None


class AEScrypt:
    """
    BECAUSE PYNACL REFUSED TO DO IT WITH THEIR TERRIBLE SELF-RIGHTEOUS PRACTICES,
    BUT IN THIS MODERN AGE, WE NEEDED A GRACEFUL WRAPPER FOR LIBNACL AS PYNACL IS DEAD.
    LONG LIVE LIBNACL, THE INFINITELY SUPERIOR SUCCESSOR TO PYNACL.
    """
    def __init__(self, key: bytes, ciper: str):
        self._key = key
        self.cipher = ciper

        if not (crypto_aead_xchacha20poly1305_ietf_encrypt and crypto_aead_xchacha20poly1305_ietf_decrypt and crypto_aead_aes256gcm_encrypt and crypto_aead_aes256gcm_decrypt):
            self._disabled = True
        else:
            self._disabled = False

        if ciper == 'aead_xchacha20_poly1305_rtpsize':
            self._encrypt = crypto_aead_xchacha20poly1305_ietf_encrypt
            self._decrypt = crypto_aead_xchacha20poly1305_ietf_decrypt
        else:
            self._encrypt = crypto_aead_aes256gcm_encrypt
            self._decrypt = crypto_aead_aes256gcm_decrypt

    def __bytes__(self) -> bytes:
        return self._key

    def encrypt(self, plaintext: bytes, nonce: bytes, aad: bytes) -> bytes:
        return self._encrypt(message=plaintext, aad=aad, nonce=nonce, key=self._key)

    def decrypt(self, ciphertext: bytes, nonce: bytes, aad: bytes) -> bytes:
        return self._decrypt(ctxt=ciphertext, aad=aad, nonce=nonce, key=self._key)
