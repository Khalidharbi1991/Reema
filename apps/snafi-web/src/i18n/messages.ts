export type Lang = "en" | "ar";
export const LANGS: readonly Lang[] = ["en", "ar"] as const;

const en = {
  appName: "Snafi",
  greeting: { morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening", night: "Good night" },
  ownerName: "Khalid",
  placeholder: "Sample",
  placeholderNote: "Sample content. Real data arrives in later steps.",
  previewBanner: "Preview mode: Supabase is not configured, so sign-in is skipped on this PC. See the README.",
  nextPrayer: "Next prayer",
  prayers: { fajr: "Fajr", dhuhr: "Dhuhr", asr: "Asr", maghrib: "Maghrib", isha: "Isha" },
  prayerRingLabel: (name: string, time: string, pct: number) => `Next prayer ${name} at ${time}, ${pct}% of the wait has passed`,
  nextEvent: "Next event",
  topTasks: "Top tasks",
  ahmadCards: "From Ahmad",
  approvals: "Waiting for your approval",
  approve: "Approve",
  reject: "Reject",
  approvalsDisabled: "Approvals start working in step 2.",
  openChat: "Talk to Ahmad",
  chatTitle: "Ahmad",
  chatSubtitle: "Your executive assistant",
  back: "Back to Today",
  messagePlaceholder: "Message Ahmad…",
  send: "Send",
  attach: "Attach a file",
  chatDisabled: "Ahmad starts replying in step 2. Messages are not sent yet.",
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
  nextPrayer: "الصلاة القادمة",
  prayers: { fajr: "الفجر", dhuhr: "الظهر", asr: "العصر", maghrib: "المغرب", isha: "العشاء" },
  prayerRingLabel: (name: string, time: string, pct: number) => `الصلاة القادمة ${name} الساعة ${time}، مضى ${pct}٪ من الانتظار`,
  nextEvent: "الموعد القادم",
  topTasks: "أهم المهام",
  ahmadCards: "من أحمد",
  approvals: "بانتظار موافقتك",
  approve: "موافقة",
  reject: "رفض",
  approvalsDisabled: "تعمل الموافقات ابتداءً من المرحلة الثانية.",
  openChat: "تحدّث مع أحمد",
  chatTitle: "أحمد",
  chatSubtitle: "مساعدك التنفيذي",
  back: "العودة إلى اليوم",
  messagePlaceholder: "اكتب رسالة لأحمد…",
  send: "إرسال",
  attach: "إرفاق ملف",
  chatDisabled: "يبدأ أحمد بالرد في المرحلة الثانية. الرسائل لا تُرسل بعد.",
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
