from bdb import BdbQuit
from typing import Any, Optional

import typer
import uvicorn

from botwit.sync_memo import sync_twitter_to_notion

cli = typer.Typer(name="botwit")


@cli.command("sync")
def sync(debug: Optional[bool] = typer.Option(None, "--debug/--no-debug")) -> None:
    if debug:
        try:
            sync_twitter_to_notion()
        except BdbQuit:
            pass
        except Exception:
            __import__("pdb").post_mortem()  # POSTMORTEM
    else:
        sync_twitter_to_notion()


@cli.command("serve")
def run_server(
    port: int = typer.Option(8000, help="port to use"),
    watch: Optional[bool] = typer.Option(None, "--watch/--no-watch"),
) -> None:
    kwargs: dict[str, Any] = {"port": port, "app": "botwit.app:app", "reload": watch}
    uvicorn.run(**kwargs)


if __name__ == "__main__":
    cli()
