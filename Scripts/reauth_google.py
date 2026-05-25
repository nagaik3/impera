#!/usr/bin/env python3
"""
Re-autenticação Google OAuth — IMPERA
Regenera google_token.json quando o refresh token expira.
Uso: python3 reauth_google.py
(Vai abrir o browser para login)
"""

import json
import os

TOKEN_FILE = os.path.expanduser("~/Scripts/google_token.json")
CRED_FILE = os.path.expanduser("~/Scripts/google_credentials_impera.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(CRED_FILE):
        print(f"ERRO: {CRED_FILE} não encontrado")
        return

    print("Abrindo browser para autenticação Google...")
    print("Faça login e autorize o acesso.\n")

    flow = InstalledAppFlow.from_client_secrets_file(CRED_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\n✅ Token salvo em {TOKEN_FILE}")
    print("Automação Drive vai voltar a funcionar no próximo ciclo (15 min).")


if __name__ == "__main__":
    main()
