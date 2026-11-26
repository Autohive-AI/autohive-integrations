"""Run locally to authorize a sandbox account and save credentials in root .env."""

import asyncio
from getpass import getpass
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlencode

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trademe.trademe import oauth_header  # noqa: E402

SANDBOX_API = "https://api.tmsandbox.co.nz"


async def exchange(session, path, header, params=None):
    async with session.post(
        f"{SANDBOX_API}/Oauth/{path}",
        headers={"Authorization": header},
        params=params,
        allow_redirects=False,
    ) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Trade Me authorization failed (HTTP {response.status}). Check the sandbox application."
            )
        values = parse_qs(await response.text())
        if not values.get("oauth_token") or not values.get("oauth_token_secret"):
            raise RuntimeError("Trade Me did not return an OAuth token and secret.")
        return values["oauth_token"][0], values["oauth_token_secret"][0]


def save_credentials(path, credentials):
    """Replace only Trade Me credentials; preserve other local settings."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition("=")[0].strip() not in credentials]
    for key, value in credentials.items():
        if any(char in value for char in "\r\n\"'"):
            raise ValueError("Credential contains an unsupported character.")
        lines.append(f'{key}="{value}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main():
    consumer_key = getpass("Sandbox consumer key: ").strip()
    consumer_secret = getpass("Sandbox consumer secret: ").strip()
    if not consumer_key or not consumer_secret:
        raise ValueError("Enter both sandbox consumer credentials.")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        token, secret = await exchange(
            session,
            "RequestToken",
            oauth_header(consumer_key, consumer_secret, oauth_callback="oob"),
            {"scope": "MyTradeMeRead"},
        )
        print("Open this URL. Sign in to the sandbox account and select Allow:")
        print("https://www.tmsandbox.co.nz/Oauth/Authorize?" + urlencode({"oauth_token": token}))
        verifier = getpass("Enter the seven-digit PIN from Trade Me: ").strip()
        if len(verifier) != 7 or not verifier.isascii() or not verifier.isdigit():
            raise ValueError("The PIN must contain seven digits.")
        access_token, access_secret = await exchange(
            session,
            "AccessToken",
            oauth_header(consumer_key, consumer_secret, token, secret, oauth_verifier=verifier),
        )
    path = Path(__file__).resolve().parents[2] / ".env"
    save_credentials(
        path,
        {
            "TRADEME_CONSUMER_KEY": consumer_key,
            "TRADEME_CONSUMER_SECRET": consumer_secret,
            "TRADEME_ACCESS_TOKEN": access_token,
            "TRADEME_ACCESS_TOKEN_SECRET": access_secret,
        },
    )
    print("Saved sandbox credentials in the repository root .env. Keep this file local.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (RuntimeError, ValueError, aiohttp.ClientError, TimeoutError):
        sys.exit("Sandbox authorization failed. Check the application credentials, PIN, and network connection.")
