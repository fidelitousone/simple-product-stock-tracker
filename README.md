# VP2430 stock checker

Checks if the Protectli VP2430 is in stock via WooCommerce Store API, sends a notification through ntfy.sh when it's back in stock. Configurable poll time on GitHub Actions.


## Basic function
1. GitHub Actions job runs 'check_stock.py'
2. Script runs a GET request to the API, checks the `is_in_stock` field from the JSON payload
3. Compares the said field against the last known status in `last_status.json` file.
4. Status flips to in-stock if it's in stock, then POSTs a notification
5. Updated status committed back to repo.
