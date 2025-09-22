import base64
import os
import urllib.parse
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

from chainlit.secret import random_secret
from chainlit.user import User


class OAuthProvider:
    id: str
    env: List[str]
    client_id: str
    client_secret: str
    authorize_url: str
    authorize_params: Dict[str, str]
    default_prompt: Optional[str] = None

    def is_configured(self):
        return all([os.environ.get(env) for env in self.env])

    async def get_token(self, code: str, url: str) -> str:
        raise NotImplementedError

    async def get_user_info(self, token: str) -> Tuple[Dict[str, str], User]:
        raise NotImplementedError

    def get_env_prefix(self) -> str:
        """Return environment prefix, like AZURE_AD."""

        return self.id.replace("-", "_").upper()

    def get_prompt(self) -> Optional[str]:
        """Return OAuth prompt param."""
        if prompt := os.environ.get(f"OAUTH_{self.get_env_prefix()}_PROMPT"):
            return prompt

        if prompt := os.environ.get("OAUTH_PROMPT"):
            return prompt

        return self.default_prompt


class GithubOAuthProvider(OAuthProvider):
    id = "github"
    env = ["OAUTH_GITHUB_CLIENT_ID", "OAUTH_GITHUB_CLIENT_SECRET"]
    authorize_url = "https://github.com/login/oauth/authorize"

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_GITHUB_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_GITHUB_CLIENT_SECRET")
        self.authorize_params = {
            "scope": "user:email",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                data=payload,
            )
            response.raise_for_status()
            content = urllib.parse.parse_qs(response.text)
            token = content.get("access_token", [""])[0]
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            user_response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}"},
            )
            user_response.raise_for_status()
            github_user = user_response.json()

            emails_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {token}"},
            )
            emails_response.raise_for_status()
            emails = emails_response.json()

            github_user.update({"emails": emails})
            user = User(
                identifier=github_user["login"],
                metadata={"image": github_user["avatar_url"], "provider": "github"},
            )
            return (github_user, user)


