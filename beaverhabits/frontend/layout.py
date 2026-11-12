import time
from contextlib import contextmanager

from nicegui import background_tasks, ui

from beaverhabits import views
from beaverhabits.app.auth import user_logout
from beaverhabits.configs import settings
from beaverhabits.frontend import css, icons
from beaverhabits.frontend.components import (
    compat_card,
    habit_edit_dialog,
    menu_header,
    menu_icon_button,
    menu_icon_item,
    redirect,
    separator,
)
from beaverhabits.frontend.javascript import PREVENT_CONTEXT_MENU
from beaverhabits.frontend.menu import add_menu, sort_menu, stats_date_pick_menu
from beaverhabits.plan import plan
from beaverhabits.storage.meta import (
    get_root_path,
    is_page_demo,
    page_path,
    page_title,
)
from beaverhabits.storage.storage import Habit, HabitList
from beaverhabits.version import IDENTITY


def pwa_headers():
    # Extend background to iOS notch
    ui.add_head_html(
        """
        <link rel="apple-touch-icon" href="/statics/images/apple-touch-icon-v4.png">
        
        <meta name="apple-mobile-web-app-title" content="Hábitos">
        <meta name="application-name" content="MenosClick Hábitos">
        
        <meta name="theme-color" content="#F9F9F9" media="(prefers-color-scheme: light)" />
        <meta name="theme-color" content="#121212" media="(prefers-color-scheme: dark)" />
        """
    )

    # Experimental PWA
    if settings.ENABLE_IOS_STANDALONE:
        # Hiding Safari User Interface Components
        ui.add_head_html('<meta name="mobile-web-app-capable" content="yes">')
        ui.add_head_html('<link rel="manifest" href="/statics/pwa/manifest.json">')


def custom_headers():
    # Get current page info
    base_url = settings.APP_URL.rstrip("/")
    page_url = base_url + page_path()

    # SEO meta tags
    ui.add_head_html(
        f"""
        <!-- Basic Meta Tags -->
        <meta name="description" content="Rastreador de hábitos simple y privado de MenosClick. Marca tus hábitos diarios sin complicaciones.">
        <meta name="keywords" content="hábitos, rastreador de hábitos, productividad, rutinas, MenosClick">
        <meta name="author" content="MenosClick">
        <meta name="robots" content="noindex">
        <link rel="canonical" href="{page_url}">
        
        <!-- Open Graph / Facebook -->
        <meta property="og:type" content="website">
        <meta property="og:url" content="{page_url}">
        <meta property="og:title" content="MenosClick Hábitos">
        <meta property="og:description" content="Rastreador de hábitos simple y privado de MenosClick. Marca tus hábitos diarios sin complicaciones.">
        <meta property="og:image" content="{base_url}/statics/images/apple-touch-icon-v4.png">
        <meta property="og:site_name" content="MenosClick Hábitos">
        
        <!-- Twitter -->
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:url" content="{page_url}">
        <meta name="twitter:title" content="MenosClick Hábitos">
        <meta name="twitter:description" content="Rastreador de hábitos simple y privado de MenosClick. Marca tus hábitos diarios sin complicaciones.">
        <meta name="twitter:image" content="{base_url}/statics/images/apple-touch-icon-v4.png">
        
        <!-- Structured Data (JSON-LD) -->
        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": "MenosClick Hábitos",
            "url": "{base_url or page_url}",
            "description": "Rastreador de hábitos simple y privado de MenosClick. Marca tus hábitos diarios sin complicaciones.",
            "applicationCategory": "ProductivityApplication",
            "operatingSystem": "Web, iOS, Android",
            "offers": {{
                "@type": "Offer",
                "price": "0",
                "priceCurrency": "USD"
            }},
            "author": {{
                "@type": "Organization",
                "name": "MenosClick",
                "url": "https://github.com/DeivyRamos"
            }}
        }}
        </script>
        """
    )

    # Long-press event
    ui.add_head_html('<script src="/statics/libs/long-press-event.min.js"></script>')

    # Analytics
    if settings.UMAMI_ANALYTICS_ID:
        ui.add_head_html(
            f'<script defer src="{settings.UMAMI_SCRIPT_URL}" data-website-id="{settings.UMAMI_ANALYTICS_ID}"></script>'
        )

    # MenosClick brand color
    ui.colors(primary="#FF5A1F")

    # Prevent white flash on page load
    ui.add_css(css.WHITE_FLASH_PREVENT)
    ui.add_css(css.TEXTAREA_CSS)

    # prevent context menu
    ui.add_body_html(f"<script>{PREVENT_CONTEXT_MENU}</script>")

    # custom css styles
    views.apply_theme_style()


