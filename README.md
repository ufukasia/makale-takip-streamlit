# Makale Konu Seçim & İlerleme Takip — Streamlit Uygulaması

Yüksek lisans yapay zekâ dersi için öğrencilerin makale konusu seçtiği ve 6 aşamalı ilerlemesini (konu seçildi → veri seti indirildi → rakip (baseline) çalıştı → kod stabil çalışıyor → rakip geçildi → makale yazıldı) takip ettiği Streamlit uygulaması.

## Özellikler

- `topics.json` içinde 14 bölüm, 58 konu ve bir bonus konu.
- Okul e-postası (`@ostimteknik.edu.tr`) ile kayıt, e-posta doğrulama kodu ve şifreyle giriş.
- Her konu yalnızca bir öğrenciye ait olabilir; konu değiştiren öğrencinin ilerlemesi sıfırlanır.
- Her aşama için durum seçimi: beklemede / tamamlandı / gerçekleştirilemiyor (sorun açıklamasıyla).
- Danışman paneli: aşama sayaçları, öğrenci tablosu, sorun bildirimlerine cevap, konu başına seçim grafiği, `.txt` durum raporu, JSON yedek indirme ve geri yükleme.
- Kalıcı kayıt için isteğe bağlı Turso (SQLite uyumlu bulut veritabanı) desteği; tanımlı değilse yerel `submissions.db` dosyası kullanılır.

## Kurulum ve çalıştırma

```bash
pip install -r requirements.txt
streamlit run app.py
```

Uygulama `http://localhost:8501` adresinde çalışır (`.streamlit/config.toml` içinde `headless = true` olduğundan tarayıcıyı kendiniz açın). Sınıftaki herkesin aynı kayıtları görmesi için uygulamayı tek bir bilgisayarda/sunucuda çalıştırıp o makinenin adresini paylaşın (ör. `http://<sunucu-ip>:8501`). Dışarıdan erişim için:

```bash
streamlit run app.py --server.address 0.0.0.0
```

Depoda bir `.devcontainer` yapılandırması da bulunur; GitHub Codespaces'ta açıldığında uygulama otomatik olarak başlatılır.

## Yapılandırma

Tüm gizli ayarlar `.streamlit/secrets.toml` dosyasında tutulur. Şablonu kopyalayıp kendi bilgilerinizle doldurun:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

`.streamlit/secrets.toml` `.gitignore` içindedir; gerçek parola ve token'ları depoya eklemeyin. Streamlit Cloud'da aynı içerik uygulama menüsündeki **Settings → Secrets** kutusuna yapıştırılır.

| Blok | Açıklama |
|---|---|
| `[smtp]` | Doğrulama kodlarını göndermek için SMTP sunucusu (`host`, `port`, `user`, `password`, `sender`). **Zorunlu.** |
| `[turso]` | Kalıcı bulut veritabanı (`url`, `auth_token`). Streamlit Cloud için gereklidir, yerelde isteğe bağlıdır. |

### E-posta doğrulaması ve hesaplar

Öğrenciler klasik site girişi kullanır:

- **Kayıt Ol:** Ad + `@ostimteknik.edu.tr` e-postası → e-postaya gelen 6 haneli kod → şifre belirleme. Hesap oluşur.
- **Giriş Yap:** Sonraki girişlerde e-posta + şifre yeterlidir (kod gerekmez).
- **Şifremi Unuttum:** E-postaya yeni kod gelir; kod girilip yeni şifre belirlenir.

Şifreler veritabanında tuzlanmış PBKDF2 özeti olarak tutulur (düz metin saklanmaz). Kod 10 dakika geçerlidir, 5 hatalı denemede iptal olur, yeni kod için 60 sn bekleme vardır.

SMTP ayarlanmadan kayıt/sıfırlama kodu gönderilemez; uygulama bunu açık bir hata mesajıyla bildirir. Gmail kullanılacaksa normal hesap şifresi değil, bir "Uygulama Şifresi" gerekir; ayrıntılar `.streamlit/secrets.toml.example` dosyasındadır.

### Danışman paneli şifresi

Danışman paneline yan menüden **Danışman Paneli** seçilip panel şifresiyle girilir. Panel şifresi `app.py` içindeki `PANEL_SIFRESI` sabitinde tanımlıdır; uygulamayı kullanıma açmadan önce bu değeri size özel bir şifreyle değiştirin ve öğrencilerle paylaşmayın.

## Kalıcı veritabanı — Turso (Streamlit Cloud için)

**Sorun:** Streamlit Cloud'un diski geçicidir. Uygulama bir süre kullanılmayınca makine uykuya dalar; uyandığında depo sıfırdan kurulur ve `submissions.db` ilk hâline döner — öğrencilerin konu seçimleri ve ilerlemeleri kaybolur.

