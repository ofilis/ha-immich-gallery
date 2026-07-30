# Immich Gallery araştırma ve tasarım notu

Tarih: 30 Temmuz 2026

Bu çalışma, `outadoc/immich-home-assistant` deposunu yalnızca davranış,
sorunlar ve uyumluluk gereksinimleri açısından inceleyerek hazırlandı.
Üçüncü taraf depodan kaynak kod, metin veya görsel kopyalanmadı.

## İncelenen eski entegrasyon

[outadoc/immich-home-assistant](https://github.com/outadoc/immich-home-assistant)
şu temel davranışları sağlıyor:

- favorilerden rastgele bir `image` entity'si;
- seçilen her albüm için bir `image` entity'si;
- kullanıcı arayüzünden URL, API anahtarı ve albüm seçimi;
- sabit, yaklaşık beş dakikalık yenileme.

Depo ağacında bir lisans dosyası görünmediği için, açık bir kopyalama izni
varsayılmadı. Yeni entegrasyonun alan adı, istemcisi, veri modeli, config flow'u,
entity yapısı, çevirileri, belgeleri ve testleri sıfırdan yazıldı.

## Eski uygulamada belirlenen başlıca riskler

Kod ve açık sorun kayıtlarının 30 Temmuz 2026 tarihli görünümüne göre:

- API istekleri için paylaşılan Home Assistant oturumu yerine tekrar tekrar
  yeni HTTP oturumu oluşturuluyor.
- Favori filtresi form biçimli metin olarak gönderiliyor. Immich 3.x gerçek
  JSON boolean istiyor; bu kırılma
  [#30](https://github.com/outadoc/immich-home-assistant/issues/30) içinde
  doğrulanmış.
- Eski options-flow deseni `self.config_entry` değerini elle atıyor. Bunun
  Home Assistant 2025.12 ile kırıldığı
  [#26](https://github.com/outadoc/immich-home-assistant/issues/26) içinde
  bildirilmiş.
- Görsel yenileme işareti güncel `ImageEntity` beklentisine uymuyor; fotoğrafın
  yalnızca yeniden başlatmadan sonra değişmesi
  [#21](https://github.com/outadoc/immich-home-assistant/issues/21) içinde
  bildirilmiş.
- Orijinal dosyalar indiriliyor; yalnızca JPEG ve PNG kabul ediliyor. HEIC,
  sertifika ve boş sonuç sorunları
  [#24](https://github.com/outadoc/immich-home-assistant/issues/24) içinde
  birlikte görülüyor.
- Başarısız görsel indirmede sınırı olmayan tekrar döngüsü oluşabiliyor.
- Hata günlüklerine API yanıt gövdesi yazılabiliyor; bu, kişisel medya
  meta verilerini günlüklerde açığa çıkarabilir.
- Tam albüm/asset listeleri bellekte tutuluyor; yanıt boyutu ve görsel boyutu
  için açık sınırlar yok.
- Reauthentication, reconfigure, güvenli diagnostics ve otomatik test kapsamı
  bulunmuyor.
- Alan adı `immich`, Home Assistant 2025.6 ile gelen yerleşik
  [Immich entegrasyonu](https://www.home-assistant.io/integrations/immich/)
  ile çakışıyor.

Bu maddeler eski kodun aynısını yamamak yerine bağımsız bir tasarım yapılmasının
temel nedenleridir.

## Güncel resmi API sözleşmesi

Immich, üçüncü taraf uygulamalara ayrıntılı yetkili API anahtarı kullanmasını ve
anahtarı `x-api-key` başlığında göndermesini öneriyor:
[Authentication](https://api.immich.app/authentication).

MVP yalnızca şu kararlı uç noktaları kullanıyor:

| Amaç | Uç nokta | Yetki |
| --- | --- | --- |
| Sunucu sürümü | `GET /server/version` | Public |
| Mevcut kullanıcı | `GET /users/me` | `user.read` |
| Albüm listesi | `GET /albums` | `album.read` |
| Rastgele görsel arama | `POST /search/random` | `asset.read` |
| Önizleme görseli | `GET /assets/{id}/thumbnail?size=preview` | `asset.view` |

Kaynaklar:
[server version](https://api.immich.app/endpoints/server/getServerVersion),
[current user](https://api.immich.app/endpoints/users/getMyUser),
[albums](https://api.immich.app/endpoints/albums/getAllAlbums),
[random search](https://api.immich.app/endpoints/search/searchRandom),
[thumbnail](https://api.immich.app/endpoints/assets/viewAsset).

`asset.download`, yazma, silme veya yönetici yetkisi kullanılmıyor. Özellikle
`/assets/random` eski ve deprecated olduğundan kullanılmadı.

## Yeni mimari

Yeni entegrasyonun alan adı `immich_gallery`. Böylece yerleşik `immich`
entegrasyonunu gölgelemeden aynı Home Assistant kurulumunda çalışabilir.

Her config entry için:

1. Home Assistant'ın paylaşılan `aiohttp` oturumu kullanılır.
2. `DataUpdateCoordinator`, seçilen her kaynak için en fazla üç eşzamanlı
   önizleme isteği çalıştırır.
3. Tüm kütüphane, favoriler ve seçilen her albüm ayrı bir kaynak/entity olur.
4. Her kaynak için sunucu tarafında rastgele seçilmiş, boyutu sınırlı bir aday
   grubu istenir; yakın zamanda gösterilen görseller elenir.
5. Önizleme byte'ları coordinator içinde tutulur.
6. `ImageEntity.async_image()` ağ isteği yapmadan yalnızca önbelleği döndürür.
7. `image_last_updated`, coordinator yenilemesinde değiştirilir.
8. Bir kaynak hata verirse diğer kaynaklar güncellenmeye devam eder; son iyi
   görsel bellekte korunur.

Bu yaklaşım Home Assistant'ın
[Image entity](https://developers.home-assistant.io/docs/core/entity/image/)
ve
[data fetching](https://developers.home-assistant.io/docs/integration_fetching_data/)
önerileriyle uyumludur.

## Host ve sonradan yapılandırma

Kurulum ve **Configure** akışları aynı URL doğrulama kurallarını kullanır.
Kök URL veya `/api` ile biten URL kabul edilir; yol bir kez normalize edilir.
Desteklenen bağlantı biçimleri:

- geçerli sertifikalı genel veya özel HTTPS;
- port içeren yerel HTTP adresi;
- Tailscale IPv4/IPv6 adresi;
- Tailscale MagicDNS adı;
- alt yola yayınlanan reverse proxy adresi.

Kullanıcı bilgisi, query string veya fragment içeren URL'ler reddedilir.
Sertifika doğrulaması varsayılan olarak açıktır. Kapalı duruma yalnızca
güvenilen özel/self-signed sertifika için açık kullanıcı tercihiyle geçilir.

Home Assistant'ta
**Ayarlar → Cihazlar ve hizmetler → Immich Gallery → Configure** ekranı şu
değerleri yeniden düzenler:

- host;
- isteğe bağlı yeni API anahtarı;
- TLS doğrulaması;
- tüm kütüphane, favoriler ve albümler;
- son gösterilen görsel hafızasının boyutu;
- 1–60 dakika yenileme aralığı.

Host veya anahtar değişikliği kaydedilmeden önce gerçek API çağrılarıyla
doğrulanır. Yeni hedefin kullanıcı UUID'si mevcut config entry ile aynı olmak
zorundadır; böylece var olan entry yanlışlıkla başka bir Immich hesabına
taşınmaz. Host değişikliği entegrasyonun yeniden yüklenmesini tetikler.

URL testleri HTTPS, yerel HTTP, Tailscale IP, MagicDNS ve IPv6 örneklerini
kapsar. Ayrıca gerçek bir yerel `aiohttp` sunucusuna karşı uçtan uca HTTP
isteğiyle başlık, endpoint ve preview davranışı denenir. Gerçek bir Tailscale
peer'ı veya kullanıcının özel sertifikası bu geliştirme ortamında
bulunmadığından, o son bağlantı doğrulaması kurulum ortamında yapılmalıdır.

## Büyük kütüphanelerde rastgelelik

Tam kütüphane veya albüm listesi Home Assistant'a indirilmez. Her yenilemede:

1. Immich'in kararlı `POST /search/random` endpoint'i kaynak filtresiyle
   çağrılır.
2. Aday sayısı `tekrar penceresi + 10` olarak hesaplanır ve 10–100 aralığında
   sınırlandırılır.
3. Sunucunun döndürdüğü yinelenen asset UUID'leri elenir.
4. İlgili kaynakta yakın zamanda gösterilen UUID'ler adaylardan çıkarılır.
5. Kalan adaylardan biri `secrets.choice` ile eşit olasılıkla seçilir.
6. Adayların tamamı yakın geçmişteyse en uzun süredir gösterilmeyen aday
   seçilir.

Geçmiş her kaynak için ayrı `deque` içinde yalnızca çalışma belleğinde tutulur.
Başarısız preview indirmesi geçmişe yazılmaz. Bu yaklaşım kalabalık
kütüphanelerde istek başına en fazla 100 metadata satırı taşır; küçük
albümlerdeyse en yeni tekrarı seçmek yerine en eski gösterilene geri döner.

## Güvenlik ve gizlilik kararları

- API anahtarı yalnızca `x-api-key` başlığında tutulur; URL'ye veya query
  parametresine eklenmez.
- Kullanıcı adı/şifre içeren, query veya fragment barındıran sunucu URL'leri
  reddedilir.
- HTTP yönlendirmeleri izlenmez; anahtarın başka bir origin'e taşınması
  engellenir.
- TLS doğrulaması varsayılan olarak açıktır.
- Orijinal dosya yerine Immich'in `preview` çıktısı alınır.
- Yalnızca AVIF, GIF, JPEG, PNG ve WebP yanıtları kabul edilir.
- Hem `Content-Length` hem de akış sırasında 20 MiB sınırı uygulanır.
- API yanıt gövdeleri, anahtarlar ve medya meta verileri loglanmaz.
- Entity state içine dosya adı, EXIF, asset ID veya çekim tarihi yazılmaz.
- Diagnostics; URL, API anahtarı, kullanıcı/entry ID, albüm/asset ID, dosya adı
  ve görsel içeriği içermez.
- Telemetri, analiz, hata raporlama servisi veya başka bir bulut geçidi yoktur.
- GitHub Actions bağımlılıkları değişmez commit SHA'larına sabitlenmiştir ve
  iş akışlarının izni `contents: read` ile sınırlıdır.

## Marka ve görsel kararı

Immich kaynak kodu AGPL-3.0 ile yayımlanıyor:
[Immich license](https://github.com/immich-app/immich/blob/main/LICENSE).
Ancak yazılım lisansı tek başına projenin adı ve logosuna ilişkin marka
haklarını üçüncü taraf entegrasyonlara otomatik olarak vermez.

Immich'in resmi FAQ sayfası, özellikle ürünle ilişki/endorsement izlenimi
yaratabilecek marka kullanımına karşı sınırlar koyuyor:
[Immich FAQ](https://docs.immich.app/FAQ/). FAQ aynı zamanda diğer
platformlara yönelik entegrasyonların uygun bildirim yapıldığında genellikle
onaylandığını belirtiyor.

Immich'in resmî Unraid kurulum belgesi, görsel tanımlama amacıyla doğrudan
`design/immich-logo.png` adresini kullanıcılara veriyor:
[Unraid installation](https://docs.immich.app/install/unraid/). Ayrıca resmî
deponun `design/` klasöründe kare, açık ve koyu wordmark dosyaları yayımlanıyor.

Tanınabilirlik kararı sonucunda kare HACS/HA ikonunda resmî Immich çiçeği
değiştirilmeden kullanıldı. GitHub README'sinde veya başka bir tanıtım
alanında Immich banner'ı, geniş wordmark, ekran görüntüsü ya da pazarlama
görseli kullanılmıyor. Yalnızca HACS ve Home Assistant'ın teknik olarak
okuduğu 256/512 piksel küçük ikonlar paketleniyor. Kaynak adresi ve SHA-256
değeri `BRANDING.md` içinde kayıtlıdır.

Immich işareti projenin MIT lisansına dahil edilmedi; sahibine ait marka olarak
açıkça ayrıldı. README ve marka belgesi bağımsızlık/endorsement bildirimini
taşıyor. İlk herkese açık sürümden önce Immich'e kısa proje ve marka kullanımı
bildirimi gönderilmesi planlandı. Bu araştırma hukuki görüş değildir.

Home Assistant 2026.3+ özel entegrasyonların yerel `brand/` klasörünü
destekliyor:
[Local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/).
Bu nedenle ikon ve açık/koyu logolar entegrasyon paketinde yerel tutuluyor;
çalışma sırasında marka görseli için dış servise istek atılmıyor.

## HACS varsayılan kütüphanesine giriş

HACS varsayılan listesi otomatik olarak yalnızca `hacs.json` ekleyerek
sağlanmıyor. Resmi sürece göre:

1. depo herkese açık, açıklamalı, konulu, Issues açık ve özel repo olarak HACS
   üzerinden kurulabilir durumda olmalı;
2. HACS Action ve Hassfest tüm kontrolleri ignore olmadan geçmeli;
3. yalnızca tag değil, tam bir GitHub Release yayımlanmalı;
4. repo sahibi veya büyük katkıcı `hacs/default` deposundaki `integration`
   listesine `"ofilis/ha-immich-gallery"` girdisini alfabetik ekleyen PR
   açmalı;
5. bakım ve destek yükümlülüğü inceleme boyunca ve kabulden sonra sürdürülmeli.

Resmi gereksinimler:
[publishing](https://www.hacs.xyz/docs/publish/start/),
[integration requirements](https://www.hacs.xyz/docs/publish/integration/),
[validation](https://hacs.xyz/docs/publish/action/) ve
[default inclusion](https://hacs.xyz/docs/publish/include/).

Bu proje yerleşik `immich` entegrasyonunun üzerine yazmaz ve onun alpha/beta
sürümü değildir. Ayrı `immich_gallery` domain'iyle, yerleşik entegrasyonun
sunmadığı dönen `image` entity kullanımını tamamlar. Gönderim adımları
`docs/HACS_SUBMISSION.md` içinde ayrıntılıdır.

## İlk sürüm kapsamı

Hazır:

- tüm kütüphaneden rastgele görsel;
- favorilerden rastgele görsel;
- seçilen birden fazla albüm için ayrı rastgele görsel entity'leri;
- 1–60 dakika yenileme aralığı;
- Configure ekranından host, anahtar, TLS, kaynak, tekrar penceresi ve süre
  değişikliği;
- UI kurulumu, options flow, reauthentication ve reconfigure;
- Türkçe ve İngilizce arayüz;
- kaynak ve hash bilgisi belgelenmiş yerel Immich marka varlıkları;
- HACS yapısı, varsayılan-kütüphane gönderim rehberi, MIT lisansı, güvenlik
  politikası ve CI;
- Home Assistant 2026.4+ hedefi.

Sonraki sürümlere bırakılan olası işler:

- kişi, tarih aralığı, puan veya konum filtreleri;
- “son eklenenler” gibi sıralı modlar;
- dashboard kartı için isteğe bağlı servislerle anında sonraki görsele geçme;
- animasyon/video desteği;
- canlı Immich sunucusuna karşı opt-in entegrasyon testleri.

Yeni filtreler eklenirken yalnızca gerekli ek okuma yetkileri istenecek; yazma
ve silme yetkileri ürün kapsamına alınmayacaktır.
