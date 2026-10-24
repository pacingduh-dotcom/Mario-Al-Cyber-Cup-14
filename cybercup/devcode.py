import hashlib
import hmac

CODE_SHA256 = "f78b0decbf47d4259a2f0f8180f1bc1f5e0c69a855390747e7682eb5343b68dd"
CODE_LEN = 10
IDLE_RESET = 3.0


def check_code(entered):
    return hmac.compare_digest(hashlib.sha256(entered.encode("utf-8", "ignore")).hexdigest(), CODE_SHA256)


class CodeDetector:

    def __init__(self):
        self.buf, self.last = "", None

    def reset(self):
        self.buf, self.last = "", None

    def feed(self, ch, now):
        if not isinstance(ch, str) or len(ch) != 1 or not ch.isalnum():
            return False
        if self.last is not None and now - self.last > IDLE_RESET:
            self.buf = ""
        self.last = now
        self.buf = (self.buf + ch.upper())[-CODE_LEN:]
        if len(self.buf) == CODE_LEN and check_code(self.buf):
            self.buf = ""
            return True
        return False
