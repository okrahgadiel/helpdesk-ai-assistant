# Printer Offline or Print Jobs Stuck

## Steps
1. Check the printer display for paper jams, empty trays, or low toner.
2. Confirm the printer is on the network: print a configuration page and check it has an IP address.
3. Clear the print queue: open Printers & scanners, select the printer, open the queue, and cancel all documents.
4. Restart the Print Spooler service on Windows (services.msc > Print Spooler > Restart).
5. Remove the printer and re-add it from the company print server (\\printserver) so the correct driver installs.

## Secure print release
Jobs sent to the follow-me queue are held for 24 hours. Badge in at any company printer to release them.
