from nicegui import ui

from beaverhabits import views
from beaverhabits.app.db import User
from beaverhabits.frontend.layout import layout
from beaverhabits.frontend.reminders_section import reminders_section
from beaverhabits.utils import set_user_dark_mode

EDIT_ME = """\
/* Edit this CSS to customize theme */
/* body {
    background-color: #ddd !important;
} */
"""


async def settings_page(user: User):
    configs = await views.get_user_configs(user)

    async def update_custom_css(e):
        await views.update_custom_css(user, e.value)
        views.apply_theme_style()

    def toggle_dark_mode(value: bool):
        set_user_dark_mode(value)
        if value:
            ui.dark_mode().enable()
        else:
            ui.dark_mode().disable()

    with layout(title="Ajustes"):
        with ui.column().classes("w-full max-w-[600px] gap-3"):
            await reminders_section(user)
            ui.separator().classes("my-4")

            # ui.label("Modo oscuro").classes("text-lg font-bold")
            # with ui.row():
            #     ui.button("Oscuro", on_click=lambda: toggle_dark_mode(True))
            #     ui.button("Claro", on_click=lambda: toggle_dark_mode(False))

            ui.label("CSS personalizado").classes("text-lg font-bold")
            editor = ui.codemirror(
                configs.custom_css or EDIT_ME, language="CSS", theme="githubDark"
            ).classes("h-96")
            editor.on_value_change(update_custom_css)
