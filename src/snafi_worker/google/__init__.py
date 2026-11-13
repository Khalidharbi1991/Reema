"""Khalid's personal Google account: Gmail, Calendar and Drive (Snafi step 3).

Raw HTTPS with the standard library (no Google SDK; the worker's private Python holds only
pyyaml and tzdata). The refresh token lives only in Khalid's Windows Credential Manager,
stored by `snafi.cmd connect-google`; the short-lived access token is kept in memory only.
The providers (gmail, google_calendar, google_drive) register when the registry imports
google.gmail, google.gcal and google.drive.
"""
