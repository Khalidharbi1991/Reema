"use server";

import { redirect } from "next/navigation";
import { authAdapter } from "@/adapters";
import { isPreviewMode } from "@/config/env";

export async function signOut() {
  if (!isPreviewMode()) await authAdapter().signOut();
  redirect("/sign-in");
}
