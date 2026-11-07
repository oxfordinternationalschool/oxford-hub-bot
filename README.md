# Oxford Hub — Oxford International School Telegram boti

Sinf guruhlarini boshqarish uchun bot (Telegram'da: **Oxford Hub**, [@OIS_HubBot](https://t.me/OIS_HubBot)):

- **📢 E'lonlar**: bir klikda barcha guruhlarga, parallel bo'yicha (masalan, hamma 9-sinflarga) yoki tanlangan guruhlarga yuboriladi. Pin qilish mumkin, kerak bo'lsa hamma guruhlardan bir klikda o'chiriladi.
- **🧹 Xodimni chaqirish**: o'qituvchi guruhda `#cleaner suv to'kildi` deb yozadi va xabar shu roldagi xodimning shaxsiy chatiga boradi. Xodim «Qabul qilaman» va «Bajarildi» tugmalarini bosadi. Sinf chaqiruvni ko'rmaydi: holat faqat o'qituvchiga ko'rinadi.
- **🏢 Qavatlar**: qavat bo'yicha ishlaydigan rollar (masalan, cleaner) faqat sinf joylashgan qavatdagi xodimga boradi.
- **⚠️ Eskalatsiya**: chaqiruvni 5 daqiqa ichida hech kim qabul qilmasa (shoshilinch chaqiruvda 2 daqiqa), adminlarga xabar boradi.
- **🌐 3 til**: o'zbekcha, ruscha va inglizcha. Har kim o'z tilini tanlaydi, guruh tili esa alohida sozlanadi.
- **📱 Admin Mini App**: Telegram ichida ochiladigan to'liq boshqaruv paneli: e'lonlar, chaqiruvlar, xodimlar, guruhlar, rollar, qavatlar, havolalar va statistika (5-bo'lim).

---

Bot ikki xil usulda ishlaydi:
- **Kompyuterda** (sinab ko'rish uchun): `run.bat` orqali. Bot kompyuter yoqiq turgan paytda ishlaydi.
- **Vercel + Supabase'da** (doimiy ishlash uchun): kompyuter kerak emas, 24/7 ishlaydi. Qo'llanma 4-bo'limda.

## 1. Kompyuterda ishga tushirish

1. [@BotFather](https://t.me/BotFather) da `/newbot` buyrug'ini yuboring. Nom so'ralganda `Oxford Hub` deb yozing, username so'ralganda `OIS_HubBot` deb yozing. Oxirida BotFather token beradi. Maktab logotipini `/setuserpic` buyrug'i bilan botning rasmi qilib qo'yish mumkin. Bot tavsifini esa bot o'zi 3 tilda o'rnatadi.
2. O'sha joyda `/mybots` → botingiz → **Bot Settings → Group Privacy → Turn off** ni bosing. Shunda bot guruhdagi `#cleaner` kabi teglarni ko'ra oladi.
3. `.env.example` faylidan nusxa olib, `.env` deb nomlang va ichiga quyidagilarni yozing:
   - `BOT_TOKEN`: BotFather bergan token
   - `ADMIN_IDS`: bosh admin(lar)ning Telegram ID raqami. ID ni bilmasangiz, avval botni ishga tushiring, botga `/me` yozing, so'ng ID ni shu yerga qo'yib, botni qayta ishga tushiring.
4. `run.bat` faylini ikki marta bosing. Birinchi marta kutubxonalar o'rnatiladi, keyin bot ishga tushadi.

Qo'lda ishga tushirish:

```bash
python -m venv .venv
```
```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
```bash
.venv\Scripts\python.exe -m bot
```

> Bot faqat kompyuter yoqiq va `run.bat` oynasi ochiq turgan paytda ishlaydi.

## 2. Birinchi sozlash (admin, bot bilan shaxsiy chatda)

```
/addrole cleaner 🧹 Tozalovchi
/addrole doctor 🩺 Shifokor
/addrole inspector 🛡 Inspektor
/rolefloor cleaner on          ← cleaner qavat bo'yicha ishlaydi
/alias cleaner clean tozalash  ← #clean va #tozalash ham ishlaydi

/addfloor 1-qavat
/addfloor 2-qavat
/addfloor 3-qavat
```

### Xodimlarni qo'shish (taklif havolalari)

```
/invite teacher 60             ← barcha o'qituvchilar uchun bitta havola (60 kishiga)
/invite cleaner 1 2-qavat      ← 2-qavat tozalovchisi uchun
/invite doctor                 ← shifokor uchun
/invite announcer              ← e'lon yubora oladigan shaxs uchun
```

Bot havola beradi. Uni xodimga yuborasiz, xodim havolani bosadi va avtomatik ro'yxatdan o'tadi. Har bir yangi xodim haqida adminlarga xabar keladi.

> ⚠️ Bot xodimga xabar yubora olishi uchun xodim botni **kamida bir marta** ochgan bo'lishi shart. Taklif havolasi orqali kirganda bu avtomatik bajariladi.

### Guruhlarni ulash

1. Botni har bir sinf guruhiga qo'shing va **admin** qiling. Botni faqat admin qo'sha oladi, boshqa odam qo'shsa bot guruhdan chiqib ketadi.
2. Bot sinfni guruh nomidan o'zi aniqlaydi (masalan, «7-B sinf» → `7-B`). Aniqlay olmasa, guruh ichida yozing: `/setclass 7-B`
3. Guruh ichida qavatni belgilang: `/setfloor 2-qavat`
4. Hammasini tekshirish uchun shaxsiy chatda `/groups` ni yozing.

## 3. Kundalik foydalanish

**O'qituvchi** (sinf guruhida):

| Yozadi | Natija |
|---|---|
| `#cleaner partada suv to'kilgan` | 2-qavat tozalovchisiga boradi |
| `/doctor` | shifokorga boradi |
| `#doctor! bola yiqildi` | 🚨 shoshilinch chaqiruv |
| biror xabarga reply qilib `#inspector` | o'sha xabar ham inspektorga boradi |

**Chaqiruvni sinf ko'rmaydi.**
- Guruhdagi **/** menyusidan tanlangan buyruq (`/cleaner`) Telegram'da yashirin buyruq: uni faqat bot ko'radi.
- Teg yozilgan xabarni (`#cleaner ...`) bot xodimga yuborgach guruhdan o'chiradi. Buning uchun botda "Xabarlarni o'chirish" huquqi bo'lishi kerak.
- Rasm yoki fayl biriktirilgan chaqiruv guruhda qoladi.
- Chaqiruv holati ("qabul qildi", "bajarildi") faqat o'qituvchining o'ziga ko'rinadi.

Rollar menyusi rol qo'shilganda yoki o'zgarganda o'zi yangilanadi.

**E'lon beruvchi** (shaxsiy chatda): tayyor e'lonni botga yuboring yoki forward qiling → **📢 Guruhlarga yuborish** → guruhlarni tanlang → 📤 Yuborish. E'lon guruhlarga aynan o'zidek boradi: formatlangan matn, rasm, video, fayl, ovozli xabar va **albom** ham. `/announce` buyrug'idan keyin yuborilgan xabarda guruhlar ro'yxati darhol ochiladi.

**Admin**: barcha buyruqlar ro'yxati `/admin` da. Statistika uchun `/stats 7` ni yozing.

**Guruh adminlarini tayinlash.** Botda guruhda "Yangi admin qo'shish" huquqi bo'lishi kerak.
- Guruhning o'zida odamning xabariga javoban `/promote` yozsangiz admin qiladi, `/demote` yozsangiz adminlikdan oladi.
- Mini App'da: **Yana → Guruh adminlari → Odamni tanlash**. Odam Telegram'ning o'z oynasidan tanlanadi va botga ulangan bo'lishi shart emas. Keyin guruhlarni belgilab, tasdiqlaysiz.
- Guruh oynasida o'sha guruhning adminlari ro'yxati chiqadi, u yerdan admin qo'shish yoki olib tashlash ham mumkin.
- Odam xabarlarni o'chirish, a'zolarni cheklash, qadash va odam qo'shish huquqini oladi. Yangi admin tayinlash huquqi berilmaydi.
- Odam guruhda bo'lmasa, uning qatorida **Taklif havolasi** tugmasi chiqadi. Bot faqat shu odam uchun bir martalik havola yaratadi (7 kun amal qiladi). Odam havola orqali kirishi bilan bot uni admin qiladi va sizga xabar beradi. Havoladan boshqa odam kirsa, u oddiy a'zo bo'lib qoladi. Buning uchun botda "Foydalanuvchilarni taklif qilish" huquqi bo'lishi kerak.
- Telegram cheklovi: bot faqat o'zi tayinlagan adminlarni olib tashlay oladi.

## 4. Vercel + Supabase'ga joylashtirish (24/7)

Bu rejimda vazifalar quyidagicha taqsimlanadi:
- **Supabase**: ma'lumotlar bazasi. Bundan tashqari, har daqiqada botni "uyg'otib" turadi (Supabase Cron). Bu qabul qilinmagan chaqiruvlarni adminlarga yuborish uchun kerak.
- **Vercel**: botning kodi. Telegram har bir yangi xabarni Vercel'ga o'zi yuboradi (webhook).

### 4.1. Supabase

1. [supabase.com](https://supabase.com) da **New project** ni bosing. Region uchun **Frankfurt (eu-central-1)** ni tanlang, u O'zbekistonga yaqin. Ma'lumotlar bazasi parolini saqlab qo'ying.
   > Parolda faqat harf va raqam ishlating. `@ # / ?` kabi belgilar ulanish manzilini buzadi.
2. Loyiha ochilgach, yuqoridagi **Connect** tugmasini bosing va **Transaction pooler** manzilini (port **6543**) nusxalang. Unda `[YOUR-PASSWORD]` o'rniga parolingizni yozing. Bu sizning `DATABASE_URL` manzilingiz bo'ladi.

### 4.2. Maxfiy so'z

Telegram va Supabase botga murojaat qilganini tekshirish uchun maxfiy so'z kerak. Uni yarating:

```bash
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Chiqqan qatorni `WEBHOOK_SECRET` sifatida saqlang.

### 4.3. Vercel

1. Kodni GitHub'ga yuklang. Bunda `.env` fayli yuklanmaydi, chunki u `.gitignore` da.
2. [vercel.com](https://vercel.com) da **Add New → Project** ni bosing va GitHub repozitoriyani tanlang. **Framework Preset** maydonida **Other** ni qoldiring.
3. **Environment Variables** bo'limiga quyidagilarni qo'shing:

   | Nomi | Qiymati |
   |---|---|
   | `BOT_TOKEN` | BotFather bergan token |
   | `ADMIN_IDS` | bosh adminlar ID raqamlari, vergul bilan |
   | `DATABASE_URL` | 4.1-bo'limdagi Supabase manzili |
   | `WEBHOOK_SECRET` | 4.2-bo'limdagi maxfiy so'z |

4. **Deploy** ni bosing. Tayyor bo'lgach, loyihaning asosiy manzilini nusxalang, masalan `https://oxford-bot.vercel.app`. Bu **Domains** bo'limidagi manzil bo'lishi kerak, "preview" manzil emas.

### 4.4. Ulash (bir marta, kompyuterdan)

`.env` faylida ham `DATABASE_URL` va `WEBHOOK_SECRET` xuddi Vercel'dagidek bo'lishi kerak. Keyin quyidagini ishga tushiring:

```bash
.venv\Scripts\python.exe -m bot.setup_webhook https://oxford-bot.vercel.app
```

Bu buyruq uchta ishni bajaradi:
1. Supabase'da jadvallarni yaratadi.
2. Telegram'ga botning Vercel'dagi manzilini beradi.
3. Supabase Cron'ni har daqiqada botni chaqiradigan qilib sozlaydi.

Agar 3-qadam bajarilmasa, buyruq nima qilish kerakligini aytadi: Supabase'da `pg_cron` va `pg_net` kengaytmalarini yoqib, [supabase/cron.sql](supabase/cron.sql) faylidagi so'rovni SQL Editor'da bajarasiz.

**Tekshirish:** brauzerda `https://oxford-bot.vercel.app/api` ni oching. "bot is running" yozuvi chiqishi kerak. Keyin botga Telegram'da `/start` yozing.

### Bilib qo'yish kerak bo'lgan narsalar

- Vercel'da ishlayotgan paytda `run.bat` ni ishga tushirsangiz, bot to'xtaydi va ogohlantiradi, chunki ikki joyda bir vaqtda ishlay olmaydi. Kompyuterda sinash kerak bo'lsa, `python -m bot --force-polling` buyrug'ini ishlating. Keyin Vercel'ga qaytarish uchun `setup_webhook` buyrug'ini qayta bajaring.
- Kodni o'zgartirib GitHub'ga yuklasangiz, Vercel o'zi qayta joylaydi. `setup_webhook` ni qayta bajarish shart emas. Faqat bazaga yangi jadval yoki ustun qo'shilgan bo'lsa, uni bir marta qayta bajaring: tezlik uchun bot ishlash paytida jadvallarni tekshirmaydi.
- Bot Vercel'ning Frankfurt (`fra1`) serverida, Supabase bazasi bilan bir hududda ishlaydi (`vercel.json` dagi `regions`). Supabase loyihasi boshqa hududda bo'lsa, buni ham o'shanga moslang.
- "Faqat o'qituvchilar chaqira oladi" ogohlantirishi faqat o'sha o'quvchiga ko'rinadi. Telegram buni rad etsa, ogohlantirish hammaga ko'rinadi va taxminan 1 daqiqada o'chadi (Supabase Cron orqali).
- **Narxlar:** Vercel'ning bepul Hobby tarifi faqat shaxsiy va notijorat loyihalar uchun. Xususiy maktab uchun Pro tarifi talab qilinishi mumkin. Supabase'ning bepul loyihasi uzoq vaqt ishlatilmasa, pauzaga tushadi.

## 5. Admin Mini App

Telegram ichida ochiladigan boshqaruv paneli. U faqat adminlarga ko'rinadi va faqat adminlar uchun ishlaydi: Telegram har bir ochilishni bot tokeni bilan imzolaydi, server esa shu imzoni tekshiradi.

**Qanday ochiladi:** bot bilan chatda xabar yozish maydoni yonidagi **Panel** tugmasi orqali yoki `/admin` → **📱 Mini App panel** orqali.

| Bo'lim | Nima qilsa bo'ladi |
|---|---|
| Asosiy | Raqamlar, ogohlantirishlar (masalan, "bot admin emas", "qavat yo'q"), kutilayotgan chaqiruvlar |
| E'lon | Matn yozish, hamma/parallel/tanlangan guruhlarga yuborish, pin qilish, yuborilganlarni hammasidan o'chirish |
| Chaqiruvlar | Kutilayotgan va barcha chaqiruvlar, osilib qolganini yopish |
| Xodimlar | Qidirish, admin/e'lon beruvchi/o'qituvchi huquqlarini yoqib-o'chirish, rol va qavat berish yoki olish |
| Guruhlar | Sinf, qavat va tilni o'zgartirish, Telegram'dan tekshirish (bot hali admin ekanmi), guruh adminlari ro'yxati, admin qo'shish yoki olib tashlash, guruhni botdan olib tashlash (bot chiqadi; qayta qo'shilsa, sozlamalari bilan qaytadi) |
| Guruh adminlari | Istalgan odamni (botga ulanmagan bo'lsa ham) tanlab, belgilangan guruhlarda admin qilish |
| Rollar | Yaratish, emoji/nom/qo'shimcha teglarni o'zgartirish, qavat bo'yicha yo'naltirish, o'chirish |
| Qavatlar | Qo'shish, nomini o'zgartirish, o'chirish |
| Havolalar | Taklif havolasi yaratish (nusxa olish yoki ulashish), bekor qilish |
| Statistika | 1/7/30/90 kunlik: rollar bo'yicha va eng ko'p chaqirgan sinflar |

Tayyor e'lonni (albom ham bo'ladi) botning o'ziga yuborib ham tarqatish mumkin (3-bo'lim). Botga yuborilgan rasm va videolar Mini App'dagi biriktirmalarda ham ko'rinadi.

### Maktab akkauntiga story

Rasmli e'lonni maktabning Telegram akkauntiga **story** qilib ham qo'yish mumkin. Bot story'ni faqat ulangan akkaunt nomidan qo'ya oladi. Kanal yoki guruh story'siga qo'yishga Telegram botlarga ruxsat bermaydi. Telegram Premium kerak emas.

1. BotFather → @OIS_HubBot → **Bot Settings → Secretary Mode** ni yoqing.
2. Maktab akkauntida: **Settings → Telegram Business → Chatbots** → `@OIS_HubBot` ni qo'shing. Ruxsatlardan faqat **Manage stories** ni qoldiring.
3. Adminlarga "🔗 … akkaunti botni ulab qo'ydi" degan xabar keladi → **✅ Ha, maktab akkaunti** ni bosing.

Shundan keyin:
- **botda** rasmli e'lon yuborilgach, hisobot ostida **📲 Story qilib qo'yish** tugmasi chiqadi. U yerda 6, 12, 24 yoki 48 soatni tanlaysiz;
- **Mini App'da** rasm biriktirilgan bo'lsa, **Story ham qo'yish** tugmasi chiqadi. Story 24 soat turadi.

Rasm story o'lchamiga (1080×1920) avtomatik moslanadi: rasm o'rtada, orqasida uning xiralashtirilgan nusxasi. Video story qilinmaydi, chunki Telegram story videosi uchun alohida format talab qiladi.

**Kanal yoki guruhga story.** Bot buni o'zi qila olmaydi: Telegram botlarga ruxsat bermaydi. Buning o'rniga Mini App → E'lon → **Yuborilganlar** ro'yxatida rasmli e'lon yonidagi yashil tugmani bosing. Telegram'ning o'z story muharriri e'lon rasmi va matni bilan ochiladi, story'ni u yerdan o'zingiz joylaysiz. Kanalni tanlash imkoni bo'lsa, kanalga ham qo'yiladi. Kanal story qo'yishi uchun Telegram boost talab qiladi.

**Vercel'da** Mini App o'zi ishlaydi: sahifa `https://SIZNING-LOYIHA.vercel.app/admin/` manzilida bo'ladi. `setup_webhook` buyrug'i adminlarga **Panel** tugmasini qo'yadi. Vercel loyiha manzilini botga o'zi beradi. Boshqa manzil (masalan, o'z domeningiz) ishlatilsa, Vercel'da `WEBAPP_URL` o'zgaruvchisini qo'shing.

**Kompyuterda sinash (ixtiyoriy).** Telegram Mini App'ni faqat HTTPS manzildan ochadi, shuning uchun kompyuterda tunnel kerak bo'ladi:
1. `.venv\Scripts\python.exe -m bot.devserver` buyrug'ini ishga tushiring. Mini App `http://localhost:8080/admin/` manzilida ochiladi.
2. Tunnel ishga tushiring, masalan [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/): `cloudflared tunnel --url http://localhost:8080`
3. Chiqqan `https://….trycloudflare.com` manzilining oxiriga `/admin/` qo'shib, `.env` dagi `WEBAPP_URL=` ga yozing va botni qayta ishga tushiring.

## 6. Testlar

```bash
.venv\Scripts\python.exe -m pip install pytest pytest-asyncio
```
```bash
.venv\Scripts\python.exe -m pytest
```

## Loyiha tuzilmasi

```
api/index.py           Vercel kirish nuqtasi
public/admin/          admin Mini App (bitta HTML sahifa)
supabase/cron.sql      Supabase Cron (qo'lda sozlash uchun)
bot/
  __main__.py          kompyuterda ishga tushirish (polling)
  webhook.py           Vercel uchun: Telegram webhook, Mini App API va cron so'rovlari
  webapp_api.py        Mini App API (initData imzosini tekshiradi, faqat adminlar)
  devserver.py         Mini App'ni kompyuterda sinash uchun server
  setup_webhook.py     Vercel + Supabase'ni bir marta ulash
  app.py               ikkala rejim uchun umumiy sozlash
  storage.py           suhbat holati (e'lon qoralamasi) bazada
  config.py            .env sozlamalari
  i18n.py              uz/ru/en matnlar
  db/models.py         ma'lumotlar bazasi jadvallari
  handlers/
    start.py           /start, til, taklif havolalari, /me, /help
    admin.py           rollar, qavatlar, xodimlar, /stats (buyruqlar)
    admin_panel.py     /admin tugmali panel
    groups.py          guruhga qo'shilish, /setclass, /setfloor
    calls.py           #teg orqali xodim chaqirish
    announce.py        e'lonlar
  services/            chaqiruv, e'lon va boshqa mantiq
tests/                 avtomatik testlar
```
