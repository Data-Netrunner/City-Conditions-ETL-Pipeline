# ============================================================
# SAFE GITHUB PUSH — paste this into a Colab cell
# Never hardcode tokens in notebook cells.
#
# SETUP (one-time):
#   1. In Colab, click the 🔑 key icon in the left sidebar
#   2. Add a secret named: GITHUB_TOKEN
#   3. Paste your Personal Access Token as the value
#   4. Make sure "Notebook access" is toggled ON
# ============================================================

import subprocess
from google.colab import userdata

TOKEN = userdata.get("GITHUB_TOKEN")

# Point remote at authenticated URL
subprocess.run([
    "git", "remote", "set-url", "origin",
    f"https://Data-Netrunner:{TOKEN}@github.com/Data-Netrunner/City-Conditions-ETL-Pipeline.git"
], check=True)

# Stage, commit, push
subprocess.run(["git", "config", "user.name",  "Andre Felix"],              check=True)
subprocess.run(["git", "config", "user.email", "andrefelix3000@gmail.com"], check=True)
subprocess.run(["git", "add", "etl", "sql", "reports", "README.md",
                "requirements.txt", ".gitignore",
                ".github/workflows/daily_weather_etl.yml"],                 check=True)
subprocess.run(["git", "commit", "-m", "Update pipeline files"],            check=True)
subprocess.run(["git", "push"],                                             check=True)

# Remove token from git config immediately after pushing
subprocess.run([
    "git", "remote", "set-url", "origin",
    "https://github.com/Data-Netrunner/City-Conditions-ETL-Pipeline.git"
], check=True)

print("Push complete. Token removed from remote URL.")
