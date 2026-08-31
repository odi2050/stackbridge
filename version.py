import os
import re
from pathlib import Path

APP_NAME="StackBridge"
APP_DESCRIPTION="Document Import Studio for BookStack"
def get_version():
 configured=os.getenv("STACKBRIDGE_VERSION","").strip()
 if configured:version=configured
 else:
  try:version=(Path(__file__).resolve().parent/"VERSION").read_text(encoding="utf-8").strip()
  except OSError:version="0.0.0-dev"
 if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",version):raise RuntimeError(f"Version SemVer invalide : {version}")
 return version
APP_VERSION=get_version()
