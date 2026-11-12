from nicegui import ui

from beaverhabits import reminders
from beaverhabits.app.db import User

SUBSCRIBE_JS = """
(async () => {
  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    return {error: 'unsupported'};
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return {error: 'denied'};
  const reg = await navigator.serviceWorker.register('/statics/pwa/service_worker.js');
  await navigator.serviceWorker.ready;
  const key = '%s';
  const pad = '='.repeat((4 - key.length %% 4) %% 4);
  const raw = atob((key + pad).replace(/-/g, '+').replace(/_/g, '/'));
  const appKey = Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
  let sub = await reg.pushManager.getSubscription();
  if (sub && sub.options && sub.options.applicationServerKey) {
    const current = new Uint8Array(sub.options.applicationServerKey);
    if (current.length !== appKey.length || current.some((b, i) => b !== appKey[i])) {
      await sub.unsubscribe();
      sub = null;
    }
  }
  if (!sub) sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: appKey});
  return {subscription: sub.toJSON(), tz: Intl.DateTimeFormat().resolvedOptions().timeZone};
})()
"""

ERRORS = {
    "unsupported": "Este navegador no admite notificaciones. En iPhone, primero añade la app a la pantalla de inicio.",
    "denied": "Bloqueaste las notificaciones. Actívalas en los permisos del navegador para este sitio.",
}


async def reminders_section(user: User):
    reminder = await reminders.get_reminder(user)

    ui.label("Recordatorio diario").classes("text-lg font-bold")
    ui.label(
        "Cada día, a la hora que elijas, te avisamos con una notificación "
        "si te quedan hábitos sin marcar."
    ).classes("text-sm opacity-70")

    async def save(**changes):
        current = await reminders.get_reminder(user)
        current.update(changes)
        await reminders.save_reminder(user, current)

    with ui.row().classes("items-center gap-4"):
        switch = ui.switch("Activado", value=reminder["enabled"])
        time_input = ui.input("Hora", value=reminder["time"]).props("type=time dense")
        time_input.classes("w-32")

    devices = ui.label().classes("text-sm opacity-70")

    def show_devices(n: int):
        devices.text = (
            "Ningún dispositivo conectado todavía."
            if n == 0
            else f"Dispositivos conectados: {n}"
        )

    show_devices(len(reminder["subscriptions"]))

    async def on_switch(e):
        await save(enabled=bool(e.value))
        if e.value and not (await reminders.get_reminder(user))["subscriptions"]:
            await connect_device()

    async def on_time(e):
        value = (e.value or "").strip()
        if len(value) == 5 and value[2] == ":":
            # A new time today should be able to fire again.
            await save(time=value, last_sent=None)

    switch.on_value_change(on_switch)
    time_input.on_value_change(on_time)

    async def connect_device():
        try:
            result = await ui.run_javascript(
                SUBSCRIBE_JS % reminders.public_key(), timeout=60
            )
        except TimeoutError:
            ui.notify("No hubo respuesta del navegador. Inténtalo de nuevo.", color="warning")
            return
        if not result or result.get("error"):
            error = (result or {}).get("error", "")
            ui.notify(ERRORS.get(error, "No se pudo activar en este dispositivo."), color="negative")
            return
        await reminders.add_subscription(user, result["subscription"], result.get("tz"))
        current = await reminders.get_reminder(user)
        if not current["enabled"]:
            await save(enabled=True)
            switch.value = True
        show_devices(len(current["subscriptions"]))
        ui.notify("Notificaciones activadas en este dispositivo", color="positive")

    async def send_test():
        n = await reminders.send_test(user)
        show_devices(n)
        if n:
            ui.notify("Notificación de prueba enviada")
        else:
            ui.notify("Primero activa las notificaciones en este dispositivo", color="warning")

    with ui.row().classes("gap-2"):
        ui.button("Activar en este dispositivo", on_click=connect_device).props("unelevated")
        ui.button("Enviar prueba", on_click=send_test).props("flat")
