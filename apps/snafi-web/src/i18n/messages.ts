export type Lang = "en" | "ar";
export const LANGS: readonly Lang[] = ["en", "ar"] as const;

const en = {
  appName: "Snafi",
  greeting: { morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening", night: "Good night" },
  ownerName: "Khalid",
  placeholder: "Sample",
  placeholderNote: "Sample content. Real data arrives in later steps.",
  previewBanner: "Preview mode: Supabase is not configured, so sign-in is skipped on this PC. See the README.",
  previewOpen: "Open preview",
  nextPrayer: "Next prayer",
  prayers: { fajr: "Fajr", dhuhr: "Dhuhr", asr: "Asr", maghrib: "Maghrib", isha: "Isha" },
  prayerRingLabel: (name: string, time: string, pct: number) => `Next prayer ${name} at ${time}, ${pct}% of the wait has passed`,
  nextEvent: "Next event",
  topTasks: "Top tasks",
  ahmadCards: "From Ahmad",
  approvals: "Waiting for your approval",
  approve: "Approve",
  reject: "Reject",
  approvalsEmpty: "Nothing is waiting for your approval.",
  cardStatus: { pending: "Waiting for you", approved: "Approved, running…", executing: "Running… (if this stays, it may not have finished; it will not run again)", rejected: "Rejected", executed: "Done", failed: "Failed", expired: "Expired" },
  decideFailed: "That didn't go through. Try again.",
  exactly: "Exactly what will run",
  expires: (time: string) => `Expires ${time} if not decided`,
  undo: "Undo",
  undoing: "Undoing…",
  undone: "Undone",
  thinking: "Ahmad is thinking…",
  pcOnline: "PC online",
  pcOffline: "PC offline. Your messages wait in the queue, and Ahmad answers when the PC is back.",
  lastBackup: (when: string, ok: boolean) => (ok ? `Last backup ${when} ✓` : `Last backup failed (${when})`),
  noBackup: "No backup yet",
  openChat: "Talk to Ahmad",
  chatTitle: "Ahmad",
  chatSubtitle: "Your executive assistant",
  back: "Back to Today",
  messagePlaceholder: "Message Ahmad…",
  send: "Send",
  attach: "Attach a file",
  chatPreview: "Preview mode: messages stay on this PC and the worker does not see them.",
  sendFailed: "Couldn't send. Try again.",
  menu: "Menu",
  closeMenu: "Close menu",
  theme: "Appearance",
  dark: "Dark",
  light: "Light",
  language: "Language",
  signOut: "Sign out",
  signIn: {
    title: "Welcome back",
    subtitle: "Sign in to Snafi",
    email: "Email",
    password: "Password",
    submit: "Sign in",
    submitting: "Signing in…",
    invalid: "Email or password is incorrect.",
    missing: "Enter your email and password.",
    unavailable: "Sign-in is not available right now. Try again shortly.",
    notConfigured: "Supabase is not configured on this server yet. Add the keys to .env.local (see the README).",
    inviteOnly: "Snafi is invite only.",
    insecure: "Sign-in is off on this connection: it is plain HTTP, so your password could be read on the network. Sign in on this PC (localhost) or over HTTPS.",
  },
  loading: "Loading",
} as const;

type Messages = {
  [K in keyof typeof en]: (typeof en)[K] extends (...args: infer A) => string
    ? (...args: A) => string
    : (typeof en)[K] extends string
      ? string
      : { [P in keyof (typeof en)[K]]: string };
};

const ar: Messages = {
  appName: "سنافي",
  greeting: { morning: "صباح الخير", afternoon: "مساء الخير", evening: "مساء الخير", night: "تصبح على خير" },
  ownerName: "خالد",
  placeholder: "نموذج",
  placeholderNote: "محتوى تجريبي. البيانات الحقيقية تأتي في المراحل القادمة.",
  previewBanner: "وضع المعاينة: Supabase غير مُعدّ، لذلك يُتخطّى تسجيل الدخول على هذا الجهاز. راجع ملف README.",
  previewOpen: "فتح المعاينة",
  nextPrayer: "الصلاة القادمة",
  prayers: { fajr: "الفجر", dhuhr: "الظهر", asr: "العصر", maghrib: "المغرب", isha: "العشاء" },
  prayerRingLabel: (name: string, time: string, pct: number) => `الصلاة القادمة ${name} الساعة ${time}، مضى ${pct}٪ من الانتظار`,
  nextEvent: "الموعد القادم",
  topTasks: "أهم المهام",
  ahmadCards: "من أحمد",
  approvals: "بانتظار موافقتك",
  approve: "موافقة",
  reject: "رفض",
  approvalsEmpty: "لا يوجد ما ينتظر موافقتك.",
  cardStatus: { pending: "بانتظارك", approved: "تمت الموافقة، جارٍ التنفيذ…", executing: "جارٍ التنفيذ… (إن بقي هكذا فربما لم يكتمل، ولن يُعاد تنفيذه)", rejected: "مرفوض", executed: "نُفّذ", failed: "لم ينجح", expired: "انتهت صلاحيته" },
  decideFailed: "لم يتم ذلك. حاول مرة أخرى.",
  exactly: "ما سيُنفَّذ بالضبط",
  expires: (time: string) => `تنتهي صلاحيته ${time} إن لم يُبتّ فيه`,
  undo: "تراجع",
  undoing: "جارٍ التراجع…",
  undone: "تم التراجع",
  thinking: "أحمد يفكّر…",
  pcOnline: "الجهاز متصل",
  pcOffline: "الجهاز غير متصل. رسائلك محفوظة في قائمة الانتظار، وسيرد أحمد عند عودة الجهاز.",
  lastBackup: (when: string, ok: boolean) => (ok ? `آخر نسخة احتياطية ${when} ✓` : `فشلت آخر نسخة احتياطية (${when})`),
  noBackup: "لا توجد نسخة احتياطية بعد",
  openChat: "تحدّث مع أحمد",
  chatTitle: "أحمد",
  chatSubtitle: "مساعدك التنفيذي",
  back: "العودة إلى اليوم",
  messagePlaceholder: "اكتب رسالة لأحمد…",
  send: "إرسال",
  attach: "إرفاق ملف",
  chatPreview: "وضع المعاينة: تبقى الرسائل على هذا الجهاز ولا يراها العامل.",
  sendFailed: "تعذّر الإرسال. حاول مرة أخرى.",
  menu: "القائمة",
  closeMenu: "إغلاق القائمة",
  theme: "المظهر",
  dark: "داكن",
  light: "فاتح",
  language: "اللغة",
  signOut: "تسجيل الخروج",
  signIn: {
    title: "أهلاً بعودتك",
    subtitle: "سجّل الدخول إلى سنافي",
    email: "البريد الإلكتروني",
    password: "كلمة المرور",
    submit: "تسجيل الدخول",
    submitting: "جارٍ تسجيل الدخول…",
    invalid: "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    missing: "أدخل البريد الإلكتروني وكلمة المرور.",
    unavailable: "تسجيل الدخول غير متاح الآن. حاول بعد قليل.",
    notConfigured: "لم يُعدّ Supabase على هذا الخادم بعد. أضف المفاتيح إلى ‎.env.local (راجع README).",
    inviteOnly: "سنافي بالدعوة فقط.",
    insecure: "تسجيل الدخول متوقف على هذا الاتصال: هو HTTP غير مشفّر، فقد تُقرأ كلمة المرور على الشبكة. سجّل الدخول من هذا الجهاز (localhost) أو عبر HTTPS.",
  },
  loading: "جارٍ التحميل",
};

const DICTS: Record<Lang, Messages> = { en, ar };

export function messages(lang: Lang): Messages {
  return DICTS[lang];
}

export function isLang(value: unknown): value is Lang {
  return value === "en" || value === "ar";
}

export function direction(lang: Lang): "ltr" | "rtl" {
  return lang === "ar" ? "rtl" : "ltr";
}

export type { Messages };
