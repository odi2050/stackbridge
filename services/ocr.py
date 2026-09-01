import io,shutil,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageEnhance,ImageFilter,ImageOps
from .runtime import detail


def _quality(text):
 text=(text or "").strip()
 if not text:return 0
 printable=sum(c.isalnum() or c.isspace() or c in ".,;:!?()[]{}'\"-_/àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ" for c in text)
 words=sum(1 for w in text.split() if len(w)>=2)
 return printable/max(1,len(text))*.65+min(words/40,1)*.35


def _preprocess(raw):
 """Conservative preprocessing: grayscale, autocontrast and light sharpening."""
 with Image.open(io.BytesIO(raw)) as source:
  image=ImageOps.exif_transpose(source).convert("L")
  image=ImageOps.autocontrast(image,cutoff=1)
  image=ImageEnhance.Contrast(image).enhance(1.15)
  image=image.filter(ImageFilter.SHARPEN)
  out=io.BytesIO();image.save(out,"PNG",optimize=True);return out.getvalue()


def _run_tesseract(path,lang,psm):
 cmd=["tesseract",str(path),"stdout","-l",lang,"--oem","1","--psm",str(psm),"-c","preserve_interword_spaces=1"]
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
 if result.returncode:return "",(result.stderr or f"Tesseract return code {result.returncode}").strip()
 return result.stdout or "",None


def image_to_text(raw,lang):
 """OCR v2. Tries automatic layout first, then a block-text pass if useful."""
 detail("OCR v2 start bytes=%s lang=%s",len(raw),lang)
 if not shutil.which("tesseract"):
  detail("OCR unavailable: tesseract not found");return "","Tesseract indisponible"
 try:processed=_preprocess(raw)
 except Exception as exc:
  detail("OCR preprocessing failed error=%s",exc);processed=raw
 best_text="";best_score=0;errors=[]
 with tempfile.TemporaryDirectory() as directory:
  path=Path(directory)/"page.png";path.write_bytes(processed)
  # PSM 3 handles normal pages/columns. PSM 6 is a useful fallback for dense scans.
  for psm in (3,6):
   try:text,error=_run_tesseract(path,lang,psm)
   except subprocess.TimeoutExpired:
    text="";error=f"Tesseract timeout (PSM {psm})"
   except Exception as exc:
    text="";error=str(exc)
   score=_quality(text)
   detail("OCR v2 pass psm=%s chars=%s score=%.3f",psm,len(text),score)
   if error:errors.append(error)
   if score>best_score:best_text,best_score=text,score
   if best_score>=.88 and len(best_text.strip())>=80:break
 if best_text.strip():
  detail("OCR v2 complete chars=%s score=%.3f",len(best_text),best_score);return best_text,None
 error="; ".join(dict.fromkeys(errors)) if errors else "OCR sans texte exploitable"
 detail("OCR v2 failed error=%s",error[:500]);return "",error