class GoogleOAuthProvider(OAuthProvider):
    id = "google"
    env = ["OAUTH_GOOGLE_CLIENT_ID", "OAUTH_GOOGLE_CLIENT_SECRET"]
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_GOOGLE_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_GOOGLE_CLIENT_SECRET")
        self.authorize_params = {
            "scope": "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
            "response_type": "code",
            "access_type": "offline",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=payload,
            )
            response.raise_for_status()
            json = response.json()
            token = json.get("access_token")
            if not token:
                raise httpx.HTTPStatusError(
                    "Failed to get the access token",
                    request=response.request,
                    response=response,
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/userinfo/v2/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            google_user = response.json()
            user = User(
                identifier=google_user["email"],
                metadata={"image": google_user["picture"], "provider": "google"},
            )
            return (google_user, user)


class AzureADOAuthProvider(OAuthProvider):
    id = "azure-ad"
    env = [
        "OAUTH_AZURE_AD_CLIENT_ID",
        "OAUTH_AZURE_AD_CLIENT_SECRET",
        "OAUTH_AZURE_AD_TENANT_ID",
    ]
    authorize_url = (
        f"https://login.microsoftonline.com/{os.environ.get('OAUTH_AZURE_AD_TENANT_ID', '')}/oauth2/v2.0/authorize"
        if os.environ.get("OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT")
        else "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    )
    token_url = (
        f"https://login.microsoftonline.com/{os.environ.get('OAUTH_AZURE_AD_TENANT_ID', '')}/oauth2/v2.0/token"
        if os.environ.get("OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT")
        else "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    )

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_AZURE_AD_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_AZURE_AD_CLIENT_SECRET")
        self.authorize_params = {
            "tenant": os.environ.get("OAUTH_AZURE_AD_TENANT_ID"),
            "response_type": "code",
            "scope": "https://graph.microsoft.com/User.Read offline_access",
            "response_mode": "query",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=payload,
            )
            response.raise_for_status()
            json = response.json()

            token = json["access_token"]
            refresh_token = json.get("refresh_token")
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            self._refresh_token = refresh_token
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            azure_user = response.json()

            try:
                photo_response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/photos/48x48/$value",
                    headers={"Authorization": f"Bearer {token}"},
                )
                photo_data = await photo_response.aread()
                base64_image = base64.b64encode(photo_data)
                azure_user["image"] = (
                    f"data:{photo_response.headers['Content-Type']};base64,{base64_image.decode('utf-8')}"
                )
            except Exception:
                # Ignore errors getting the photo
                pass

            user = User(
                identifier=azure_user["userPrincipalName"],
                metadata={
                    "image": azure_user.get("image"),
                    "provider": "azure-ad",
                    "refresh_token": getattr(self, "_refresh_token", None),
                },
            )
            return (azure_user, user)


class AzureADHybridOAuthProvider(OAuthProvider):
    id = "azure-ad-hybrid"
    env = [
        "OAUTH_AZURE_AD_HYBRID_CLIENT_ID",
        "OAUTH_AZURE_AD_HYBRID_CLIENT_SECRET",
        "OAUTH_AZURE_AD_HYBRID_TENANT_ID",
    ]
    authorize_url = (
        f"https://login.microsoftonline.com/{os.environ.get('OAUTH_AZURE_AD_HYBRID_TENANT_ID', '')}/oauth2/v2.0/authorize"
        if os.environ.get("OAUTH_AZURE_AD_HYBRID_ENABLE_SINGLE_TENANT")
        else "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    )
    token_url = (
        f"https://login.microsoftonline.com/{os.environ.get('OAUTH_AZURE_AD_HYBRID_TENANT_ID', '')}/oauth2/v2.0/token"
        if os.environ.get("OAUTH_AZURE_AD_HYBRID_ENABLE_SINGLE_TENANT")
        else "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    )

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_AZURE_AD_HYBRID_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_AZURE_AD_HYBRID_CLIENT_SECRET")
        nonce = random_secret(16)
        self.authorize_params = {
            "tenant": os.environ.get("OAUTH_AZURE_AD_HYBRID_TENANT_ID"),
            "response_type": "code id_token",
            "scope": "https://graph.microsoft.com/User.Read https://graph.microsoft.com/openid offline_access",
            "response_mode": "form_post",
            "nonce": nonce,
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=payload,
            )
            response.raise_for_status()
            json = response.json()

            token = json["access_token"]
            refresh_token = json.get("refresh_token")
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            self._refresh_token = refresh_token
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            azure_user = response.json()

            try:
                photo_response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/photos/48x48/$value",
                    headers={"Authorization": f"Bearer {token}"},
                )
                photo_data = await photo_response.aread()
                base64_image = base64.b64encode(photo_data)
                azure_user["image"] = (
                    f"data:{photo_response.headers['Content-Type']};base64,{base64_image.decode('utf-8')}"
                )
            except Exception:
                # Ignore errors getting the photo
                pass

            user = User(
                identifier=azure_user["userPrincipalName"],
                metadata={
                    "image": azure_user.get("image"),
                    "provider": "azure-ad",
                    "refresh_token": getattr(self, "_refresh_token", None),
                },
            )
            return (azure_user, user)


class OktaOAuthProvider(OAuthProvider):
    id = "okta"
    env = [
        "OAUTH_OKTA_CLIENT_ID",
        "OAUTH_OKTA_CLIENT_SECRET",
        "OAUTH_OKTA_DOMAIN",
    ]
    # Avoid trailing slash in domain if supplied
    domain = f"https://{os.environ.get('OAUTH_OKTA_DOMAIN', '').rstrip('/')}"

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_OKTA_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_OKTA_CLIENT_SECRET")
        self.authorization_server_id = os.environ.get(
            "OAUTH_OKTA_AUTHORIZATION_SERVER_ID", ""
        )
        self.authorize_url = (
            f"{self.domain}/oauth2{self.get_authorization_server_path()}/v1/authorize"
        )
        self.authorize_params = {
            "response_type": "code",
            "scope": "openid profile email",
            "response_mode": "query",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    def get_authorization_server_path(self):
        if not self.authorization_server_id:
            return "/default"
        if self.authorization_server_id == "false":
            return ""
        return f"/{self.authorization_server_id}"

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.domain}/oauth2{self.get_authorization_server_path()}/v1/token",
                data=payload,
            )
            response.raise_for_status()
            json_data = response.json()

            token = json_data.get("access_token")
            if not token:
                raise httpx.HTTPStatusError(
                    "Failed to get the access token",
                    request=response.request,
                    response=response,
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.domain}/oauth2{self.get_authorization_server_path()}/v1/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            okta_user = response.json()

            user = User(
                identifier=okta_user.get("email"),
                metadata={"image": "", "provider": "okta"},
            )
            return (okta_user, user)


class Auth0OAuthProvider(OAuthProvider):
    id = "auth0"
    env = ["OAUTH_AUTH0_CLIENT_ID", "OAUTH_AUTH0_CLIENT_SECRET", "OAUTH_AUTH0_DOMAIN"]

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_AUTH0_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_AUTH0_CLIENT_SECRET")
        # Ensure that the domain does not have a trailing slash
        self.domain = f"https://{os.environ.get('OAUTH_AUTH0_DOMAIN', '').rstrip('/')}"
        self.original_domain = (
            f"https://{os.environ.get('OAUTH_AUTH0_ORIGINAL_DOMAIN').rstrip('/')}"
            if os.environ.get("OAUTH_AUTH0_ORIGINAL_DOMAIN")
            else self.domain
        )

        self.authorize_url = f"{self.domain}/authorize"

        self.authorize_params = {
            "response_type": "code",
            "scope": "openid profile email",
            "audience": f"{self.original_domain}/userinfo",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.domain}/oauth/token",
                data=payload,
            )
            response.raise_for_status()
            json_content = response.json()
            token = json_content.get("access_token")
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.original_domain}/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            auth0_user = response.json()
            user = User(
                identifier=auth0_user.get("email"),
                metadata={
                    "image": auth0_user.get("picture", ""),
                    "provider": "auth0",
                },
            )
            return (auth0_user, user)


