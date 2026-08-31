import shutil,subprocess,tempfile
from pathlib import Path
from .runtime import detail
def image_to_text(raw,lang):
 detail("OCR start bytes=%s lang=%s",len(raw),lang)
 if not shutil.which("tesseract"):detail("OCR unavailable: tesseract not found");return "","Tesseract indisponible"
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/"p.png";o=Path(d)/"o";p.write_bytes(raw)
  r=subprocess.run(["tesseract",str(p),str(o),"-l",lang,"--psm","6"],capture_output=True,text=True)
  if r.returncode:detail("OCR failure returncode=%s stderr=%s",r.returncode,r.stderr[:500]);return "",r.stderr
  text=o.with_suffix(".txt").read_text(encoding="utf8",errors="replace");detail("OCR complete chars=%s",len(text));return text,None