**Çözüm:** Kayıtları Turso'da (SQLite uyumlu bulut veritabanı) tutmak. Kod tarafında değişiklik gerekmez; `secrets.toml` içinde `[turso]` bloğu varsa uygulama otomatik olarak buluta yazar, yoksa yerel dosyaya düşer.

### Adımlar

1. <https://turso.tech> adresinde bir hesap açın.
2. **Create Database** → bir isim verin (ör. `makale-takip`).
3. Veritabanına tıklayın → **Connect / Connection URL** → `libsql://...` adresini kopyalayın.
4. Aynı ekrandan **Create Token** ile bir erişim token'ı oluşturun.
5. `.streamlit/secrets.toml` dosyasına ekleyin:

   ```toml
   [turso]
   url = "libsql://<veritabani-adiniz>.turso.io"
   auth_token = "<token>"
   ```

6. Tabloları kurun ve **yereldeki mevcut kayıtları buluta taşıyın**:

   ```bash
   python turso_kur.py
   ```

   Yalnızca bağlantıyı ve kayıt sayılarını görmek için: `python turso_kur.py --kontrol`

7. **Streamlit Cloud tarafı:** uygulama sayfasında **⋮ → Settings → Secrets** kutusuna aynı `[turso]` bloğunu (ve `[smtp]` bloğunu) yapıştırıp kaydedin. Uygulama yeniden başlar.

8. Doğrulama: Danışman Paneli → en altta **Veri saklama** kutusunda **"✅ Kalıcı mod (Turso)"** yazmalıdır. "⚠ Geçici mod" yazıyorsa secrets okunmamıştır.

Turso tanımlıyken veritabanına ulaşılamazsa uygulama kayıt kaybını önlemek için geçici yerel dosyaya yazmaz, bir hata mesajı gösterir.

### Yedekleme

Danışman Paneli → **Veri saklama** bölümünde:

- **💾 Yedek indir (.json)** — tüm öğrenci kayıtları, adım durumları ve hesaplar.
- **♻ Yedekten geri yükle** — indirilen dosyayı geri yükler (aynı anahtardaki kayıtların üzerine yazar). Yereldeki verileri buluta taşımanın ikinci yolu budur.

Yedek dosyaları öğrenci adı, e-posta adresi ve şifre özetleri içerir; herkese açık yerlerde paylaşmayın.

## Kullanım

**Öğrenci:** İlk seferde "Kayıt Ol" sekmesinden ad soyad + okul e-postası ile doğrulama kodu alıp şifresini belirler → sonraki girişlerde "Giriş Yap" ile e-posta + şifre yeterlidir → konuyu açıp "Bu konuyu seç" der → seçtiği konunun içinde her adımı radyo butonuyla işaretler: beklemede / tamamlandı / gerçekleştirilemiyor (sorununu yazar, danışman panelden cevaplar).

**Danışman:** Yan menüden "Danışman Paneli" → panel şifresi. Panelde aşama sayaçları, öğrenci tablosu, sorun bildirimleri, konu başına seçim grafiği, `.txt` durum raporu indirme ve veri saklama/yedekleme bölümü bulunur.

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `app.py` | Tüm uygulama (öğrenci görünümü + danışman paneli) |
| `turso_db.py` | Turso bulut veritabanı için küçük HTTP istemcisi (ek paket gerektirmez) |
| `turso_kur.py` | Turso tablolarını kurar ve yerel kayıtları buluta taşır |
| `topics.json` | 14 bölüm / 58 konu + bonus havuzu |
| `requirements.txt` | Bağımlılıklar: `streamlit`, `requests` |
| `.streamlit/config.toml` | Tema ve sunucu ayarları |
| `.streamlit/secrets.toml.example` | SMTP ve Turso ayarları için şablon |
| `submissions.db` | Yerel veritabanı; çalışma sırasında oluşur, `[turso]` tanımlı değilse kullanılır (`.gitignore` içindedir) |

## Notlar

- `[turso]` tanımlıysa veriler bulutta, değilse `submissions.db` dosyasında saklanır. Hangisinin geçerli olduğunu Danışman Paneli → **Veri saklama** kutusundan görebilirsiniz.
- Yedek almak için panelden **💾 Yedek indir (.json)** kullanın (veya yerelde `submissions.db` dosyasını kopyalayın).
- Sıfırlamak için: yerelde `submissions.db` dosyasını silin; Turso'da ise Turso panelinden veritabanını silip yeniden oluşturun.

## İletişim

Dr. Öğr. Üyesi Ufuk Asil, Ostim Teknik Üniversitesi. Sorular ve öneriler için GitHub üzerinden issue açabilirsiniz.
