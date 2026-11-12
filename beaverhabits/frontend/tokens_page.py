from nicegui import ui

from beaverhabits.app import crud
from beaverhabits.app.db import User
from beaverhabits.frontend.layout import layout


async def tokens_page(user: User):
    token = await crud.get_user_api_token(user)

    with layout():
        with ui.column().classes("w-full max-w-[600px] px-4"):
            ui.label("Token de API").classes("text-lg font-bold")
            ui.label(
                "Use this token to authenticate with the Beaver Habits API. "
                "It never expires but can be reset at any time."
            ).classes("text-sm opacity-70")

            token_container = ui.column().classes("w-full gap-2")

            async def render_token():
                nonlocal token
                token_container.clear()
                with token_container:
                    if token:
                        ui.input(
                            "Tu token de API",
                            value=token,
                        ).props("readonly outlined dense").classes(
                            "w-full font-mono text-xs sm:text-sm"
                        )

                        with ui.row().classes("gap-2 flex-wrap"):
                            ui.button(
                                "Copy",
                                on_click=lambda: (
                                    ui.run_javascript(
                                        f"navigator.clipboard.writeText('{token}')"
                                    ),
                                    ui.notify("Copiado al portapapeles", color="positive"),
                                ),
                                icon="content_copy",
                            ).props("flat dense")

                            async def reset_token():
                                nonlocal token
                                token = await crud.reset_user_api_token(user)
                                ui.notify("Token regenerado", color="positive")
                                await render_token()

                            ui.button(
                                "Regenerar token",
                                on_click=reset_token,
                                icon="refresh",
                            ).props("flat dense color=negative")

                            async def delete_token():
                                nonlocal token
                                await crud.delete_user_api_token(user)
                                token = None
                                ui.notify("Token eliminado", color="positive")
                                await render_token()

                            ui.button(
                                "Eliminar",
                                on_click=delete_token,
                                icon="delete",
                            ).props("flat dense color=negative")
                    else:

                        async def create_token():
                            nonlocal token
                            token = await crud.create_user_api_token(user)
                            ui.notify("Token creado", color="positive")
                            await render_token()

                        ui.button(
                            "Generar token de API",
                            on_click=create_token,
                            icon="add",
                        ).props("flat dense")

            await render_token()

            ui.separator()

            ui.label("Uso").classes("text-lg font-bold")
            ui.markdown(
                "```\n"
                "curl -H 'Authorization: Bearer <YOUR_TOKEN>' \\\n"
                "  https://beaverhabits.com/api/v1/habits\n"
                "```"
            ).classes("w-full overflow-x-auto")
