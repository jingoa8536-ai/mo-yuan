import shutil, os
path = "C:/Users/user/.cache/huggingface/modules/transformers_modules/MOSS_hyphen_TTS_hyphen_Nano_hyphen_100M"
if os.path.exists(path):
    shutil.rmtree(path)
    print("缓存已删除")
else:
    print("缓存已不存在")
