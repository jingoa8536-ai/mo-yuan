"""Get base64 of the image and save to a file."""

import logging
logger = logging.getLogger(__name__)

import base64
img_path = r'C:\Users\user\AppData\Local\hermes\profiles\laap-avatar-v4\image_cache\img_1cdd68034bd5.jpg'
with open(img_path, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
logger.info(f"Length: {len(b64)}")
with open('D:/LAAP/aris_brain/_img_b64.txt', 'w') as f:
    f.write(b64)
logger.info("Saved to _img_b64.txt")