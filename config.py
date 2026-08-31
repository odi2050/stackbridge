import os
from dotenv import load_dotenv
load_dotenv()
MAX_UPLOAD_MB=int(os.getenv("MAX_UPLOAD_MB","500"))
TEMP_TTL_MINUTES=int(os.getenv("TEMP_TTL_MINUTES","120"))
VERIFY_TLS=os.getenv("VERIFY_TLS","true").lower()=="true"
OCR_LANG=os.getenv("OCR_LANG","fra+eng")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","admin")
ADMIN_PASSWORD_HASH=os.getenv("ADMIN_PASSWORD_HASH","")
SECRET_KEY=os.getenv("SECRET_KEY","stackbridge-change-me")
