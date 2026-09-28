"""Model A'nin hedefi olan olay gozlemi etiketi: gorus < 1000 m VEYA
alani kaplayan FG.

Bu testler dokumantasyonla koddaki tanimin bir kez daha kopmasina karsi
KOD tarafini kilitliyor: belgeler uzun sure "gorus < 1000 m VE alani
kaplayan FG" diyordu; kod ise VEYA uyguluyor ve 1.702 egitim pozitifi bu
VEYA tanimindan geliyor. Iki kol ayri ayri sabitleniyor:
  - gorus kolu: FG yokken bile gorus < 1000 m olay gozlemidir (kar dahil),
  - FG kolu: gorus >= 1000 m iken alani kaplayan FG olay gozlemidir.
Teknik adi "LTFJ dusuk gorus/FG olayi"; koddaki `sis` adi tarihseldir.
"""
from datetime import datetime

import pytest

from sis_modeli.ozellik import ozellik_cikar

ZAMAN = datetime(2020, 1, 15, 2, 20)


def _etiket(gorus_ve_hava: str) -> int:
    metin = f"LTFJ 150220Z 03004KT {gorus_ve_hava} NSC 05/04 Q1024"
    ozellik = ozellik_cikar(metin, ZAMAN)
    assert ozellik is not None, metin
    return ozellik["sis"]


@pytest.mark.parametrize("gorus_ve_hava,beklenen", [
    ("0800 BR", 1),      # gorus kolu, FG yok
    ("5000 FG", 1),      # FG kolu, gorus >= 1000
    ("5000 BR", 0),      # ikisi de yok
    ("0800 -SN", 1),     # kar kaynakli dusuk gorus DA hedefe girer
    ("0800 BCFG", 1),    # parcali sis, gorus kolu uzerinden
    ("5000 BCFG", 0),    # parcali sis tek basina FG kolunu ACMAZ
])
def test_olay_gozlemi_GORUS_VEYA_alani_kaplayan_FG(gorus_ve_hava, beklenen):
    assert _etiket(gorus_ve_hava) == beklenen
