"""Sis modeli paketi. Bazi moduller botun ortak yardimcilarini (ltfj_analiz,
ltfj_ayarlar, ltfj_pist, ltfj_sis_olasilik) kullanir; bunlar bot/ altinda.
`python -m sis_modeli.xxx` repo kokunden calistirildiginda da bulunsunlar."""
import sys
from pathlib import Path

_BOT = str(Path(__file__).resolve().parent.parent / "bot")
if _BOT not in sys.path:
    sys.path.insert(0, _BOT)
