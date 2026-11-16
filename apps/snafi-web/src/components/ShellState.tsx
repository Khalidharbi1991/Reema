"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Shell = {
  /** Ids Khalid has just read or decided on this screen: the bell stops counting them at once. */
  settled: ReadonlySet<string>;
  settle: (id: string) => void;
  /** Puts an id back (the mark-read call failed, so the card is still unread). */
  unsettle: (id: string) => void;
  /** Chat tells the top bar when Ahmad is thinking. */
  thinking: boolean;
  setThinking: (value: boolean) => void;
};

const NONE: Shell = { settled: new Set(), settle: () => {}, unsettle: () => {}, thinking: false, setThinking: () => {} };
const ShellContext = createContext<Shell>(NONE);

/** What the signed-in screens share with the top bar without a reload: the bell's count and Chat's status. */
export function ShellProvider({ children }: { children: ReactNode }) {
  const [settled, setSettled] = useState<ReadonlySet<string>>(() => new Set());
  const [thinking, setThinking] = useState(false);
  const settle = useCallback((id: string) => setSettled((s) => (s.has(id) ? s : new Set(s).add(id))), []);
  const unsettle = useCallback((id: string) => setSettled((s) => {
    if (!s.has(id)) return s;
    const next = new Set(s);
    next.delete(id);
    return next;
  }), []);
  const value = useMemo(() => ({ settled, settle, unsettle, thinking, setThinking }), [settled, settle, unsettle, thinking]);
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell(): Shell {
  return useContext(ShellContext);
}
