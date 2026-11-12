# VPN Not Connecting

## Quick checks
1. Confirm you have internet access by opening any public website.
2. Make sure the device date and time are correct; certificate checks fail when the clock is wrong.
3. Restart the VPN client completely (quit from the system tray / menu bar, then reopen).

## Common errors
- "Authentication failed": your password may have expired — reset it, then update the password saved in the VPN client.
- "Certificate not trusted" or "no valid certificate": the device certificate expired; connect to the office network or run a device sync from Company Portal to renew it.
- Connects but internal sites do not load: flush DNS (Windows: `ipconfig /flushdns`; macOS: `sudo dscacheutil -flushcache`) and reconnect.

## Still failing
Collect the VPN client log (Help > Export logs) and open a ticket with the exact error message and time.
