from flask import Flask, redirect, url_for, session, request, render_template
from msal import ConfidentialClientApplication
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
import os
import ssl

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'secret_key')

CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET')
TENANT_ID = os.getenv('AZURE_TENANT_ID')
KEY_VAULT_NAME = os.getenv('AZURE_VAULT_URL').split('//')[1].split('.')[0]      ##AZ Documentation

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
REDIRECT_PATH = "/getAToken"
SCOPE = ["User.Read"]

app.config["MSAL_CLIENT"] = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
)

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain('cert.pem', 'key.pem')

@app.route("/")
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    return render_template("index.html", user=session.get("user"))

@app.route("/login")
def login():
    session["flow"] = app.config["MSAL_CLIENT"].initiate_auth_code_flow(SCOPE, redirect_uri=url_for("authorized", _external=True))
    return render_template("login.html", auth_url=session["flow"]["auth_uri"])

@app.route(REDIRECT_PATH)
def authorized():
    try:
        result = app.config["MSAL_CLIENT"].acquire_token_by_auth_code_flow(session.get("flow", {}), request.args)
        session["user"] = result.get("id_token_claims")
        cache = session.get("msal_cache")
        if cache:
            session["msal_cache"] = cache.serialize()
    except ValueError: 
        pass
    return redirect(url_for("index"))

def get_keyvault_secret(secret_name):
    try:
        credential = ClientSecretCredential(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, tenant_id=TENANT_ID)
        kv_url = f"https://{KEY_VAULT_NAME}.vault.azure.net"
        client = SecretClient(vault_url=kv_url, credential=credential)
        secret = client.get_secret(secret_name)
        return secret.value
    except Exception as e:
        print(f"Error occurred while accessing Key Vault: {e}")
        return None

@app.route("/secrets")
def secrets():
    if not session.get("user"):
        return redirect(url_for("logout"))
    secret_value = get_keyvault_secret('x') 
    return render_template("secrets.html", secret_value=secret_value)

if __name__ == "__main__":
    app.run(debug=True, ssl_context=context)
