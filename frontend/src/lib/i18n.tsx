import { createContext, useContext, useState, type ReactNode } from "react";

// Staff-facing labels in English and Amharic. Guest invoices stay in English.
const AM: Record<string, string> = {
  Dashboard: "ዳሽቦርድ",
  "Front desk": "እንግዳ መቀበያ",
  Reservations: "ቦታ ማስያዝ",
  Rooms: "ክፍሎች",
  Housekeeping: "የክፍል ጽዳት",
  Billing: "ሂሳብ",
  POS: "ሽያጭ",
  Kitchen: "ማብሰያ ቤት",
  Laundry: "ላውንድሪ",
  Inventory: "ንብረት ክምችት",
  Reports: "ሪፖርቶች",
  Settings: "ቅንብሮች",
  "Log out": "ውጣ",
  Arrivals: "የሚመጡ",
  Departures: "የሚወጡ",
  "In house": "በሆቴል ያሉ",
  "Check in": "አስገባ",
  "Check out": "አስወጣ",
  Save: "አስቀምጥ",
  Cancel: "ሰርዝ",
  Search: "ፈልግ",
  "New reservation": "አዲስ ቦታ ማስያዝ",
  Guest: "እንግዳ",
  Room: "ክፍል",
  Total: "ጠቅላላ",
  Balance: "ቀሪ ሂሳብ",
  Pay: "ክፈል",
  "Post to room": "ወደ ክፍል ሂሳብ",
  "Send to kitchen": "ወደ ማብሰያ ቤት ላክ",
  Clean: "ንጹህ",
  Dirty: "የቆሸሸ",
  Inspected: "የተፈተሸ",
  Occupied: "የተያዘ",
  Vacant: "ባዶ",
  "Out of order": "ከአገልግሎት ውጭ",
  Start: "ጀምር",
  Done: "ተጠናቋል",
  Offline: "ከመስመር ውጭ",
  Online: "መስመር ላይ",
  "Business date": "የሥራ ቀን",
};

type Lang = "en" | "am";
const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (s: string) => string }>({
  lang: "en",
  setLang: () => {},
  t: (s) => s,
});

export function I18nProvider({ children, initial }: { children: ReactNode; initial: Lang }) {
  const [lang, setLang] = useState<Lang>(initial);
  const t = (s: string) => (lang === "am" ? AM[s] ?? s : s);
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
