import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApprovalButtons } from "@/components/ApprovalButtons";
import { Menu } from "@/components/Menu";
import { PrayerRing } from "@/components/PrayerRing";
import { ChatView } from "@/app/(app)/chat/ChatView";
import { TodayView } from "@/app/(app)/today/TodayView";
import { PlaceholderTodaySource } from "@/adapters/today/placeholder";
import { messages } from "@/i18n/messages";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

const labels = (lang: "en" | "ar") => {
  const t = messages(lang);
  return { menu: t.menu, closeMenu: t.closeMenu, theme: t.theme, dark: t.dark, light: t.light, language: t.language, signOut: t.signOut };
};

async function today(lang: "en" | "ar") {
  return new PlaceholderTodaySource().getToday(lang, new Date("2026-11-07T15:00:00Z"));
}

describe("Today screen", () => {
  it("shows the greeting, prayer ring, sample badges and the orb link (English)", async () => {
    render(<TodayView lang="en" hour={19} today={await today("en")} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Good evening, Khalid");
    expect(screen.getByRole("img", { name: /Next prayer Asr at 15:12, 62%/ })).toBeInTheDocument();
    expect(screen.getAllByText("Sample").length).toBeGreaterThanOrEqual(4);
    expect(screen.getByRole("link", { name: "Talk to Ahmad" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("renders in Arabic", async () => {
    render(<TodayView lang="ar" hour={8} today={await today("ar")} />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("صباح الخير، خالد");
    expect(screen.getByRole("link", { name: "تحدّث مع أحمد" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "موافقة" })).toBeInTheDocument();
  });
});

describe("approvals", () => {
  it("are buttons that do nothing yet but say so", () => {
    const vibrate = vi.fn(() => true);
    vi.stubGlobal("navigator", { ...navigator, vibrate });
    render(<ApprovalButtons approve="Approve" reject="Reject" disabledNote="Approvals start working in step 2." />);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByRole("status")).toHaveTextContent("step 2");
    expect(vibrate).toHaveBeenCalledWith(12);
    vi.unstubAllGlobals();
    vi.stubGlobal("fetch", () => { throw new Error("Network access is forbidden in Snafi tests"); });
  });
});

describe("prayer ring", () => {
  it("clamps progress and fills the ring", () => {
    const { rerender } = render(<PrayerRing name="Asr" time="15:12" progress={0.5} label="l" size={100} />);
    const ring = screen.getByTestId("prayer-progress");
    const c = Number(ring.getAttribute("stroke-dasharray"));
    expect(Number(ring.getAttribute("stroke-dashoffset"))).toBeCloseTo(c / 2);
    rerender(<PrayerRing name="Asr" time="15:12" progress={7} label="l" size={100} />);
    expect(Number(screen.getByTestId("prayer-progress").getAttribute("stroke-dashoffset"))).toBeCloseTo(0);
    rerender(<PrayerRing name="Asr" time="15:12" progress={Number.NaN} label="l" size={100} />);
    expect(Number(screen.getByTestId("prayer-progress").getAttribute("stroke-dashoffset"))).toBeCloseTo(c);
  });
});

describe("chat screen", () => {
  it("shows sample messages and keeps sending off until step 2", () => {
    render(<ChatView lang="en" />);
    expect(screen.getByRole("heading", { name: "Ahmad" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByLabelText("Message Ahmad…")).toBeDisabled();
    expect(screen.getByText(/Messages are not sent yet/)).toBeInTheDocument();
  });
});

describe("menu", () => {
  beforeEach(() => {
    document.documentElement.dataset.theme = "dark";
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    document.cookie = "snafi-theme=; Max-Age=0; Path=/";
    document.cookie = "snafi-lang=; Max-Age=0; Path=/";
    refresh.mockClear();
  });

  it("opens, switches to light, and closes with Escape", () => {
    render(<Menu labels={labels("en")} theme="dark" lang="en" />);
    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Light" }));
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.cookie).toContain("snafi-theme=light");
    expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("switches to Arabic with right-to-left layout", () => {
    render(<Menu labels={labels("en")} theme="dark" lang="en" />);
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    expect(document.cookie).toContain("snafi-lang=ar");
    expect(refresh).toHaveBeenCalled();
  });

  it("offers sign-out when signed in", () => {
    render(<Menu labels={labels("ar")} theme="light" lang="ar" signOutAction={async () => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "القائمة" }));
    expect(screen.getByRole("button", { name: "تسجيل الخروج" })).toBeInTheDocument();
  });
});