class DescopeOAuthProvider(OAuthProvider):
    id = "descope"
    env = ["OAUTH_DESCOPE_CLIENT_ID", "OAUTH_DESCOPE_CLIENT_SECRET"]
    # Ensure that the domain does not have a trailing slash
    domain = "https://api.descope.com/oauth2/v1"

    authorize_url = f"{domain}/authorize"

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_DESCOPE_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_DESCOPE_CLIENT_SECRET")
        self.authorize_params = {
            "response_type": "code",
            "scope": "openid profile email",
            "audience": f"{self.domain}/userinfo",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.domain}/token",
                data=payload,
            )
            response.raise_for_status()
            json_content = response.json()
            token = json_content.get("access_token")
            if not token:
                raise httpx.HTTPStatusError(
                    "Failed to get the access token",
                    request=response.request,
                    response=response,
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.domain}/userinfo", headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()  # This will raise an exception for 4xx/5xx responses
            descope_user = response.json()

            user = User(
                identifier=descope_user.get("email"),
                metadata={"image": "", "provider": "descope"},
            )
            return (descope_user, user)


class AWSCognitoOAuthProvider(OAuthProvider):
    id = "aws-cognito"
    env = [
        "OAUTH_COGNITO_CLIENT_ID",
        "OAUTH_COGNITO_CLIENT_SECRET",
        "OAUTH_COGNITO_DOMAIN",
    ]
    authorize_url = f"https://{os.environ.get('OAUTH_COGNITO_DOMAIN')}/login"
    token_url = f"https://{os.environ.get('OAUTH_COGNITO_DOMAIN')}/oauth2/token"

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_COGNITO_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_COGNITO_CLIENT_SECRET")
        self.scopes = os.environ.get("OAUTH_COGNITO_SCOPE", "openid profile email")
        self.authorize_params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": self.scopes,
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data=payload,
            )
            response.raise_for_status()
            json = response.json()

            token = json.get("access_token")
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            return token

    async def get_user_info(self, token: str):
        user_info_url = (
            f"https://{os.environ.get('OAUTH_COGNITO_DOMAIN')}/oauth2/userInfo"
        )
        async with httpx.AsyncClient() as client:
            response = await client.get(
                user_info_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()

            cognito_user = response.json()

            # Customize user metadata as needed
            user = User(
                identifier=cognito_user["email"],
                metadata={
                    "image": cognito_user.get("picture", ""),
                    "provider": "aws-cognito",
                },
            )
            return (cognito_user, user)


class GitlabOAuthProvider(OAuthProvider):
    id = "gitlab"
    env = [
        "OAUTH_GITLAB_CLIENT_ID",
        "OAUTH_GITLAB_CLIENT_SECRET",
        "OAUTH_GITLAB_DOMAIN",
    ]

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_GITLAB_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_GITLAB_CLIENT_SECRET")
        # Ensure that the domain does not have a trailing slash
        self.domain = f"https://{os.environ.get('OAUTH_GITLAB_DOMAIN', '').rstrip('/')}"

        self.authorize_url = f"{self.domain}/oauth/authorize"

        self.authorize_params = {
            "scope": "openid profile email",
            "response_type": "code",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.domain}/oauth/token",
                data=payload,
            )
            response.raise_for_status()
            json_content = response.json()
            token = json_content.get("access_token")
            if not token:
                raise HTTPException(
                    status_code=400, detail="Failed to get the access token"
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.domain}/oauth/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            gitlab_user = response.json()
            user = User(
                identifier=gitlab_user.get("email"),
                metadata={
                    "image": gitlab_user.get("picture", ""),
                    "provider": "gitlab",
                },
            )
            return (gitlab_user, user)


