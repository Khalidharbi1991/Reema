/** Phase 2: the "Couldn't send" note belongs to one attempt. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatComposer } from "@/app/(app)/chat/ChatComposer";

const labels = { placeholder: "Message Ahmad", send: "Send", attach: "Attach", failed: "Couldn't send. Try again." };

async function submit() {
  await act(async () => {
    fireEvent.submit(screen.getByRole("textbox").closest("form")!);
  });
}

describe("ChatComposer", () => {
  it("shows the failure, keeps the text, and hides the note once Khalid types again", async () => {
    const send = async () => ({ error: true, sentAt: Date.now() });
    render(<ChatComposer send={send} labels={labels} note="" />);
    const box = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.input(box, { target: { value: "hello" } });
    await submit();
    expect(screen.getByRole("status")).toHaveTextContent(labels.failed);
    expect(box.value).toBe("hello");
    fireEvent.input(box, { target: { value: "hello!" } });
    expect(screen.getByRole("status")).not.toHaveTextContent(labels.failed);
  });

  it("SEC-73: posts, never puts the message in a URL", () => {
    const send = async () => ({ error: false, sentAt: Date.now() });
    render(<ChatComposer send={send} labels={labels} note="" />);
    expect(screen.getByRole("textbox").closest("form")!.getAttribute("method")).toBe("post");
  });

  it("shows no failure after a send that worked", async () => {
    const send = async () => ({ error: false, sentAt: Date.now() });
    render(<ChatComposer send={send} labels={labels} note="" />);
    fireEvent.input(screen.getByRole("textbox"), { target: { value: "hello" } });
    await submit();
    expect(screen.getByRole("status")).not.toHaveTextContent(labels.failed);
  });
});
