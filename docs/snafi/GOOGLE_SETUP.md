# Snafi step 3: connecting your Google account

Nov 14, 2026 · For Khalid. You do every step yourself. Never paste the client secret, a
code or a token into a chat.

## What Snafi gets

| Scope | Why |
| --- | --- |
| `gmail.readonly` | read and search your mail |
| `gmail.compose` | make drafts, and send an email after you tap Approve (Gmail has no narrower scope for drafts) |
| `calendar.events` | read your main calendar and add events |
| `drive.readonly` | search and read Drive files; Snafi can never change, share or delete a file |

The refresh token stays only in your Windows Credential Manager on the PC. It never goes to
Supabase, Vercel, the logs or any chat.

## 1. Google Cloud (once, in the browser)

1. Open console.cloud.google.com, signed in with your **personal** Gmail. Create a project
   named **Snafi**. No billing account is needed.
2. **APIs & Services → Library:** enable **Gmail API**, **Google Calendar API** and
   **Google Drive API**.
3. **Google Auth Platform → Branding:** app name **Snafi**, user support email and developer
   contact your Gmail. **Do not upload a logo**: a logo starts Google's brand review.
4. **Audience:** user type **External**, publishing status **Testing**. Under Test users, add
   your Gmail.
5. **Data Access → Add or remove scopes:** add the four scopes in the table above. Save.
6. **Clients → Create client:** application type **Desktop app**, name **Snafi worker**.
   Keep the window open for the client ID and client secret (or download the JSON and keep
   it private).

## 2. On the PC (after the step 3 worker is deployed)

Do these as yourself, in a normal (not admin) PowerShell window:

1. Apply `apps/snafi-web/supabase/migrations/0006_google_today.sql` once in the Supabase
   SQL Editor.
2. Deploy the worker as usual (`src\snafi_worker\deploy\deploy.ps1`, as admin).
3. `C:\SnafiWorker\snafi.cmd set-secrets`: press Enter to keep the stored values, then paste
   the Google client ID and the client secret (hidden while you paste).
4. `C:\SnafiWorker\snafi.cmd connect-google`: your browser opens Google's sign-in.
   - Sign in with your personal Gmail.
   - "Google hasn't verified this app": choose **Advanced → Go to Snafi (unsafe)**. That is
     your own app.
   - **Tick every box**, then Continue. The browser says Snafi received the answer.
   - If a box is left unticked, nothing is stored; run it again.
5. Within five minutes the running worker picks up the connection; the Today screen shows
   your next event and important emails. `snafi.cmd connect-google --status` checks it.

To cancel the connection: `snafi.cmd connect-google --disconnect` (it cancels it at Google
and deletes it from the PC), or remove Snafi at myaccount.google.com/permissions.

## 3. The 7-day limit, and verification

- While the app is in **Testing**, Google ends the connection **every 7 days**. Today then
  says "Google needs reconnecting"; run step 2.4 again.
- After the first week, in **Audience**, click **Publish app** to move to **In production**,
  and **do not** submit it for verification. Google allows this for a personal app with
  fewer than 100 users: you see the unverified-app warning once, and the connection lasts
  until you cancel it, leave it unused for about six months, or change your Google password
  (that ends Gmail connections). Run step 2.4 once more after publishing.
- **Verification is not worth it:** Gmail and Drive are restricted scopes, so it needs a
  paid security assessment by an outside lab every year.

## What Ahmad may do

| Level | What |
| --- | --- |
| 1, just does it | read and search mail, calendar and Drive |
| 2, with Undo | save an email draft (never sent); add an event with only you |
| 3, approval card | send an email, invite people, delete an event or a draft; the card shows every recipient, the subject and the whole body |
| 4, never | more than 5 people in one email or invite; forwarding, filters, sharing, deleting mail or files |

What an email or a file says is never an instruction to Ahmad: an email that says "send X to
Y" can at most make him prepare a card, marked as suggested after reading outside content,
that waits for your Approve.
