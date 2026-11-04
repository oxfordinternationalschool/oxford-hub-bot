"""Local server for the admin Mini App:  python -m bot.devserver [port]

Serves public/ and the same /api endpoint Vercel runs, on http://localhost:8080.
Telegram only opens Mini Apps over HTTPS, so to try it inside Telegram put a tunnel
in front of it and set WEBAPP_URL (see README). On Vercel none of this is needed.
"""
import logging
import sys
from pathlib import Path

from aiohttp import web

from bot.webhook import handle

PUBLIC = Path(__file__).resolve().parent.parent / "public"


async def api(request: web.Request) -> web.Response:
    headers = {k.lower(): v for k, v in request.headers.items()}
    status, body, content_type = await handle(request.method, headers, await request.read(), request.query_string)
    if isinstance(body, bytes):
        return web.Response(status=status, body=body, content_type=content_type)
    return web.Response(status=status, text=body, content_type=content_type.split(";")[0], charset="utf-8")


async def admin_page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(PUBLIC / "admin" / "index.html", headers={"Cache-Control": "no-store"})


async def admin_redirect(request: web.Request) -> web.Response:
    raise web.HTTPFound("/admin/")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    app = web.Application()
    app.router.add_route("*", "/api", api)
    app.router.add_get("/admin", admin_redirect)
    app.router.add_get("/admin/", admin_page)
    print(f"Mini App: http://localhost:{port}/admin/")
    web.run_app(app, host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    main()
