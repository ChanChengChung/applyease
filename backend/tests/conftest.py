import os

# Keep the complete test suite isolated from the developer's PostgreSQL database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_ENV"] = "test"
os.environ["AI_EXTRACTION_ENABLED"] = "false"
os.environ["AI_JOB_ANALYSIS_ENABLED"] = "false"
os.environ["AI_MATERIAL_GENERATION_ENABLED"] = "false"
os.environ["AI_APPLICATION_FORM_ENABLED"] = "false"
os.environ["MAIL_DELIVERY_MODE"] = "disabled"
os.environ["ACCOUNT_EMAIL_MAX_IP_REQUESTS"] = "10000"