class KeycloakOAuthProvider(OAuthProvider):
    env = [
        "OAUTH_KEYCLOAK_CLIENT_ID",
        "OAUTH_KEYCLOAK_CLIENT_SECRET",
        "OAUTH_KEYCLOAK_REALM",
        "OAUTH_KEYCLOAK_BASE_URL",
    ]
    id = os.environ.get("OAUTH_KEYCLOAK_NAME", "keycloak")

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_KEYCLOAK_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_KEYCLOAK_CLIENT_SECRET")
        self.realm = os.environ.get("OAUTH_KEYCLOAK_REALM")
        self.base_url = os.environ.get("OAUTH_KEYCLOAK_BASE_URL")
        self.authorize_url = (
            f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/auth"
        )

        self.authorize_params = {
            "scope": "profile email openid",
            "response_type": "code",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token",
                data=payload,
            )
            response.raise_for_status()
            json = response.json()
            token = json.get("access_token")
            if not token:
                raise httpx.HTTPStatusError(
                    "Failed to get the access token",
                    request=response.request,
                    response=response,
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/userinfo",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            kc_user = response.json()
            user = User(
                identifier=kc_user["email"],
                metadata={"provider": "keycloak"},
            )
            return (kc_user, user)


class GenericOAuthProvider(OAuthProvider):
    env = [
        "OAUTH_GENERIC_CLIENT_ID",
        "OAUTH_GENERIC_CLIENT_SECRET",
        "OAUTH_GENERIC_AUTH_URL",
        "OAUTH_GENERIC_TOKEN_URL",
        "OAUTH_GENERIC_USER_INFO_URL",
        "OAUTH_GENERIC_SCOPES",
    ]
    id = os.environ.get("OAUTH_GENERIC_NAME", "generic")

    def __init__(self):
        self.client_id = os.environ.get("OAUTH_GENERIC_CLIENT_ID")
        self.client_secret = os.environ.get("OAUTH_GENERIC_CLIENT_SECRET")
        self.authorize_url = os.environ.get("OAUTH_GENERIC_AUTH_URL")
        self.token_url = os.environ.get("OAUTH_GENERIC_TOKEN_URL")
        self.user_info_url = os.environ.get("OAUTH_GENERIC_USER_INFO_URL")
        self.scopes = os.environ.get("OAUTH_GENERIC_SCOPES")
        self.user_identifier = os.environ.get("OAUTH_GENERIC_USER_IDENTIFIER", "email")

        self.authorize_params = {
            "scope": self.scopes,
            "response_type": "code",
        }

        if prompt := self.get_prompt():
            self.authorize_params["prompt"] = prompt

    async def get_token(self, code: str, url: str):
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": url,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_url, data=payload)
            response.raise_for_status()
            json = response.json()
            token = json.get("access_token")
            if not token:
                raise httpx.HTTPStatusError(
                    "Failed to get the access token",
                    request=response.request,
                    response=response,
                )
            return token

    async def get_user_info(self, token: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.user_info_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            server_user = response.json()
            user = User(
                identifier=server_user.get(self.user_identifier),
                metadata={
                    "provider": self.id,
                },
            )
            return (server_user, user)


providers = [
    GithubOAuthProvider(),
    GoogleOAuthProvider(),
    AzureADOAuthProvider(),
    AzureADHybridOAuthProvider(),
    OktaOAuthProvider(),
    Auth0OAuthProvider(),
    DescopeOAuthProvider(),
    AWSCognitoOAuthProvider(),
    GitlabOAuthProvider(),
    KeycloakOAuthProvider(),
    GenericOAuthProvider(),
]


def get_oauth_provider(provider: str) -> Optional[OAuthProvider]:
    for p in providers:
        if p.id == provider:
            return p
    return None


def get_configured_oauth_providers():
    return [p.id for p in providers if p.is_configured()]
