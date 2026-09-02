import os
import re
from pathlib import Path

APP_NAME="StackBridge"
APP_DESCRIPTION="Document Import Studio for BookStack"

def get_version():
 configured=os.getenv("STACKBRIDGE_VERSION","").strip()
 if configured:
  version=configured
 else:
  try:
   version=(Path(__file__).resolve().parent/"VERSION").read_text(encoding="utf-8").strip()
  except OSError:
   version="latest"

 # "latest" est la valeur par defaut pour les installations Docker.
 if version.lower()=="latest":
  return "latest"

 # Les versions SemVer restent supportees pour les releases versionnees.
 if re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",version):
  return version

 # Une valeur non reconnue ne doit pas empecher StackBridge de demarrer.
 return "latest"

APP_VERSION=get_version()
