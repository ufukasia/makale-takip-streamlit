# Makale Konu Seçim & İlerleme Takip — Streamlit Uygulaması

Yüksek lisans yapay zeka dersi için öğrenci konu seçimi ve 5 aşamalı ilerleme takibi.

## Kurulum ve çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır. Sınıftaki herkesin aynı kayıtları görmesi için
uygulamayı tek bir bilgisayarda/sunucuda çalıştırıp o makinenin adresini paylaşın
(ör. `http://<sunucu-ip>:8501`). Dışarıdan erişim için:

```bash
streamlit run app.py --server.address 0.0.0.0
```

## E-posta doğrulaması ve hesaplar (zorunlu kurulum)

Öğrenciler klasik site girişi kullanır:

- **Kayıt Ol:** Ad + `@ostimteknik.edu.tr` e-postası → mailine gelen 6 haneli kod →
  şifre belirle. Hesap oluşur.
- **Giriş Yap:** Sonraki girişlerde sadece e-posta + şifre yeterlidir (kod gerekmez).
- **Şifremi Unuttum:** Mailine yeni kod gelir, kodu girip yeni şifre belirler.

Şifreler veritabanında tuzlanmış PBKDF2 özeti olarak tutulur (düz metin asla saklanmaz).
Kod 10 dakika geçerlidir, 5 hatalı denemede iptal olur, yeni kod için 60 sn bekleme vardır.

Kodların gönderilebilmesi için SMTP ayarı gerekir:

1. `.streamlit/secrets.toml.example` dosyasını `.streamlit/secrets.toml` olarak kopyalayın.
2. İçine kendi SMTP bilgilerinizi yazın (Gmail için "Uygulama Şifresi" gerekir —
   dosyanın içindeki yönergeleri izleyin).

SMTP ayarlanmadan kayıt/sıfırlama kodu gönderilemez; uygulama bunu açık bir hata mesajıyla bildirir.

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `app.py` | Tüm uygulama (öğrenci görünümü + danışman paneli) |
| `topics.json` | 14 bölüm / 58 konu + bonus havuzu (dashboard ile aynı veri) |
| `requirements.txt` | Tek bağımlılık: streamlit |
| `submissions.db` | Çalışınca otomatik oluşur — öğrenci kayıtları (SQLite) |

## Kullanım

**Öğrenci:** İlk seferde "Kayıt Ol" sekmesinden ad soyad + okul e-postası
(`@ostimteknik.edu.tr`) ile doğrulama kodu alıp şifresini belirler → sonraki
girişlerde "Giriş Yap" ile e-posta + şifre yeterlidir → konuyu açıp "Bu konuyu seç"
der → seçtiği konunun içinde her adımı radyo butonuyla işaretler:
beklemede / tamamlandı / gerçekleştirilemiyor (sorununu yazar, danışman panelden
cevaplar). Bir konu yalnızca bir öğrenciye aittir. Konu değiştirirse ilerleme sıfırlanır.

**Danışman:** Sol menüden "Danışman Paneli" → şifre (varsayılan: `orkestra2026`,
değiştirmek için `app.py` içindeki `PANEL_SIFRESI` satırını düzenleyin).
Panelde: aşama sayaçları, öğrenci tablosu, konu başına seçim grafiği ve
.txt durum raporu indirme.

## Notlar

- Veriler `submissions.db` dosyasında saklanır; yedeklemek için bu dosyayı kopyalayın.
- Sıfırlamak için uygulamayı durdurup `submissions.db` dosyasını silin.
