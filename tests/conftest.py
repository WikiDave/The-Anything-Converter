import os

# Tests never ask GitHub for a newer version.
os.environ.setdefault("ANYTHING_NO_UPDATE_CHECK", "1")