def show_help_dialog():
    with ui.context.client.content:
        with ui.dialog() as dialog:
            with compat_card().classes("w-[360px]"):
                title = IDENTITY.replace("/", " ")
                title = title.split("@")[0] if "@" in title else title
                ui.label(title).classes("text-lg font-bold")
                ui.separator()

                items = {
                    "Código fuente": "https://github.com/DeivyRamos/beaverhabits",
                    "Reportar un problema": "https://github.com/DeivyRamos/beaverhabits/issues",
                    "Proyecto original": "https://github.com/daya0576/beaverhabits",
                }

                with ui.grid(columns=2).classes("gap-2"):
                    for name, link in items.items():
                        ui.link(name, link, new_tab=True)

        dialog.props('backdrop-filter="blur(4px)"')
        dialog.open()


@ui.refreshable
def menu_component():
    """Dropdown menu for the top-right corner of the page."""
    with ui.menu().props('role="menu" transition-duration="50"'):
        add_menu()
        separator()

        with menu_icon_item("Herramientas", auto_close=False).classes("pr-1"):
            with ui.item_section().props("side").classes("pl-[1px]"):
                ui.icon(icons.CHEVRON_RIGHT)
            with ui.menu().props('anchor="top end" self="top start" auto-close'):
                # Stats for all habtis
                menu_icon_item("Reordenar", lambda: redirect("order"))
                separator()

                # Export & import
                menu_icon_item("Exportar", lambda: redirect("export"))
                separator()
                imp = menu_icon_item("Importar", lambda: redirect("import"))
                if is_page_demo():
                    imp.classes("disabled")
                separator()

                # Stats for all habtis
                menu_icon_item("Estadísticas", lambda: redirect("stats"))
                separator()

        separator()

        # Settings & reminders
        if not is_page_demo():
            menu_icon_item("Ajustes", lambda: redirect("settings"))
            separator()

        # About page
        menu_icon_item("Ayuda", show_help_dialog)
        separator()

        # Login & Logout
        menu_icon_item("Cerrar sesión", lambda: user_logout() and ui.navigate.to("/login"))


@contextmanager
def layout(
    title: str | None = None,
    habit: Habit | None = None,
    habit_list: HabitList | None = None,
    page_ui: ui.refreshable | None = None,
):
    # Standard headers
    custom_headers()
    pwa_headers()

    # Center the content on small screens
    with ui.column().classes("mx-auto mx-0"):

        # Layout wrapper
        with ui.row().classes("w-full gap-x-1"):
            title, target = title or page_title(), get_root_path()
            menu_header(title, target=target)
            ui.space()

            if habit:
                edit_dialog = habit_edit_dialog(habit)
                edit_btn = menu_icon_button("sym_r_pen_size_3", tooltip="Editar hábito")
                edit_btn.on_click(edit_dialog.open)
            elif habit_list and "add" in page_path():
                with menu_icon_button("sym_o_swap_vert", tooltip="Ordenar"):
                    sort_menu(habit_list)
            elif "stats" in page_path() and page_ui:
                with menu_icon_button("sym_o_expand_content", tooltip="Fechas"):
                    stats_date_pick_menu()

            with menu_icon_button("sym_o_menu"):
                menu_component()

        yield
