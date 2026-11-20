# Saved market snapshots

This directory holds real, timestamped Yahoo Finance option snapshots, when a fetch succeeds.
The scheduled workflow attempts to refresh the default SPY / 3-expiry snapshot once per weekday
during market hours. Failed requests and responses without usable bid/ask quotes leave the
previous file unchanged. Until the first valid capture succeeds, this directory contains no
market JSON and the dashboard uses its explicitly labeled synthetic fallback.

The dashboard reads these committed files on a cold start, before trying Yahoo in the background.
It also saves successful interactive fetches in its local bounded disk cache. Local files may be
lost when the hosting service replaces the machine; committed snapshots remain available.

Every snapshot retains its source, underlying bar timestamp, original capture time, and the time
to expiry measured at that capture. Cached quotes are historical observations, not live prices.
The JSON filename is a hash of the requested ticker and expiry count.

If no real snapshot has ever been captured, the dashboard explicitly displays an offline
synthetic example. Example prices are never saved here or presented as cached market quotes.
