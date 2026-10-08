import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import es from "./es.json";

// App UI only — generated documents (contracts, change orders, PDFs) stay
// English regardless of this setting, since they fill a fixed CSLB-template
// AcroForm whose text must stay verbatim (see CLAUDE.md). Backend-authored
// error messages (HTTPException details) aren't translated either; only
// strings this app itself renders are.
const STORAGE_KEY = "cabrera-language";

export type AppLanguage = "en" | "es";

function initialLanguage(): AppLanguage {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "es") return saved;
  } catch {
    // localStorage unavailable (private browsing, etc.) — fall through to default
  }
  return "en";
}

i18next.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es } },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setAppLanguage(lang: AppLanguage) {
  i18next.changeLanguage(lang);
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // ignore — language just won't persist across reloads
  }
}

export default i18next;
