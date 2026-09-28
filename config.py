"""Central settings for Jawabdari. Change values here, not inside other files."""

# SQLite database file (created automatically)
DB_PATH = "jawabdari.db"

# Public URL of the app. Change this to your live URL after deploying,
# so QR codes point to the deployed Public Board page.
BASE_URL = "http://localhost:8501"

# Defect Liability Period (DLP) rule - Ahmedabad Municipal Corporation, Aug 2026
DLP_THRESHOLD_RS = 1_00_00_000   # Rs 1 crore
DLP_MONTHS_SMALL = 12            # works costing up to Rs 1 crore
DLP_MONTHS_LARGE = 36            # works costing more than Rs 1 crore

# Days a contractor gets to repair a defect after a notice is sent
NOTICE_DAYS = 7

# Show "inspect before guarantee expires" alerts this many days in advance
EXPIRY_ALERT_DAYS = 30
