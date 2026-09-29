# Makale Konu Seçim & İlerleme Takip — Streamlit Uygulaması

Yüksek lisans yapay zeka dersi için öğrenci konu seçimi ve 6 aşamalı ilerleme takibi (son aşama: makale yazıldı).

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

## Kalıcı veritabanı — Turso (Streamlit Cloud için zorunlu)

**Sorun:** Streamlit Cloud'un diski geçicidir. Uygulama bir süre kullanılmayınca
makine uykuya dalar; uyandığında repo sıfırdan kurulur ve `submissions.db` ilk
haline döner — öğrencilerin konu seçimleri ve ilerlemeleri kaybolur.

**Çözüm:** Kayıtları Turso'da (ücretsiz, SQLite uyumlu bulut veritabanı) tutmak.
Kod tarafında değişiklik gerekmez; `secrets.toml` içinde `[turso]` varsa uygulama
otomatik olarak buluta yazar, yoksa yerel dosyaya düşer.

### Adımlar (5 dakika, kredi kartı istemez)

1. <https://turso.tech> → **GitHub ile giriş yap**.
2. **Create Database** → isim ver (ör. `makale-takip`), bölge: Frankfurt (`fra`).
3. Veritabanına tıkla → **Connect / Connection URL** → `libsql://...` adresini kopyala.
4. Aynı ekrandan **Create Token** → çıkan uzun metni kopyala.
5. `.streamlit/secrets.toml` dosyana şunu ekle:

   ```toml
   [turso]
   url = "libsql://makale-takip-kullaniciadin.turso.io"
   auth_token = "eyJhbGciOiJF..."
   ```

6. Tabloları kur ve **yereldeki mevcut kayıtları buluta taşı**:

   ```bash
   python turso_kur.py
   ```

   Sadece bağlantıyı denemek için: `python turso_kur.py --kontrol`

7. **Streamlit Cloud tarafı:** uygulamanın sayfasında sağ üst **⋮ → Settings →
   Secrets** kutusuna aynı `[turso]` bloğunu (ve `[smtp]` bloğunu) yapıştır → Save.
   Uygulama yeniden başlar.

8. Doğrula: Danışman Paneli → en altta **Veri saklama** kutusu
   **"✅ Kalıcı mod (Turso)"** yazmalı. "⚠ Geçici mod" yazıyorsa secrets okunmamıştır.

Artık makine uyuyup uyansa, uygulamayı yeniden deploy etsen bile kayıtlar yerinde kalır.

### Yedekleme

Danışman Paneli → **Veri saklama** bölümünde:

- **💾 Yedek indir (.json)** — tüm öğrenci kayıtları, adım durumları ve hesaplar.
- **♻ Yedekten geri yükle** — indirilen dosyayı geri yükler (aynı anahtardaki
  kayıtların üzerine yazar). Yereldeki verileri buluta taşımanın ikinci yolu budur.

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
| `turso_db.py` | Turso bulut veritabanı için küçük HTTP istemcisi (ek paket gerektirmez) |
| `turso_kur.py` | Turso tablolarını kurar ve yerel kayıtları buluta taşır |
| `topics.json` | 14 bölüm / 58 konu + bonus havuzu (dashboard ile aynı veri) |
| `requirements.txt` | Bağımlılıklar: streamlit, requests |
| `submissions.db` | Yerel yedek depo — `[turso]` tanımlı değilse burası kullanılır |

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

- `[turso]` tanımlıysa veriler bulutta, değilse `submissions.db` dosyasında saklanır.
  Hangisinin geçerli olduğunu Danışman Paneli → **Veri saklama** kutusundan görebilirsiniz.
- Yedek almak için panelden **💾 Yedek indir (.json)** (veya yerelde `submissions.db`
  dosyasını kopyalayın).
- Sıfırlamak için: yerelde `submissions.db` dosyasını silin; Turso'da ise
  <https://turso.tech> panelinden veritabanını silip yeniden oluşturun.
- Turso'nun ücretsiz planı bu ders için fazlasıyla yeterlidir (milyarlarca satır
  okuma / 9 GB depolama).
