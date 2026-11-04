"""All user-facing texts in Uzbek, Russian and English. Texts are HTML (parse_mode=HTML)."""

LANG_LABELS = {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

TEXTS: dict[str, dict[str, str]] = {
    # ---------- Start / profile ----------
    "choose_lang": {
        "uz": "Tilni tanlang:",
        "ru": "Выберите язык:",
        "en": "Choose your language:",
    },
    "lang_set": {
        "uz": "✅ Til: O'zbekcha",
        "ru": "✅ Язык: Русский",
        "en": "✅ Language: English",
    },
    "welcome": {
        "uz": "Assalomu alaykum, <b>{name}</b>! 👋\nMen <b>Oxford Hub</b> — Oxford International School boti.",
        "ru": "Здравствуйте, <b>{name}</b>! 👋\nЯ <b>Oxford Hub</b> — бот Oxford International School.",
        "en": "Hello, <b>{name}</b>! 👋\nI'm <b>Oxford Hub</b>, the Oxford International School bot.",
    },
    "your_roles": {
        "uz": "Sizning rollaringiz: {roles}",
        "ru": "Ваши роли: {roles}",
        "en": "Your roles: {roles}",
    },
    "no_roles_yet": {
        "uz": "Sizga hali rol berilmagan. Admindan taklif havolasini so'rang yoki unga ID raqamingizni yuboring: <code>{id}</code>",
        "ru": "У вас пока нет роли. Попросите у администратора ссылку-приглашение или отправьте ему свой ID: <code>{id}</code>",
        "en": "You have no role yet. Ask an admin for an invite link or send them your ID: <code>{id}</code>",
    },
    "see_help": {
        "uz": "Buyruqlar: /help",
        "ru": "Команды: /help",
        "en": "Commands: /help",
    },
    "me": {
        "uz": "👤 <b>{name}</b>\nID: <code>{id}</code>\nUsername: {username}\nRollar: {roles}",
        "ru": "👤 <b>{name}</b>\nID: <code>{id}</code>\nUsername: {username}\nРоли: {roles}",
        "en": "👤 <b>{name}</b>\nID: <code>{id}</code>\nUsername: {username}\nRoles: {roles}",
    },
    "perm_admin": {"uz": "👑 Admin", "ru": "👑 Админ", "en": "👑 Admin"},
    "perm_announcer": {"uz": "📢 E'lon beruvchi", "ru": "📢 Публикует объявления", "en": "📢 Announcer"},
    "perm_teacher": {"uz": "👩‍🏫 O'qituvchi", "ru": "👩‍🏫 Учитель", "en": "👩‍🏫 Teacher"},
    "inv_invalid": {
        "uz": "❌ Havola yaroqsiz yoki muddati tugagan. Admindan yangisini so'rang.",
        "ru": "❌ Ссылка недействительна или устарела. Попросите у администратора новую.",
        "en": "❌ This link is invalid or expired. Ask an admin for a new one.",
    },
    "inv_ok": {
        "uz": "✅ Sizga rol berildi: {what}",
        "ru": "✅ Вам назначена роль: {what}",
        "en": "✅ You have been given the role: {what}",
    },
    "pick_floor": {
        "uz": "{role}: qaysi qavatda ishlaysiz?",
        "ru": "{role}: на каком этаже вы работаете?",
        "en": "{role}: which floor do you work on?",
    },
    "all_floors": {"uz": "Barcha qavatlar", "ru": "Все этажи", "en": "All floors"},
    "floor_picked": {
        "uz": "✅ {role} — {floor}",
        "ru": "✅ {role} — {floor}",
        "en": "✅ {role} — {floor}",
    },
    "adm_new_member": {
        "uz": "🆕 {user} ro'yxatdan o'tdi: {what}",
        "ru": "🆕 {user} зарегистрировался: {what}",
        "en": "🆕 {user} registered as: {what}",
    },
    "cancelled": {"uz": "Bekor qilindi.", "ru": "Отменено.", "en": "Cancelled."},
    "unknown": {
        "uz": "Buyruqni tushunmadim. Ro'yxat: /help",
        "ru": "Не понял команду. Список: /help",
        "en": "I didn't understand that. See /help",
    },
    "expired": {
        "uz": "Bu tugmalar eskirgan. Qaytadan boshlang.",
        "ru": "Эти кнопки устарели. Начните заново.",
        "en": "These buttons have expired. Please start again.",
    },
    "cannot_do": {
        "uz": "Bu amalni bajara olmaysiz.",
        "ru": "Вы не можете выполнить это действие.",
        "en": "You can't do that.",
    },

    # ---------- Help ----------
    "help_basic": {
        "uz": "<b>ℹ️ Buyruqlar</b>\n/me — mening ma'lumotlarim\n/lang — tilni o'zgartirish\n/cancel — amalni bekor qilish",
        "ru": "<b>ℹ️ Команды</b>\n/me — мои данные\n/lang — сменить язык\n/cancel — отменить действие",
        "en": "<b>ℹ️ Commands</b>\n/me — my profile\n/lang — change language\n/cancel — cancel current action",
    },
    "help_teacher": {
        "uz": (
            "<b>👩‍🏫 Xodimni chaqirish</b>\n"
            "Sinf guruhida rol tegini yozing:\n"
            "<code>#cleaner partada suv to'kilgan</code>\n"
            "<code>#doctor!</code> — 🚨 shoshilinch chaqiruv\n"
            "Biror xabarga javob (reply) qilib yozsangiz, o'sha xabar ham xodimga yuboriladi.\n\n"
            "🤫 Chaqiruvni sinf ko'rmaydi: bot teg yozilgan xabarni o'chiradi, holatini esa faqat sizga ko'rsatadi. "
            "Guruhdagi <b>/</b> menyusidan tanlangan buyruq (<code>/cleaner</code>) esa umuman ko'rinmaydi. "
            "Rasm yoki fayl biriktirilgan chaqiruv guruhda qoladi."
        ),
        "ru": (
            "<b>👩‍🏫 Вызов сотрудника</b>\n"
            "Напишите тег роли в группе класса:\n"
            "<code>#cleaner на парте пролита вода</code>\n"
            "<code>#doctor!</code> — 🚨 срочный вызов\n"
            "Если написать ответом (reply) на сообщение, оно тоже будет отправлено сотруднику.\n\n"
            "🤫 Класс не видит вызов: бот удаляет сообщение с тегом, а его статус показывает только вам. "
            "Команда из меню <b>/</b> в группе (<code>/cleaner</code>) не видна вовсе. "
            "Вызов с фото или файлом остаётся в группе."
        ),
        "en": (
            "<b>👩‍🏫 Calling staff</b>\n"
            "Write the role tag in a class group:\n"
            "<code>#cleaner water spilled on a desk</code>\n"
            "<code>#doctor!</code> — 🚨 urgent call\n"
            "If you write it as a reply to a message, that message is sent to the staff member too.\n\n"
            "🤫 The class doesn't see the call: the bot deletes the tag message and shows its status to you only. "
            "A command picked from the group's <b>/</b> menu (<code>/cleaner</code>) isn't visible at all. "
            "A call with a photo or file attached stays in the group."
        ),
    },
    "help_roles": {
        "uz": "Mavjud teglar: {triggers}",
        "ru": "Доступные теги: {triggers}",
        "en": "Available tags: {triggers}",
    },
    "help_announcer": {
        "uz": (
            "<b>📢 E'lonlar</b>\n/announce — barcha yoki tanlangan guruhlarga e'lon yuborish\n"
            "Yoki tayyor e'lonni (albom ham bo'ladi) shu chatga yuboring yoki forward qiling → 📢 Guruhlarga yuborish"
        ),
        "ru": (
            "<b>📢 Объявления</b>\n/announce — отправить объявление во все или выбранные группы\n"
            "Или пришлите/перешлите сюда готовое объявление (можно альбом) → 📢 Отправить в группы"
        ),
        "en": (
            "<b>📢 Announcements</b>\n/announce — send an announcement to all or selected groups\n"
            "Or send/forward a finished announcement here (albums too) → 📢 Send to groups"
        ),
    },
    "help_admin": {
        "uz": (
            "<b>⚙️ Admin buyruqlari</b>\nTugmali panel: /admin\n\n"
            "<b>Rollar</b>\n"
            "/roles — rollar ro'yxati\n"
            "<code>/addrole cleaner 🧹 Tozalovchi</code> — yangi rol\n"
            "<code>/delrole cleaner</code> — rolni o'chirish\n"
            "<code>/rolefloor cleaner on</code> — qavat bo'yicha yo'naltirish (on/off)\n"
            "<code>/alias cleaner clean tozalash</code> — qo'shimcha teglar (#clean, #tozalash)\n"
            "<code>/unalias cleaner clean</code> — tegni olib tashlash\n\n"
            "<b>Qavatlar</b>\n"
            "/floors — qavatlar va sinflar\n"
            "<code>/addfloor 2-qavat</code> — qavat qo'shish\n"
            "<code>/delfloor 2-qavat</code> — qavatni o'chirish\n\n"
            "<b>Xodimlar</b>\n"
            "<code>/invite teacher 60</code> — o'qituvchilar uchun havola (60 kishiga)\n"
            "<code>/invite cleaner 1 2-qavat</code> — xodim uchun havola (qavati bilan)\n"
            "<code>/invite announcer</code>, <code>/invite admin</code> — e'lon beruvchi / admin\n"
            "/invites — faol havolalar · <code>/revoke KOD</code> — havolani bekor qilish\n"
            "/staff — barcha xodimlar · <code>/staff cleaner</code> — bitta rol\n"
            "<code>/assign 123456789 cleaner 2-qavat</code> — rol berish (ID yoki @username)\n"
            "<code>/unassign 123456789 cleaner</code> — rolni olib qo'yish\n\n"
            "<b>Guruhlar</b>\n"
            "/groups — ulangan guruhlar\n"
            "Guruh ichida: <code>/setclass 7-B</code> · <code>/setfloor 2-qavat</code> · <code>/grouplang ru</code> · /groupinfo\n"
            "Kimningdir xabariga javoban: /promote — guruh admini qilish · /demote — adminlikdan olish\n\n"
            "<b>Statistika</b>\n"
            "<code>/stats 7</code> — oxirgi 7 kunlik chaqiruvlar"
        ),
        "ru": (
            "<b>⚙️ Команды администратора</b>\nПанель с кнопками: /admin\n\n"
            "<b>Роли</b>\n"
            "/roles — список ролей\n"
            "<code>/addrole cleaner 🧹 Уборщица</code> — новая роль\n"
            "<code>/delrole cleaner</code> — удалить роль\n"
            "<code>/rolefloor cleaner on</code> — направлять по этажам (on/off)\n"
            "<code>/alias cleaner clean уборка</code> — дополнительные теги (#clean, #уборка)\n"
            "<code>/unalias cleaner clean</code> — убрать тег\n\n"
            "<b>Этажи</b>\n"
            "/floors — этажи и классы\n"
            "<code>/addfloor 2-этаж</code> — добавить этаж\n"
            "<code>/delfloor 2-этаж</code> — удалить этаж\n\n"
            "<b>Сотрудники</b>\n"
            "<code>/invite teacher 60</code> — ссылка для учителей (на 60 человек)\n"
            "<code>/invite cleaner 1 2-этаж</code> — ссылка для сотрудника (с этажом)\n"
            "<code>/invite announcer</code>, <code>/invite admin</code> — публикующий / админ\n"
            "/invites — активные ссылки · <code>/revoke КОД</code> — отменить ссылку\n"
            "/staff — все сотрудники · <code>/staff cleaner</code> — одна роль\n"
            "<code>/assign 123456789 cleaner 2-этаж</code> — назначить роль (ID или @username)\n"
            "<code>/unassign 123456789 cleaner</code> — снять роль\n\n"
            "<b>Группы</b>\n"
            "/groups — подключённые группы\n"
            "Внутри группы: <code>/setclass 7-B</code> · <code>/setfloor 2-этаж</code> · <code>/grouplang ru</code> · /groupinfo\n"
            "Ответом на чьё-то сообщение: /promote — сделать админом группы · /demote — снять админа\n\n"
            "<b>Статистика</b>\n"
            "<code>/stats 7</code> — вызовы за последние 7 дней"
        ),
        "en": (
            "<b>⚙️ Admin commands</b>\nButton panel: /admin\n\n"
            "<b>Roles</b>\n"
            "/roles — list roles\n"
            "<code>/addrole cleaner 🧹 Cleaner</code> — new role\n"
            "<code>/delrole cleaner</code> — delete a role\n"
            "<code>/rolefloor cleaner on</code> — route by floor (on/off)\n"
            "<code>/alias cleaner clean</code> — extra tags (#clean)\n"
            "<code>/unalias cleaner clean</code> — remove a tag\n\n"
            "<b>Floors</b>\n"
            "/floors — floors and classes\n"
            "<code>/addfloor Floor 2</code> — add a floor\n"
            "<code>/delfloor Floor 2</code> — delete a floor\n\n"
            "<b>Staff</b>\n"
            "<code>/invite teacher 60</code> — invite link for teachers (60 uses)\n"
            "<code>/invite cleaner 1 Floor 2</code> — invite link for staff (with floor)\n"
            "<code>/invite announcer</code>, <code>/invite admin</code> — announcer / admin\n"
            "/invites — active links · <code>/revoke CODE</code> — revoke a link\n"
            "/staff — all staff · <code>/staff cleaner</code> — one role\n"
            "<code>/assign 123456789 cleaner Floor 2</code> — give a role (ID or @username)\n"
            "<code>/unassign 123456789 cleaner</code> — take a role away\n\n"
            "<b>Groups</b>\n"
            "/groups — connected groups\n"
            "Inside a group: <code>/setclass 7-B</code> · <code>/setfloor Floor 2</code> · <code>/grouplang ru</code> · /groupinfo\n"
            "As a reply to someone's message: /promote — make them a group admin · /demote — remove them as admin\n\n"
            "<b>Statistics</b>\n"
            "<code>/stats 7</code> — calls over the last 7 days"
        ),
    },

    # ---------- Admin panel (buttons) ----------
    "see_admin": {
        "uz": "⚙️ Admin panel: /admin · Barcha buyruqlar: /help",
        "ru": "⚙️ Админ-панель: /admin · Все команды: /help",
        "en": "⚙️ Admin panel: /admin · All commands: /help",
    },
    "panel_title": {
        "uz": "⚙️ <b>Admin panel</b>\nBo'limni tanlang:",
        "ru": "⚙️ <b>Админ-панель</b>\nВыберите раздел:",
        "en": "⚙️ <b>Admin panel</b>\nChoose a section:",
    },
    "btn_roles": {"uz": "🏷 Rollar", "ru": "🏷 Роли", "en": "🏷 Roles"},
    "btn_floors": {"uz": "🏢 Qavatlar", "ru": "🏢 Этажи", "en": "🏢 Floors"},
    "btn_staff": {"uz": "👥 Xodimlar", "ru": "👥 Сотрудники", "en": "👥 Staff"},
    "btn_groups": {"uz": "🏫 Guruhlar", "ru": "🏫 Группы", "en": "🏫 Groups"},
    "btn_announce": {"uz": "📢 E'lon", "ru": "📢 Объявление", "en": "📢 Announcement"},
    "btn_stats": {"uz": "📊 Statistika", "ru": "📊 Статистика", "en": "📊 Statistics"},
    "btn_back": {"uz": "⬅️ Orqaga", "ru": "⬅️ Назад", "en": "⬅️ Back"},
    "btn_add_role": {"uz": "➕ Rol qo'shish", "ru": "➕ Добавить роль", "en": "➕ Add role"},
    "btn_add_floor": {"uz": "➕ Qavat qo'shish", "ru": "➕ Добавить этаж", "en": "➕ Add floor"},
    "btn_invite": {"uz": "🔗 Taklif havolasi", "ru": "🔗 Ссылка-приглашение", "en": "🔗 Invite link"},
    "btn_more_invite": {"uz": "🔗 Yana havola", "ru": "🔗 Ещё ссылка", "en": "🔗 Another link"},
    "btn_invites": {"uz": "📋 Faol havolalar", "ru": "📋 Активные ссылки", "en": "📋 Active links"},
    "btn_staff_list": {"uz": "👥 Xodimlari", "ru": "👥 Сотрудники", "en": "👥 Its staff"},
    "btn_delete": {"uz": "🗑 O'chirish", "ru": "🗑 Удалить", "en": "🗑 Delete"},
    "btn_confirm_delete": {"uz": "✅ Ha, o'chirish", "ru": "✅ Да, удалить", "en": "✅ Yes, delete"},
    "btn_floor_on": {
        "uz": "🏢 Qavat bo'yicha: ✅ yoqilgan",
        "ru": "🏢 По этажам: ✅ включено",
        "en": "🏢 By floor: ✅ on",
    },
    "btn_floor_off": {
        "uz": "🏢 Qavat bo'yicha: o'chiq",
        "ru": "🏢 По этажам: выключено",
        "en": "🏢 By floor: off",
    },
    "btn_refresh": {"uz": "🔄 Yangilash", "ru": "🔄 Обновить", "en": "🔄 Refresh"},
    "ask_role_input": {
        "uz": "Yangi rolni bitta xabarda yuboring: <b>kalit</b>, emoji va nom.\nMasalan: <code>cleaner 🧹 Tozalovchi</code>\n\nKalit — guruhda yoziladigan teg (#cleaner). Bekor qilish: /cancel",
        "ru": "Отправьте новую роль одним сообщением: <b>ключ</b>, эмодзи и название.\nНапример: <code>cleaner 🧹 Уборщица</code>\n\nКлюч — тег, который пишут в группе (#cleaner). Отмена: /cancel",
        "en": "Send the new role in one message: <b>key</b>, emoji and name.\nExample: <code>cleaner 🧹 Cleaner</code>\n\nThe key is the tag written in groups (#cleaner). Cancel: /cancel",
    },
    "ask_floor_input": {
        "uz": "Qavat nomini yuboring, masalan: <code>2-qavat</code>\nBekor qilish: /cancel",
        "ru": "Отправьте название этажа, например: <code>2-этаж</code>\nОтмена: /cancel",
        "en": "Send the floor name, for example: <code>Floor 2</code>\nCancel: /cancel",
    },
    "role_detail": {
        "uz": "<b>{title}</b>\nTeglar: {triggers}\nXodimlar: {n}\n{mode}",
        "ru": "<b>{title}</b>\nТеги: {triggers}\nСотрудников: {n}\n{mode}",
        "en": "<b>{title}</b>\nTags: {triggers}\nStaff: {n}\n{mode}",
    },
    "role_mode_floor": {
        "uz": "🏢 Chaqiruv sinf joylashgan qavatdagi xodimga boradi.",
        "ru": "🏢 Вызов идёт сотруднику этажа, где находится класс.",
        "en": "🏢 Calls go to staff on the class's floor.",
    },
    "role_mode_all": {
        "uz": "Chaqiruv shu roldagi barcha xodimlarga boradi.",
        "ru": "Вызов идёт всем сотрудникам этой роли.",
        "en": "Calls go to all staff with this role.",
    },
    "confirm_delete_role": {
        "uz": "{title} rolini o'chirasizmi?\nUnga biriktirilgan xodimlar roldan chiqariladi, havolalari bekor bo'ladi.",
        "ru": "Удалить роль {title}?\nСотрудники будут сняты с роли, ссылки-приглашения отменены.",
        "en": "Delete the role {title}?\nIts staff lose the role and its invite links are cancelled.",
    },
    "confirm_delete_floor": {
        "uz": "«{name}» qavatini o'chirasizmi?\nSinflar va xodimlar bu qavatdan ajratiladi.",
        "ru": "Удалить этаж «{name}»?\nКлассы и сотрудники будут отвязаны от этого этажа.",
        "en": "Delete the floor “{name}”?\nClasses and staff will be detached from it.",
    },
    "inv_pick_target": {
        "uz": "🔗 Havola kim uchun?",
        "ru": "🔗 Для кого ссылка?",
        "en": "🔗 Who is the link for?",
    },
    "inv_pick_uses": {
        "uz": "{what}: havoladan necha kishi foydalana oladi?",
        "ru": "{what}: сколько человек может воспользоваться ссылкой?",
        "en": "{what}: how many people can use the link?",
    },
    "inv_uses_n": {"uz": "{n} kishi", "ru": "{n} чел.", "en": "{n} people"},
    "inv_pick_floor": {
        "uz": "{what}: qaysi qavat uchun?",
        "ru": "{what}: для какого этажа?",
        "en": "{what}: which floor?",
    },
    "inv_floor_any": {
        "uz": "Xodim o'zi tanlaydi",
        "ru": "Сотрудник выберет сам",
        "en": "Staff member picks",
    },
    "staff_menu": {
        "uz": "👥 <b>Xodimlar</b>\nRo'yxatni ko'rish uchun tanlang:",
        "ru": "👥 <b>Сотрудники</b>\nВыберите, чей список показать:",
        "en": "👥 <b>Staff</b>\nChoose which list to show:",
    },
    "staff_remove_hint": {
        "uz": "Rolni olib qo'yish: <code>/unassign ID rol</code>, masalan <code>/unassign 123456789 teacher</code>",
        "ru": "Снять роль: <code>/unassign ID роль</code>, например <code>/unassign 123456789 teacher</code>",
        "en": "Remove a role: <code>/unassign ID role</code>, e.g. <code>/unassign 123456789 teacher</code>",
    },
    "list_cut": {
        "uz": "…va yana {n} qator. To'liq ro'yxat uchun buyruqdan foydalaning (/staff, /groups).",
        "ru": "…и ещё {n} строк. Полный список — командой (/staff, /groups).",
        "en": "…and {n} more lines. Use the command for the full list (/staff, /groups).",
    },
    "stats_days": {"uz": "{n} kun", "ru": "{n} дн.", "en": "{n} days"},

    # ---------- Mini App ----------
    "btn_mini_app": {"uz": "📱 Mini App panel", "ru": "📱 Mini App панель", "en": "📱 Mini App panel"},
    "menu_panel": {"uz": "Panel", "ru": "Панель", "en": "Panel"},
    "webapp_forbidden": {
        "uz": "Bu panel faqat adminlar uchun. Avval botga /start yozing.",
        "ru": "Эта панель только для администраторов. Сначала напишите боту /start.",
        "en": "This panel is for admins only. Send /start to the bot first.",
    },
    "webapp_cannot_demote": {
        "uz": "O'zingizni yoki bosh adminni (ADMIN_IDS) adminlikdan olib bo'lmaydi.",
        "ru": "Нельзя снять права админа с себя или с главного админа (ADMIN_IDS).",
        "en": "You can't remove admin rights from yourself or a main admin (ADMIN_IDS).",
    },
    "webapp_not_found": {
        "uz": "Topilmadi. Sahifani yangilang.",
        "ru": "Не найдено. Обновите страницу.",
        "en": "Not found. Please refresh.",
    },
    "webapp_media_too_big": {
        "uz": "Fayl juda katta (3 MB dan oshmasin). Kattaroq faylni botga yuboring, u «Botga yuborilganlar» ro'yxatida chiqadi.",
        "ru": "Файл слишком большой (не больше 3 МБ). Отправьте большой файл боту — он появится в списке «Отправленные боту».",
        "en": "The file is too big (3 MB max). Send larger files to the bot; they'll appear under “Sent to the bot”.",
    },
    "webapp_album_max": {
        "uz": "Albomga ko'pi bilan 10 ta rasm yoki video qo'shiladi.",
        "ru": "В альбоме может быть не больше 10 фото или видео.",
        "en": "An album can hold at most 10 photos or videos.",
    },
    "webapp_album_mix": {
        "uz": "Bular bitta albomga sig'maydi: rasm va videolarni birga, fayllarni alohida, audiolarni alohida yuboring. Ovozli xabar, video xabar va GIF faqat yakka yuboriladi.",
        "ru": "Это не собрать в один альбом: фото и видео — вместе, файлы — отдельно, аудио — отдельно. Голосовые, видеосообщения и GIF — только по одному.",
        "en": "These can't share one album: photos and videos go together, files separately, audio separately. Voice messages, video messages and GIFs go one at a time.",
    },
    "webapp_layout_needs_photos": {
        "uz": "Slideshow va kollaj uchun kamida 2 ta rasm yoki video tanlang (faqat rasm va video).",
        "ru": "Для слайд-шоу и коллажа выберите хотя бы 2 фото или видео (только фото и видео).",
        "en": "A slideshow or collage needs at least 2 photos or videos (photos and videos only).",
    },
    "webapp_upload_failed": {
        "uz": "Faylni Telegram'ga yuklab bo'lmadi. Uni botga to'g'ridan-to'g'ri yuborib ko'ring.",
        "ru": "Не удалось загрузить файл в Telegram. Попробуйте отправить его боту напрямую.",
        "en": "Couldn't upload the file to Telegram. Try sending it to the bot directly.",
    },
    "fwd_ask": {
        "uz": "📢 Shu xabarni guruhlarga yuboraymi? Guruhlarda aynan shunday ko'rinadi.",
        "ru": "📢 Отправить это сообщение в группы? Там оно будет выглядеть точно так же.",
        "en": "📢 Send this message to groups? It will look exactly like this there.",
    },
    "fwd_btn": {"uz": "📢 Guruhlarga yuborish", "ru": "📢 Отправить в группы", "en": "📢 Send to groups"},
    "fwd_saved_too": {
        "uz": "<i>{kind} Mini App'dagi biriktirmalarga ham saqlandi.</i>",
        "ru": "<i>{kind}: также сохранено во вложениях Mini App.</i>",
        "en": "<i>{kind} is also saved to the Mini App's attachments.</i>",
    },
    "media_photo": {"uz": "Rasm", "ru": "Фото", "en": "Photo"},
    "media_video": {"uz": "Video", "ru": "Видео", "en": "Video"},
    "media_voice": {"uz": "Ovozli xabar", "ru": "Голосовое", "en": "Voice message"},
    "media_audio": {"uz": "Audio", "ru": "Аудио", "en": "Audio"},
    "media_document": {"uz": "Fayl", "ru": "Файл", "en": "File"},
    "media_video_note": {"uz": "Video xabar", "ru": "Видеосообщение", "en": "Video message"},
    "media_animation": {"uz": "GIF", "ru": "GIF", "en": "GIF"},
    "webapp_text_empty": {
        "uz": "E'lon matni bo'sh.",
        "ru": "Текст объявления пуст.",
        "en": "The announcement text is empty.",
    },

    # ---------- Roles ----------
    "roles_empty": {
        "uz": "Hali rol yo'q. Qo'shish: <code>/addrole cleaner 🧹 Tozalovchi</code>",
        "ru": "Ролей пока нет. Добавить: <code>/addrole cleaner 🧹 Уборщица</code>",
        "en": "No roles yet. Add one: <code>/addrole cleaner 🧹 Cleaner</code>",
    },
    "roles_title": {"uz": "<b>Rollar:</b>", "ru": "<b>Роли:</b>", "en": "<b>Roles:</b>"},
    "staff_count": {"uz": "{n} xodim", "ru": "сотрудников: {n}", "en": "{n} staff"},
    "floor_based": {"uz": "🏢 qavat bo'yicha", "ru": "🏢 по этажам", "en": "🏢 by floor"},
    "usage_addrole": {
        "uz": "Foydalanish: <code>/addrole kalit [emoji] Nomi</code>\nMasalan: <code>/addrole cleaner 🧹 Tozalovchi</code>",
        "ru": "Использование: <code>/addrole ключ [эмодзи] Название</code>\nНапример: <code>/addrole cleaner 🧹 Уборщица</code>",
        "en": "Usage: <code>/addrole key [emoji] Name</code>\nExample: <code>/addrole cleaner 🧹 Cleaner</code>",
    },
    "bad_key": {
        "uz": "❌ «{word}» teg sifatida yaramaydi: harf bilan boshlanishi, 2–32 belgi (harf, raqam, _) bo'lishi va bot buyrug'i bilan bir xil bo'lmasligi kerak.",
        "ru": "❌ «{word}» не подходит как тег: должен начинаться с буквы, 2–32 символа (буквы, цифры, _) и не совпадать с командой бота.",
        "en": "❌ “{word}” can't be a tag: it must start with a letter, be 2–32 characters (letters, digits, _) and not match a bot command.",
    },
    "key_taken": {
        "uz": "❌ «{word}» tegi allaqachon band.",
        "ru": "❌ Тег «{word}» уже занят.",
        "en": "❌ The tag “{word}” is already taken.",
    },
    "role_added": {
        "uz": "✅ Rol qo'shildi: {title}\nChaqirish: <code>#{key}</code> yoki <code>/{key}</code>\n\nKeyingi qadam — xodim uchun havola: <code>/invite {key}</code>\nQavat bo'yicha ishlasa: <code>/rolefloor {key} on</code>",
        "ru": "✅ Роль добавлена: {title}\nВызов: <code>#{key}</code> или <code>/{key}</code>\n\nДалее — ссылка для сотрудника: <code>/invite {key}</code>\nЕсли работает по этажам: <code>/rolefloor {key} on</code>",
        "en": "✅ Role added: {title}\nCall with: <code>#{key}</code> or <code>/{key}</code>\n\nNext — an invite link for staff: <code>/invite {key}</code>\nIf it works by floor: <code>/rolefloor {key} on</code>",
    },
    "role_not_found": {
        "uz": "❌ Bunday rol topilmadi. Ro'yxat: /roles",
        "ru": "❌ Такая роль не найдена. Список: /roles",
        "en": "❌ Role not found. See /roles",
    },
    "role_deleted": {"uz": "🗑 Rol o'chirildi: {title}", "ru": "🗑 Роль удалена: {title}", "en": "🗑 Role deleted: {title}"},
    "usage_rolefloor": {
        "uz": "Foydalanish: <code>/rolefloor cleaner on</code> yoki <code>off</code>",
        "ru": "Использование: <code>/rolefloor cleaner on</code> или <code>off</code>",
        "en": "Usage: <code>/rolefloor cleaner on</code> or <code>off</code>",
    },
    "rolefloor_on": {
        "uz": "✅ {title}: chaqiruvlar sinf joylashgan qavatdagi xodimga boradi. Agar o'sha qavatda hech kim bo'lmasa — hammasiga.",
        "ru": "✅ {title}: вызовы идут сотруднику этажа, где находится класс. Если на этаже никого нет — всем.",
        "en": "✅ {title}: calls go to staff on the class's floor. If nobody covers that floor — to everyone.",
    },
    "rolefloor_off": {
        "uz": "✅ {title}: chaqiruvlar shu roldagi barcha xodimlarga boradi.",
        "ru": "✅ {title}: вызовы идут всем сотрудникам этой роли.",
        "en": "✅ {title}: calls go to all staff with this role.",
    },
    "usage_alias": {
        "uz": "Foydalanish: <code>/alias cleaner clean tozalash</code> yoki <code>/unalias cleaner clean</code>",
        "ru": "Использование: <code>/alias cleaner clean уборка</code> или <code>/unalias cleaner clean</code>",
        "en": "Usage: <code>/alias cleaner clean</code> or <code>/unalias cleaner clean</code>",
    },
    "alias_set": {
        "uz": "✅ {title} teglari: {triggers}",
        "ru": "✅ Теги {title}: {triggers}",
        "en": "✅ {title} tags: {triggers}",
    },

    # ---------- Floors ----------
    "floors_empty": {
        "uz": "Hali qavat yo'q. Qo'shish: <code>/addfloor 1-qavat</code>",
        "ru": "Этажей пока нет. Добавить: <code>/addfloor 1-этаж</code>",
        "en": "No floors yet. Add one: <code>/addfloor Floor 1</code>",
    },
    "floors_title": {"uz": "<b>Qavatlar:</b>", "ru": "<b>Этажи:</b>", "en": "<b>Floors:</b>"},
    "groups_without_floor": {
        "uz": "⚠️ Qavati belgilanmagan sinflar: {classes}",
        "ru": "⚠️ Классы без этажа: {classes}",
        "en": "⚠️ Classes without a floor: {classes}",
    },
    "usage_addfloor": {
        "uz": "Foydalanish: <code>/addfloor 2-qavat</code>",
        "ru": "Использование: <code>/addfloor 2-этаж</code>",
        "en": "Usage: <code>/addfloor Floor 2</code>",
    },
    "floor_exists": {"uz": "❌ «{name}» allaqachon bor.", "ru": "❌ «{name}» уже есть.", "en": "❌ “{name}” already exists."},
    "floor_added": {
        "uz": "✅ Qavat qo'shildi: {name}\nSinfni shu qavatga biriktirish uchun sinf guruhida yozing: <code>/setfloor {name}</code>",
        "ru": "✅ Этаж добавлен: {name}\nЧтобы привязать класс, напишите в группе класса: <code>/setfloor {name}</code>",
        "en": "✅ Floor added: {name}\nTo attach a class, write in its group: <code>/setfloor {name}</code>",
    },
    "floor_not_found": {
        "uz": "❌ Bunday qavat topilmadi. Ro'yxat: /floors",
        "ru": "❌ Такой этаж не найден. Список: /floors",
        "en": "❌ Floor not found. See /floors",
    },
    "floor_deleted": {"uz": "🗑 Qavat o'chirildi: {name}", "ru": "🗑 Этаж удалён: {name}", "en": "🗑 Floor deleted: {name}"},

    # ---------- Invites & staff ----------
    "usage_invite": {
        "uz": "Foydalanish: <code>/invite [teacher|announcer|admin|rol] [necha kishi] [qavat]</code>\nMasalan: <code>/invite teacher 60</code> yoki <code>/invite cleaner 1 2-qavat</code>",
        "ru": "Использование: <code>/invite [teacher|announcer|admin|роль] [сколько человек] [этаж]</code>\nНапример: <code>/invite teacher 60</code> или <code>/invite cleaner 1 2-этаж</code>",
        "en": "Usage: <code>/invite [teacher|announcer|admin|role] [uses] [floor]</code>\nExample: <code>/invite teacher 60</code> or <code>/invite cleaner 1 Floor 2</code>",
    },
    "invite_created": {
        "uz": "🔗 Taklif havolasi: {what}\nNecha kishi foydalana oladi: {uses}\n\n{link}\n\nHavolani faqat kerakli odamga yuboring. Bekor qilish: <code>/revoke {code}</code>",
        "ru": "🔗 Ссылка-приглашение: {what}\nСколько человек может использовать: {uses}\n\n{link}\n\nОтправьте ссылку только нужному человеку. Отменить: <code>/revoke {code}</code>",
        "en": "🔗 Invite link: {what}\nUses: {uses}\n\n{link}\n\nOnly send it to the right person. Revoke: <code>/revoke {code}</code>",
    },
    "invites_empty": {"uz": "Faol havolalar yo'q.", "ru": "Активных ссылок нет.", "en": "No active invite links."},
    "invites_title": {"uz": "<b>Faol havolalar:</b>", "ru": "<b>Активные ссылки:</b>", "en": "<b>Active invite links:</b>"},
    "uses_left": {"uz": "yana {n} marta", "ru": "осталось {n}", "en": "{n} uses left"},
    "invite_revoked": {"uz": "✅ Havola bekor qilindi.", "ru": "✅ Ссылка отменена.", "en": "✅ Invite link revoked."},
    "staff_title": {"uz": "<b>Xodimlar ({n}):</b>", "ru": "<b>Сотрудники ({n}):</b>", "en": "<b>Staff ({n}):</b>"},
    "staff_empty": {"uz": "Hech kim topilmadi.", "ru": "Никого не найдено.", "en": "Nobody found."},
    "usage_assign": {
        "uz": "Foydalanish: <code>/assign ID_yoki_@username rol [qavat]</code>\nRol: teacher, announcer, admin yoki /roles dagi kalit",
        "ru": "Использование: <code>/assign ID_или_@username роль [этаж]</code>\nРоль: teacher, announcer, admin или ключ из /roles",
        "en": "Usage: <code>/assign ID_or_@username role [floor]</code>\nRole: teacher, announcer, admin or a key from /roles",
    },
    "user_not_found": {
        "uz": "❌ Foydalanuvchi topilmadi. U avval botga /start yozishi kerak.",
        "ru": "❌ Пользователь не найден. Сначала он должен написать боту /start.",
        "en": "❌ User not found. They need to send /start to the bot first.",
    },
    "assigned": {"uz": "✅ {user}: {roles}", "ru": "✅ {user}: {roles}", "en": "✅ {user}: {roles}"},

    # ---------- Groups ----------
    "groups_empty": {
        "uz": "Hali birorta guruh ulanmagan. Botni sinf guruhiga qo'shing va admin qiling.",
        "ru": "Пока не подключено ни одной группы. Добавьте бота в группу класса и сделайте админом.",
        "en": "No groups connected yet. Add the bot to a class group and make it an admin.",
    },
    "groups_title": {"uz": "<b>Guruhlar ({n}):</b>", "ru": "<b>Группы ({n}):</b>", "en": "<b>Groups ({n}):</b>"},
    "no_floor": {"uz": "qavat yo'q", "ru": "без этажа", "en": "no floor"},
    "not_admin_warn": {"uz": "⚠️ bot admin emas", "ru": "⚠️ бот не админ", "en": "⚠️ bot is not admin"},
    "no_class_warn": {"uz": "⚠️ sinf belgilanmagan", "ru": "⚠️ класс не указан", "en": "⚠️ class not set"},
    "groups_hint": {
        "uz": "\nSinf/qavatni o'zgartirish uchun guruh ichida yozing: <code>/setclass 7-B</code>, <code>/setfloor 2-qavat</code>",
        "ru": "\nЧтобы изменить класс/этаж, напишите в группе: <code>/setclass 7-B</code>, <code>/setfloor 2-этаж</code>",
        "en": "\nTo change class/floor, write inside the group: <code>/setclass 7-B</code>, <code>/setfloor Floor 2</code>",
    },
    "only_admin_can_add": {
        "uz": "Bu botni faqat maktab adminlari qo'sha oladi. / Этого бота могут добавлять только администраторы школы.",
        "ru": "Bu botni faqat maktab adminlari qo'sha oladi. / Этого бота могут добавлять только администраторы школы.",
        "en": "Bu botni faqat maktab adminlari qo'sha oladi. / Only school admins can add this bot.",
    },
    "make_me_admin": {
        "uz": "👋 Salom! Ishlashim uchun meni guruh admini qiling (xabarlarni o'qish, o'chirish va pin qilish huquqi bilan).",
        "ru": "👋 Здравствуйте! Чтобы я работал, сделайте меня администратором группы (с правами читать, удалять и закреплять сообщения).",
        "en": "👋 Hi! Please make me a group admin (with rights to read, delete and pin messages) so I can work.",
    },
    "adm_group_added": {
        "uz": "➕ Bot guruhga qo'shildi: <b>{title}</b>\nAniqlangan sinf: {cls}\nGuruh ichida <code>/setfloor ...</code> bilan qavatini belgilang.",
        "ru": "➕ Бот добавлен в группу: <b>{title}</b>\nОпределён класс: {cls}\nУкажите этаж в группе командой <code>/setfloor ...</code>.",
        "en": "➕ Bot added to group: <b>{title}</b>\nDetected class: {cls}\nSet its floor inside the group with <code>/setfloor ...</code>.",
    },
    "adm_group_removed": {
        "uz": "➖ Bot guruhdan chiqarildi: <b>{title}</b>",
        "ru": "➖ Бот удалён из группы: <b>{title}</b>",
        "en": "➖ Bot removed from group: <b>{title}</b>",
    },
    "adm_group_not_admin": {
        "uz": "⚠️ Bot <b>{title}</b> guruhida admin emas — chaqiruvlarni ko'ra olmaydi.",
        "ru": "⚠️ Бот не админ в группе <b>{title}</b> — он не видит вызовы.",
        "en": "⚠️ The bot is not an admin in <b>{title}</b> — it can't see calls.",
    },
    "usage_setclass": {
        "uz": "Foydalanish: <code>/setclass 7-B</code>",
        "ru": "Использование: <code>/setclass 7-B</code>",
        "en": "Usage: <code>/setclass 7-B</code>",
    },
    "class_set": {"uz": "✅ Sinf: {cls}", "ru": "✅ Класс: {cls}", "en": "✅ Class: {cls}"},
    "floor_set": {"uz": "✅ {cls} — {floor}", "ru": "✅ {cls} — {floor}", "en": "✅ {cls} — {floor}"},
    "usage_grouplang": {
        "uz": "Foydalanish: <code>/grouplang uz</code> (uz, ru, en)",
        "ru": "Использование: <code>/grouplang ru</code> (uz, ru, en)",
        "en": "Usage: <code>/grouplang en</code> (uz, ru, en)",
    },
    "groupinfo": {
        "uz": "<b>{title}</b>\nSinf: {cls}\nQavat: {floor}\nTil: {lang}\nBot admin: {admin}\nID: <code>{id}</code>",
        "ru": "<b>{title}</b>\nКласс: {cls}\nЭтаж: {floor}\nЯзык: {lang}\nБот админ: {admin}\nID: <code>{id}</code>",
        "en": "<b>{title}</b>\nClass: {cls}\nFloor: {floor}\nLanguage: {lang}\nBot is admin: {admin}\nID: <code>{id}</code>",
    },

    # ---------- Group admins (/promote, /demote and the Mini App) ----------
    "gadm_usage": {
        "uz": "Odamning xabariga javob (reply) qilib yozing: /promote — guruh admini qilish, /demote — adminlikdan olish.",
        "ru": "Напишите ответом (reply) на сообщение человека: /promote — сделать админом группы, /demote — снять админа.",
        "en": "Write it as a reply to the person's message: /promote makes them a group admin, /demote removes them.",
    },
    "pick_person": {
        "uz": "Admin qilinadigan odamni tanlang",
        "ru": "Выберите, кого сделать админом",
        "en": "Choose who to make an admin",
    },
    "gadm_promoted": {
        "uz": "✅ {name} endi guruh admini: xabarlarni o'chira oladi, a'zolarni cheklay oladi, xabarni qadaydi va odam qo'sha oladi.",
        "ru": "✅ {name} теперь админ группы: может удалять сообщения, ограничивать участников, закреплять и приглашать.",
        "en": "✅ {name} is now a group admin: they can delete messages, restrict members, pin and invite people.",
    },
    "gadm_demoted": {
        "uz": "✅ {name} endi admin emas.",
        "ru": "✅ {name} больше не админ.",
        "en": "✅ {name} is no longer an admin.",
    },
    "gadm_already_admin": {
        "uz": "{name} allaqachon admin.",
        "ru": "{name} уже админ.",
        "en": "{name} is already an admin.",
    },
    "gadm_not_admin": {
        "uz": "{name} admin emas edi.",
        "ru": "{name} и так не админ.",
        "en": "{name} wasn't an admin.",
    },
    "gadm_owner": {
        "uz": "{name} — guruh egasi, uning huquqlarini o'zgartirib bo'lmaydi.",
        "ru": "{name} — владелец группы, его права изменить нельзя.",
        "en": "{name} owns the group; their rights can't be changed.",
    },
    "gadm_not_member": {
        "uz": "{name} bu guruhda yo'q. Avval uni guruhga qo'shing.",
        "ru": "{name} нет в этой группе. Сначала добавьте его в группу.",
        "en": "{name} isn't in this group. Add them to the group first.",
    },
    "gadm_not_ours": {
        "uz": "{name}ni bot emas, boshqa admin tayinlagan. Telegram uni faqat o'sha admin yoki guruh egasiga olib tashlashga ruxsat beradi.",
        "ru": "{name} назначен не ботом, а другим админом. Telegram разрешает снять его только тому админу или владельцу группы.",
        "en": "{name} was made an admin by someone else, not the bot. Telegram lets only that admin or the group owner remove them.",
    },
    "gadm_no_right": {
        "uz": "Menda bu guruhda «Yangi admin qo'shish» huquqi yo'q. Guruh sozlamalarida menga shu huquqni bering.",
        "ru": "У меня нет права «Добавление администраторов» в этой группе. Дайте мне его в настройках группы.",
        "en": "I don't have the \"Add new admins\" right in this group. Give it to me in the group settings.",
    },
    "gadm_basic_group": {
        "uz": "Bu eski turdagi guruh: Telegram bunday guruhda bot orqali admin tayinlashga ruxsat bermaydi.",
        "ru": "Это группа старого типа: в ней Telegram не разрешает ботам назначать админов.",
        "en": "This is an old-style group: Telegram doesn't let bots appoint admins there.",
    },
    "gadm_joined": {
        "uz": "✅ {name} taklif havolasi orqali «{group}» guruhiga kirdi va admin qilindi.",
        "ru": "✅ {name} вступил(а) в группу «{group}» по ссылке-приглашению и стал(а) админом.",
        "en": "✅ {name} joined «{group}» through the invite link and is now an admin.",
    },
    "gadm_joined_failed": {
        "uz": "⚠️ {name} taklif havolasi orqali «{group}» guruhiga kirdi, lekin admin qilinmadi.\n{reason}",
        "ru": "⚠️ {name} вступил(а) в группу «{group}» по ссылке-приглашению, но админом не стал(а).\n{reason}",
        "en": "⚠️ {name} joined «{group}» through the invite link but wasn't made an admin.\n{reason}",
    },
    "gadm_wrong_person": {
        "uz": "⚠️ «{group}» guruhiga {name} uchun berilgan havola orqali boshqa odam kirdi: {who}. U admin qilinmadi.",
        "ru": "⚠️ По ссылке в группу «{group}», выданной для {name}, вступил другой человек: {who}. Админом он не стал.",
        "en": "⚠️ Someone else joined «{group}» through the link made for {name}: {who}. They weren't made an admin.",
    },
    "gadm_invite_failed": {
        "uz": "Taklif havolasini yaratib bo'lmadi: botga bu guruhda «Foydalanuvchilarni taklif qilish» huquqini bering.",
        "ru": "Не удалось создать ссылку-приглашение: дайте боту в этой группе право «Приглашение пользователей».",
        "en": "Couldn't create an invite link: give the bot the \"Invite users\" right in this group.",
    },
    "gadm_error": {
        "uz": "Telegram rad etdi. Birozdan keyin qayta urinib ko'ring.",
        "ru": "Telegram отказал. Попробуйте чуть позже.",
        "en": "Telegram refused. Please try again a bit later.",
    },

    # ---------- Calls ----------
    "only_teachers": {
        "uz": "Xodimlarni faqat ro'yxatdan o'tgan o'qituvchilar chaqira oladi.",
        "ru": "Вызывать сотрудников могут только зарегистрированные учителя.",
        "en": "Only registered teachers can call staff.",
    },
    "card_urgent": {"uz": "🚨 <b>SHOSHILINCH!</b>", "ru": "🚨 <b>СРОЧНО!</b>", "en": "🚨 <b>URGENT!</b>"},
    "card_title": {
        "uz": "{role} — <b>chaqiruv #{id}</b>",
        "ru": "{role} — <b>вызов #{id}</b>",
        "en": "{role} — <b>call #{id}</b>",
    },
    "card_class": {"uz": "🏫 Sinf: <b>{cls}</b>", "ru": "🏫 Класс: <b>{cls}</b>", "en": "🏫 Class: <b>{cls}</b>"},
    "card_from": {"uz": "👤 Kimdan: {name}", "ru": "👤 От кого: {name}", "en": "👤 From: {name}"},
    "card_time": {"uz": "🕐 Vaqt: {time}", "ru": "🕐 Время: {time}", "en": "🕐 Time: {time}"},
    "card_open": {"uz": "Guruhdagi xabarni ochish", "ru": "Открыть сообщение в группе", "en": "Open the message in the group"},
    "st_pending": {
        "uz": "⏳ Kutilmoqda — borsangiz «Qabul qilaman» ni bosing.",
        "ru": "⏳ Ожидает — если идёте, нажмите «Принимаю».",
        "en": "⏳ Waiting — tap “I'll take it” if you're going.",
    },
    "st_pending_escalated": {
        "uz": "⚠️ Hali hech kim qabul qilmadi!",
        "ru": "⚠️ Пока никто не принял!",
        "en": "⚠️ Nobody has taken this yet!",
    },
    "st_accepted_you": {
        "uz": "✅ Siz qabul qildingiz ({time}). Ish tugagach «Bajarildi» ni bosing.",
        "ru": "✅ Вы приняли ({time}). Когда закончите, нажмите «Выполнено».",
        "en": "✅ You took it ({time}). Tap “Done” when finished.",
    },
    "st_accepted": {
        "uz": "✅ {name} qabul qildi ({time})",
        "ru": "✅ Принял(а): {name} ({time})",
        "en": "✅ Taken by {name} ({time})",
    },
    "st_done": {
        "uz": "✔️ Bajarildi — {name} ({time})",
        "ru": "✔️ Выполнено — {name} ({time})",
        "en": "✔️ Done — {name} ({time})",
    },
    "st_closed": {"uz": "✖️ Chaqiruv yopildi", "ru": "✖️ Вызов закрыт", "en": "✖️ Call closed"},
    "btn_accept": {"uz": "✅ Qabul qilaman", "ru": "✅ Принимаю", "en": "✅ I'll take it"},
    "btn_done": {"uz": "✔️ Bajarildi", "ru": "✔️ Выполнено", "en": "✔️ Done"},
    "btn_close": {"uz": "✖️ Yopish", "ru": "✖️ Закрыть", "en": "✖️ Close"},
    "grp_pending": {
        "uz": "{role} chaqirildi. ⏳ Kutilmoqda…",
        "ru": "{role} вызван(а). ⏳ Ожидаем…",
        "en": "{role} has been called. ⏳ Waiting…",
    },
    "grp_accepted": {
        "uz": "{role}: ✅ {name} qabul qildi, yo'lda.",
        "ru": "{role}: ✅ {name} принял(а) вызов, уже идёт.",
        "en": "{role}: ✅ {name} is on the way.",
    },
    "grp_done": {
        "uz": "{role}: ✔️ {name} — bajarildi.",
        "ru": "{role}: ✔️ {name} — выполнено.",
        "en": "{role}: ✔️ {name} — done.",
    },
    "grp_closed": {
        "uz": "{role}: ✖️ chaqiruv yopildi.",
        "ru": "{role}: ✖️ вызов закрыт.",
        "en": "{role}: ✖️ call closed.",
    },
    "grp_nostaff": {
        "uz": "{role} uchun xodim biriktirilmagan. Ma'muriyatga xabar berildi.",
        "ru": "Для роли {role} нет сотрудников. Администрация уведомлена.",
        "en": "No staff assigned for {role}. The administration has been notified.",
    },
    "esc_nostaff": {
        "uz": "⚠️ Bu chaqiruvni oladigan xodim yo'q (rolga hech kim biriktirilmagan yoki botni ishga tushirmagan):",
        "ru": "⚠️ Этот вызов некому принять (у роли нет сотрудников или они не запустили бота):",
        "en": "⚠️ Nobody can receive this call (no staff in this role, or they haven't started the bot):",
    },
    "esc_timeout": {
        "uz": "⚠️ {minutes} daqiqa o'tdi, bu chaqiruvni hech kim qabul qilmadi:",
        "ru": "⚠️ Прошло {minutes} мин., этот вызов никто не принял:",
        "en": "⚠️ {minutes} minutes passed and nobody has taken this call:",
    },
    "not_yours": {
        "uz": "Bu chaqiruv sizga yuborilmagan.",
        "ru": "Этот вызов отправлен не вам.",
        "en": "This call wasn't sent to you.",
    },
    "accepted_ok": {"uz": "Qabul qildingiz ✅", "ru": "Вы приняли ✅", "en": "You took it ✅"},
    "already_taken": {
        "uz": "Bu chaqiruvni boshqa xodim allaqachon qabul qilgan.",
        "ru": "Этот вызов уже принял другой сотрудник.",
        "en": "Someone else has already taken this call.",
    },
    "done_ok": {"uz": "Rahmat! ✔️", "ru": "Спасибо! ✔️", "en": "Thank you! ✔️"},
    "closed_ok": {"uz": "Chaqiruv yopildi.", "ru": "Вызов закрыт.", "en": "Call closed."},

    # ---------- Announcements ----------
    "ann_send_content": {
        "uz": (
            "📢 Tayyor e'lonni yuboring yoki forward qiling: matn, rasm, albom, video, fayl yoki ovozli xabar. "
            "Guruhlarga aynan shunday boradi.\n\n"
            "💡 Buyruqsiz ham bo'ladi: istalgan xabarni menga yuborsangiz, guruhlarga yuborishni taklif qilaman.\n"
            "Bekor qilish: /cancel"
        ),
        "ru": (
            "📢 Отправьте или перешлите готовое объявление: текст, фото, альбом, видео, файл или голосовое. "
            "В группы оно уйдёт точно таким же.\n\n"
            "💡 Можно и без команды: пришлите мне любое сообщение, и я предложу отправить его в группы.\n"
            "Отмена: /cancel"
        ),
        "en": (
            "📢 Send or forward the finished announcement: text, photo, album, video, file or voice message. "
            "Groups get it exactly as it is.\n\n"
            "💡 No command needed: send me any message and I'll offer to send it to groups.\n"
            "Cancel: /cancel"
        ),
    },
    "ann_choose": {
        "uz": "Qaysi guruhlarga yuborilsin? Tanlangan: <b>{n}</b>",
        "ru": "В какие группы отправить? Выбрано: <b>{n}</b>",
        "en": "Which groups should get it? Selected: <b>{n}</b>",
    },
    "ann_all": {"uz": "🏫 Hammasi ({n})", "ru": "🏫 Все ({n})", "en": "🏫 All ({n})"},
    "ann_grade": {"uz": "{grade}-sinflar", "ru": "{grade}-е классы", "en": "Grade {grade}"},
    "ann_pin_on": {"uz": "📌 Pin qilish: ✅ ha", "ru": "📌 Закрепить: ✅ да", "en": "📌 Pin: ✅ yes"},
    "ann_pin_off": {"uz": "📌 Pin qilish: yo'q", "ru": "📌 Закрепить: нет", "en": "📌 Pin: no"},
    "ann_send": {"uz": "📤 Yuborish ({n})", "ru": "📤 Отправить ({n})", "en": "📤 Send ({n})"},
    "ann_cancel": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена", "en": "❌ Cancel"},
    "ann_nothing_selected": {
        "uz": "Avval kamida bitta guruhni tanlang.",
        "ru": "Сначала выберите хотя бы одну группу.",
        "en": "Select at least one group first.",
    },
    "ann_sending": {
        "uz": "⏳ {n} ta guruhga yuborilmoqda…",
        "ru": "⏳ Отправляю в {n} групп…",
        "en": "⏳ Sending to {n} groups…",
    },
    "ann_report": {
        "uz": "✅ E'lon yuborildi: {sent}/{total}",
        "ru": "✅ Объявление отправлено: {sent}/{total}",
        "en": "✅ Announcement sent: {sent}/{total}",
    },
    "ann_failed": {
        "uz": "❌ Yuborilmadi: {names}",
        "ru": "❌ Не отправлено: {names}",
        "en": "❌ Failed: {names}",
    },
    "ann_pin_failed": {
        "uz": "📌 Pin qilinmadi (botda huquq yo'q): {names}",
        "ru": "📌 Не закреплено (нет прав у бота): {names}",
        "en": "📌 Not pinned (bot lacks rights): {names}",
    },
    "ann_forwarded": {
        "uz": "↪️ Telegram bu xabarni nusxalashga ruxsat bermadi, shuning uchun forward qilib yuborildi.",
        "ru": "↪️ Telegram не разрешил скопировать это сообщение, поэтому оно переслано.",
        "en": "↪️ Telegram wouldn't copy this message, so it was forwarded instead.",
    },
    # ---------- Stories on the school account ----------
    "story_connected": {
        "uz": (
            "🔗 <b>{name}</b> akkaunti botni ulab qo'ydi.\n{right}\n\n"
            "Bu maktab akkauntimi? Tasdiqlasangiz, rasmli e'lonlarni shu akkauntga story qilib qo'yish mumkin bo'ladi."
        ),
        "ru": (
            "🔗 Аккаунт <b>{name}</b> подключил бота.\n{right}\n\n"
            "Это аккаунт школы? Если подтвердите, объявления с фото можно будет публиковать в нём как истории."
        ),
        "en": (
            "🔗 The account <b>{name}</b> connected the bot.\n{right}\n\n"
            "Is this the school's account? Once you confirm, photo announcements can be posted there as stories."
        ),
    },
    "story_status": {"uz": "🔗 <b>{name}</b>\n{right}", "ru": "🔗 <b>{name}</b>\n{right}", "en": "🔗 <b>{name}</b>\n{right}"},
    "story_right_yes": {
        "uz": "✅ Story qo'yish ruxsati bor.",
        "ru": "✅ Разрешение на истории есть.",
        "en": "✅ The bot may post stories.",
    },
    "story_right_no": {
        "uz": (
            "⚠️ Story qo'yish ruxsati berilmagan. Shu akkauntda: Settings → Telegram Business → Chatbots → "
            "@{bot} → «Manage stories» ni yoqing."
        ),
        "ru": (
            "⚠️ Нет разрешения на истории. В этом аккаунте: Настройки → Telegram для бизнеса → Чат-боты → "
            "@{bot} → включите «Управление историями»."
        ),
        "en": (
            "⚠️ The bot may not post stories. On that account: Settings → Telegram Business → Chatbots → "
            "@{bot} → turn on “Manage stories”."
        ),
    },
    "story_acc_yes": {"uz": "✅ Ha, maktab akkaunti", "ru": "✅ Да, аккаунт школы", "en": "✅ Yes, the school's"},
    "story_acc_no": {"uz": "❌ Yo'q", "ru": "❌ Нет", "en": "❌ No"},
    "story_approved": {
        "uz": "✅ <b>{name}</b> — maktab akkaunti. Rasmli e'lon yuborilgach, ostida «📲 Story qilib qo'yish» tugmasi chiqadi.",
        "ru": "✅ <b>{name}</b> — аккаунт школы. После отправки объявления с фото под ним появится «📲 В истории».",
        "en": "✅ <b>{name}</b> is the school's account. After a photo announcement is sent, “📲 Post as a story” appears under it.",
    },
    "story_rejected": {
        "uz": "❌ <b>{name}</b> ishlatilmaydi.",
        "ru": "❌ <b>{name}</b> не используется.",
        "en": "❌ <b>{name}</b> won't be used.",
    },
    "story_disconnected": {
        "uz": "🔌 <b>{name}</b> akkaunti botni uzdi. E'lonlarni story qilib qo'yib bo'lmaydi.",
        "ru": "🔌 Аккаунт <b>{name}</b> отключил бота. Публиковать истории нельзя.",
        "en": "🔌 <b>{name}</b> disconnected the bot. Stories can't be posted.",
    },
    "story_btn": {"uz": "📲 Story qilib qo'yish", "ru": "📲 В истории", "en": "📲 Post as a story"},
    "story_hours": {"uz": "{h} soat", "ru": "{h} ч", "en": "{h} h"},
    "story_posting": {"uz": "⏳ Story tayyorlanmoqda…", "ru": "⏳ Готовлю историю…", "en": "⏳ Preparing the story…"},
    "story_done": {
        "uz": "📲 Story qo'yildi: {name}, {h} soat.",
        "ru": "📲 История опубликована: {name}, {h} ч.",
        "en": "📲 Story posted: {name}, {h} h.",
    },
    "story_failed": {
        "uz": "❌ Story qo'yilmadi: {error}",
        "ru": "❌ История не опубликована: {error}",
        "en": "❌ The story wasn't posted: {error}",
    },
    "story_unavailable": {
        "uz": "Story uchun maktab akkaunti ulanmagan yoki e'londa rasm yo'q.",
        "ru": "Аккаунт школы для историй не подключён, или в объявлении нет фото.",
        "en": "No school account is connected for stories, or the announcement has no photo.",
    },
    "ann_delete_all": {
        "uz": "🗑 Hamma guruhlardan o'chirish",
        "ru": "🗑 Удалить из всех групп",
        "en": "🗑 Delete from all groups",
    },
    "ann_already_deleted": {
        "uz": "Bu e'lon allaqachon o'chirilgan.",
        "ru": "Это объявление уже удалено.",
        "en": "This announcement was already deleted.",
    },
    "ann_deleted": {
        "uz": "🗑 E'lon o'chirildi: {n}/{total}",
        "ru": "🗑 Объявление удалено: {n}/{total}",
        "en": "🗑 Announcement deleted: {n}/{total}",
    },

    # ---------- Stats ----------
    "stats_empty": {
        "uz": "Oxirgi {days} kunda chaqiruv bo'lmagan.",
        "ru": "За последние {days} дн. вызовов не было.",
        "en": "No calls in the last {days} days.",
    },
    "stats_title": {
        "uz": "<b>📊 Oxirgi {days} kun: {n} ta chaqiruv</b>",
        "ru": "<b>📊 За {days} дн.: {n} вызовов</b>",
        "en": "<b>📊 Last {days} days: {n} calls</b>",
    },
    "stats_role": {
        "uz": "{title}: {n} ta · qabul qilingan {accepted} · o'rtacha javob {avg} daq · kechikkan {escalated}",
        "ru": "{title}: {n} · принято {accepted} · среднее время ответа {avg} мин · просрочено {escalated}",
        "en": "{title}: {n} · taken {accepted} · avg response {avg} min · overdue {escalated}",
    },
    "stats_top": {
        "uz": "\n<b>Eng ko'p chaqirgan sinflar:</b>",
        "ru": "\n<b>Классы с наибольшим числом вызовов:</b>",
        "en": "\n<b>Classes with the most calls:</b>",
    },
}


def t(lang: str, key: str, /, **kwargs) -> str:
    variants = TEXTS[key]
    text = variants.get(lang) or variants["uz"]
    return text.format(**kwargs) if kwargs else text
