from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from .sync_memo import sync_twitter_to_notion


async def homepage(request: Request) -> PlainTextResponse:
    sync_twitter_to_notion()
    return PlainTextResponse("gut")


routes = [Route("/", endpoint=homepage)]

app = Starlette(debug=True, routes=routes)
