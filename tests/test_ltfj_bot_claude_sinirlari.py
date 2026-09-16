"""P2: Claude 'aciklama katmani' olmali, operasyonel karar verici degil.

SISTEM_ISTEMI'nin bu siniri metin olarak tasidigini dogrular - Claude'un
kendisinin buna uymasini test edemeyiz (LLM cagrisi gerektirir, deterministik
degil), ama en azindan promptun bu talimati ICERDIGINI sabitleriz."""
import ltfj_bot as b


def test_sistem_istemi_operasyonel_karar_yasagini_icerir():
    metin = b.SISTEM_ISTEMI
    assert "KARAR VERİCİ DEĞİLSİN" in metin
    assert "pist ataması yapma" in metin
    assert "gecikme" in metin


def test_metar_sablonu_kesin_gecikme_tahmini_istemiyor():
    assert "kesin gecikme" in b.METAR_SABLONU
