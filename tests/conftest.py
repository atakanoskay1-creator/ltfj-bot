"""Repo kokunu ve bot/ dizinini sys.path'e ekler ki 'import ltfj_analiz' ve
'import sis_modeli...' gibi satirlar pytest'in nereden calistirildigina
bakmaksizin calissin. Bot modulleri bot/, elle calistirilan araclar araclar/
altinda."""
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
for yol in (KOK / "araclar", KOK / "bot", KOK):
    sys.path.insert(0, str(yol))
