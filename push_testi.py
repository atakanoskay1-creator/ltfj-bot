#!/usr/bin/env python3
"""Web Push'u ELLE, anında test eder - METAR/TAF akışına hiç dokunmaz.

Neden var: push yalnızca SPECI/TAF/düzeltme/renk kötüleşmesi/yeni NOTAM
geldiğinde tetiklenir. Bunlar seyrek olduğu için "abone oldum, çalışıyor mu?"
sorusunun cevabı saatlerce beklemeyi gerektiriyordu. Bu script o döngüyü
kırar: Actions sekmesinden elle çalıştırılır, hem telefona GERÇEK bir
bildirim düşürür hem de sayaçları loga yazar.

ltfj_bot.py'ye DOKUNMAZ - state okumaz/yazmaz, METAR çekmez, Telegram'a
mesaj atmaz, Claude API'si kullanmaz. Tek yaptığı ltfj_push.gonder()
çağırmak.

Çıkış kodu 0 = en az bir aboneye gönderildi; 1 = gönderilemedi (sebep
loga yazılır). Böylece Actions adımı kırmızı/yeşil olarak da okunabilir.
"""

import sys

import ltfj_push
from ltfj_ayarlar import ayar

BASLIK = "🔔 LTFJ test bildirimi"
GOVDE = ("Bu bir testtir - gerçek bir hava durumu uyarısı değildir. "
         "Bunu gördüyseniz Web Push uçtan uca çalışıyor.")
ETIKET = "TEST"


def main() -> int:
    if not ayar("push", "aktif", varsayilan=True):
        print("Push kapalı (ayarlar.json::push.aktif = false).", file=sys.stderr)
        return 1

    if not ltfj_push.yapilandirilmis_mi():
        print("Push yapılandırılmamış - FIREBASE_SERVICE_ACCOUNT, "
              "FIREBASE_DATABASE_URL ve VAPID_PRIVATE_KEY secret'larının "
              "üçü de tanımlı olmalı.", file=sys.stderr)
        return 1

    try:
        sonuc = ltfj_push.gonder(
            BASLIK, GOVDE,
            ayar("push", "vapid_subject", varsayilan="mailto:ornek@ornek.com"),
            etiket=ETIKET)
    except ltfj_push.PushGonderimHatasi as e:
        print(f"Gönderim başarısız: {e}", file=sys.stderr)
        return 1

    print(f'Kayıtlı abone      : {sonuc["abone"]}')
    print(f'Gönderildi         : {sonuc["gonderildi"]}')
    print(f'Geçersiz (silindi) : {sonuc["silindi"]}')
    print(f'Hata               : {sonuc["hata"]}')

    if not sonuc["abone"]:
        print("\nKayıtlı abone YOK. Tarayıcıdaki abonelik tek başına yetmez - "
              "kaydın Firebase'e düşmesi gerekir. Firebase Console > Realtime "
              "Database > Rules sekmesinde firebase-rules.json'ın güncel hali "
              "yayınlanmış mı (push_abonelikler bloğu var mı) kontrol edin, "
              "sonra sayfayı yenileyip tekrar abone olun.", file=sys.stderr)
        return 1

    if not sonuc["gonderildi"]:
        print("\nAbone var ama hiçbirine gönderilemedi - yukarıdaki "
              "silindi/hata sayaçlarına bakın.", file=sys.stderr)
        return 1

    print("\nBaşarılı - abone olan cihazlarda bildirim görünmeli.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
