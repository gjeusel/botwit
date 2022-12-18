from __future__ import annotations

from typing import Any, Generator, Sequence

import httpx
import httpx_auth
from pydantic import BaseModel


class TwitterError(Exception):
    def __init__(self, payload: dict[str, Any] | None = None):
        """

        Note: payload is like:

        ```json
        {
            "errors": [
                {
                    "value": "trashh_devowejr",
                    "detail": "Could not find user with username: [trashh_devowejr].",
                    "title": "Not Found Error",
                    "resource_type": "user",
                    "parameter": "username",
                    "resource_id": "trashh_devowejr",
                    "type": "https://api.twitter.com/2/problems/resource-not-found",
                }
            ]
        }
        ```

        """
        self.payload = payload

        def __str__(self) -> str:
            if self.payload:
                errs = [
                    f"{e['resource_type']} '{e['title']}': {e['detail']}"
                    for e in self.payload
                ]
                if len(errs) > 1:
                    raise NotImplementedError
                else:
                    return errs[0]
            else:
                raise super().__str__()


class TwitterTokenCache(httpx_auth.oauth2_tokens.TokenMemoryCache):
    NO_EXPIRY = 2524608000  # "2050-01-01T00:00:00+00:00"

    def _add_bearer_token(self, key: str, token: str) -> None:
        if not token:
            raise httpx_auth.errors.InvalidToken(token)

        self._add_token(key=key, token=token, expiry=self.NO_EXPIRY)


class TwitterOAuth2ClientCredentials(httpx_auth.OAuth2ClientCredentials):
    # https://developer.twitter.com/en/docs/authentication/api-reference/token

    token_cache = TwitterTokenCache()

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        token = self.token_cache.get_token(
            self.state,
            early_expiry=self.early_expiry,
            on_missing_token=self.request_new_token,
        )
        request.headers[self.header_name] = self.header_value.format(token=token)
        yield request


class User(BaseModel):
    id: int  # noqa
    name: str
    username: str


class Tweet(BaseModel):
    id: int  # noqa
    text: str
    edit_history_tweet_ids: list[int]


def handle_twitter_error(response: httpx.Response) -> httpx.Response:
    response.read()  # ensure response is read before parsing json
    data = response.json()
    if data.get("errors"):
        raise TwitterError(data.get("errors"))
    return response


class TwitterClient(httpx.Client):
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        # access_token_key: str,
        # access_token_secret: str,
        base_url: str = "https://api.twitter.com",
        **kwargs: dict[str, Any],
    ):
        auth = TwitterOAuth2ClientCredentials(
            token_url=base_url + "/oauth2/token",
            # client_id=access_token_key,
            # client_secret=access_token_secret,
            client_id=consumer_key,
            client_secret=consumer_secret,
        )
        kwargs = {
            "follow_redirects": True,
            "event_hooks": {
                "request": [],
                "response": [
                    lambda resp: resp.raise_for_status(),
                    handle_twitter_error,
                ],
            },
        } | kwargs
        super().__init__(base_url=base_url, auth=auth, **kwargs)

    def get_user(self, username: str) -> User:
        username = username.lstrip("@")
        resp = self.get(f"/2/users/by/username/{username}")
        return User(**resp.json()["data"])

    def get_tweets(self, ids: int | Sequence[int]) -> list[Tweet]:
        params = {"ids": ",".join(str(e) for e in list(ids))}
        resp = self.get("/2/tweets", params=params)
        return [Tweet(**e) for e in resp.json()["data"]]

    def get_user_tweets(self, user_id: int) -> list[Tweet]:
        resp = self.get(f"/2/users/{user_id}/tweets")
        return [Tweet(**e) for e in resp.json()["data"]]

    def get_user_mentions(self, user_id: int) -> list[Tweet]:
        resp = self.get(f"/2/users/{user_id}/mentions")
        return [Tweet(**e) for e in resp.json()["data"]]
