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

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `app.py` | Tüm uygulama (öğrenci görünümü + danışman paneli) |
| `topics.json` | 14 bölüm / 58 konu + bonus havuzu (dashboard ile aynı veri) |
| `requirements.txt` | Tek bağımlılık: streamlit |
| `submissions.db` | Çalışınca otomatik oluşur — öğrenci kayıtları (SQLite) |

## Kullanım

**Öğrenci:** Sol menüden ad soyad + öğrenci numarasını girer → konuyu açıp
"Bu konuyu seç" der → seçtiği konunun içinde ilerleme kutuları belirir:
veri seti indirildi / rakip çalıştı / kod stabil / rakip geçildi.
Konu değiştirirse ilerleme sıfırlanır.

**Danışman:** Sol menüden "Danışman Paneli" → şifre (varsayılan: `orkestra2026`,
değiştirmek için `app.py` içindeki `PANEL_SIFRESI` satırını düzenleyin).
Panelde: aşama sayaçları, öğrenci tablosu, konu başına seçim grafiği ve
.txt durum raporu indirme.

## Notlar

- Veriler `submissions.db` dosyasında saklanır; yedeklemek için bu dosyayı kopyalayın.
- Sıfırlamak için uygulamayı durdurup `submissions.db` dosyasını silin.
