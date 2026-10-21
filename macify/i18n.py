"""Idioma de Macify: el del usuario. Inglés por defecto, español si el sistema está en español.

Los textos del código están en inglés; `_()` devuelve la traducción cuando corresponde.
Los textos con datos usan marcadores: `_("Downloading {name}").format(name=...)`.
"""

import os


def language() -> str:
    for variable in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(variable)
        if value:
            return "es" if value.lower().startswith("es") else "en"
    return "en"


SPANISH = {
    # Asistente
    "Goodbye, Ubuntu style. Hello, macOS style.": "Adiós, estilo Ubuntu. Bienvenido, estilo macOS.",
    "session": "sesión",
    "unknown": "desconocida",
    "Get Started": "Comenzar",
    "Back": "Atrás",
    "Continue": "Continuar",
    "Install": "Instalar",
    "Choose your look": "Elige tu apariencia",
    "Windows, menus and apps will switch to this style.": "Ventanas, menús y apps cambiarán a este estilo.",
    "Light": "Claro",
    "Dark": "Oscuro",
    "Choose your wallpaper": "Elige tu fondo",
    "Buttons and system colors come from your wallpaper.": "El color de los botones y del sistema sale de tu fondo.",
    "Accent color: {color}": "Color de acento: {color}",
    "Add Photos…": "Agregar fotos…",
    "Add your photos": "Agrega tus fotos",
    "Images": "Imágenes",
    "Your Dock": "Tu dock",
    "Bottom, floating and glass, like on macOS.": "Abajo, flotante y de cristal, como en macOS.",
    "Icon size": "Tamaño de los iconos",
    "Magnify on hover": "Ampliar al pasar el ratón",
    "Icons grow like on macOS": "Los iconos crecen como en macOS",
    "Magic lamp effect": "Efecto lámpara mágica",
    "Animation when minimizing windows": "Animación al minimizar ventanas",
    "Ready to begin": "Todo listo para empezar",
    "Takes a few minutes. You'll be asked to restart at the end.": "Tarda unos minutos. Al final te pedirá reiniciar.",
    "macOS-style login screen": "Pantalla de inicio de sesión estilo macOS",
    "From the moment you turn on your computer. Asks for your password. Beta.":
        "Desde que enciendes el equipo. Pedirá tu contraseña. Beta.",
    "Preparing…": "Preparando…",
    "What's happening, in detail": "Qué está pasando, en detalle",
    "Restart Now": "Reiniciar ahora",
    "Later": "Más tarde",
    "Welcome to your new Mac": "Bienvenido a tu nuevo Mac",
    "Restart your computer to see all the changes.": "Reinicia el equipo para ver todos los cambios.",
    "Customize Again": "Volver a personalizar",
    "Restore Original Settings": "Restaurar ajustes originales",
    "Uninstall Everything": "Desinstalar todo",
    "Macify is active": "Macify está activo",
    "Change your style, go back to the original, or remove everything.":
        "Puedes cambiar tu estilo, volver al original o quitarlo todo.",
    "Restoring…": "Restaurando…",
    "Uninstalling…": "Desinstalando…",
    "One moment.": "Un momento.",
    "Done": "Hecho",
    "Restart your computer to see the change.": "Reinicia el equipo para ver el cambio.",
    "Something went wrong": "Algo salió mal",
    "Check the details to see the error.": "Revisa el detalle para ver el error.",
    "Open “What's happening, in detail” to see the error. You can retry or restore your settings.":
        "Abre «Qué está pasando, en detalle» para ver el error. Puedes reintentar o restaurar tus ajustes.",
    # Pasos
    "Preparing the system": "Preparando el sistema",
    "Checks and installs the tools that are needed.": "Comprueba e instala las herramientas que hacen falta.",
    "Installing San Francisco fonts": "Instalando fuentes San Francisco",
    "The same typefaces as macOS across the whole system.": "Las mismas letras de macOS en todo el sistema.",
    "macOS windows and buttons": "Ventanas y botones de macOS",
    "Title bars, colored buttons and apps in macOS style.": "Barras de título, botones de colores y apps en estilo macOS.",
    "macOS icons": "Iconos de macOS",
    "Installs the macOS-style icon set.": "Instala el set de iconos estilo macOS.",
    "macOS cursor": "Cursor de macOS",
    "The macOS mouse pointer.": "El puntero del ratón de macOS.",
    "Dock, menu bar and effects": "Dock, barra superior y efectos",
    "Animated dock, macOS menu bar and minimize effect.": "Dock con animaciones, barra de menús de macOS y efecto al minimizar.",
    "Checking every icon": "Revisando cada icono",
    "Creates missing icons and makes sure none is broken.": "Crea los iconos que falten y comprueba que no quede ninguno roto.",
    "Applying wallpaper, colors and settings": "Aplicando fondo, colores y ajustes",
    "Wallpaper, accent color, fonts, keyboard shortcuts and lock screen.":
        "Fondo, color de acento, fuentes, atajos de teclado y pantalla de bloqueo.",
    "Login screen": "Pantalla de inicio de sesión",
    "macOS style from the moment you turn on your computer. Asks for your password.":
        "Estilo macOS desde que enciendes el equipo. Pedirá tu contraseña.",
    # Registro
    "Tools: all set.": "Herramientas: todo listo.",
    "Tools to install: {packages}": "Herramientas a instalar: {packages}",
    "Installing dependencies: {packages}": "Instalando dependencias: {packages}",
    "Could not install dependencies (cancelled or apt error).":
        "No se pudieron instalar las dependencias (cancelado o error de apt).",
    "Icons created for apps without a macOS style: {count}": "Iconos creados para apps sin estilo Mac: {count}",
    "Audit: no broken icons.": "Auditoría: ningún icono roto.",
    "Audit: {count} missing: {apps}": "Auditoría: faltan {count}: {apps}",
    "Accent color from your wallpaper: {color}": "Color de acento según tu fondo: {color}",
    "== Macify: {count} steps": "== Macify: {count} pasos",
    " (dry run)": " (simulación)",
    "== Dry run finished: nothing was changed.": "== Simulación terminada: no se cambió nada.",
    "== Done. Restart to see all the changes.": "== Listo. Reinicia para ver todos los cambios.",
    "Downloading {name} from {source}": "Descargando {name} desde {source}",
    "Downloaded: {size:.1f} MB": "Descargado: {size:.1f} MB",
    "The {name} file does not match its UUID.": "El archivo de {name} no coincide con su UUID.",
    "Install extension {name}": "Instalar extensión {name}",
    "Install Macify's own extension in {path}": "Instalar extensión propia de Macify en {path}",
    "Remove {path}": "Borrar {path}",
    "Disable {name}": "Desactivar {name}",
    "{name}: {count} fonts extracted": "{name}: {count} fuentes extraídas",
    "No local fonts: SF Pro and SF Mono would be downloaded from apple.com":
        "No hay fuentes locales: se descargarían SF Pro y SF Mono de apple.com",
    "SF fonts: {count} files from {source}": "Fuentes SF: {count} archivos desde {source}",
    "your resources folder": "tu carpeta de recursos",
    "Skipped: schema {schema} does not exist on this system.": "Omitido: el esquema {schema} no existe en este sistema.",
    "Skipped: key {schema}/{key} does not exist.": "Omitido: la clave {schema}/{key} no existe.",
    "No backup: nothing to restore.": "No hay copia de seguridad: no hay nada que restaurar.",
    "Restore dry run finished.": "Simulación de restauración terminada.",
    "Restore complete.": "Restauración completa.",
    "Failed: {command}": "Falló: {command}",
    "Install: {options}": "Instalar: {options}",
    "Install WhiteSur icons in ~/.local/share/icons": "Instalar iconos WhiteSur en ~/.local/share/icons",
    "Install WhiteSur cursors": "Instalar cursores WhiteSur",
    "Login screen: {options}": "Pantalla de inicio de sesión: {options}",
    "== Uninstalling Macify": "== Desinstalando Macify",
    "To remove the package from the system: sudo apt remove macify":
        "Para quitar el paquete del sistema: sudo apt remove macify",
    "== Dry run finished.": "== Simulación terminada.",
    "== Uninstall complete. Restart your session.": "== Desinstalación completa. Reinicia la sesión.",
    "Icon theme {theme}: inherits from {parents}": "Tema de iconos {theme}: hereda de {parents}",
    "{app}: fixed image icon → {name}": "{app}: icono fijo → {name}",
    "{app}: no macOS-style icon → created": "{app}: sin icono estilo Mac → creado",
    "Remove launcher {path}": "Borrar lanzador {path}",
    "Theme chain:": "Cadena de temas:",
    "No broken icons.": "Ningún icono roto.",
    "Your apps": "Tus apps",
    "Browsers, VS Code, Firefox and Flatpak apps use the macOS buttons.":
        "Navegadores, VS Code, Firefox y apps Flatpak usan los botones de macOS.",
    "Automatic upkeep": "Mantenimiento automático",
    "New apps get their macOS icon on their own; the dock switches at login.":
        "Las apps nuevas reciben su icono estilo Mac solas; el dock cambia al iniciar sesión.",
    "Automatic upkeep: at login and whenever an app is installed":
        "Mantenimiento automático: al iniciar sesión y cada vez que se instala una app",
    "VS Code: use the system title bar": "VS Code: usar la barra de título del sistema",
    "Brave is open: its title bar will change at your next login.":
        "Brave está abierto: su barra de título cambiará en tu próximo inicio de sesión.",
    "Brave: use the system title bar": "Brave: usar la barra de título del sistema",
    "Firefox is open: its macOS theme will be installed at your next login.":
        "Firefox está abierto: su tema de macOS se instalará en tu próximo inicio de sesión.",
    "Firefox: macOS theme with traffic-light buttons": "Firefox: tema de macOS con botones de semáforo",
    "VS Code: restore its title bar": "VS Code: restaurar su barra de título",
    "Brave: restore its title bar": "Brave: restaurar su barra de título",
    "Firefox: remove the macOS theme": "Firefox: quitar el tema de macOS",
    "macOS-style startup and login screens": "Arranque e inicio de sesión estilo macOS",
    "Black boot screen with your logo and the macOS login screen. Asks for your password once.":
        "Arranque negro con tu logo y la pantalla de inicio de sesión de macOS. Pide tu contraseña una vez.",
    "Startup and login screens": "Arranque e inicio de sesión",
    "macOS style from the moment you turn on your computer. Asks for your password once.":
        "Estilo macOS desde que enciendes el equipo. Pide tu contraseña una vez.",
    "Startup and login screens: one administrator password":
        "Arranque e inicio de sesión: una contraseña de administrador",
    "Startup and login screens: back to the original": "Arranque e inicio de sesión: volver al original",
    "The startup and login screens could not be applied (cancelled or error).":
        "No se pudieron aplicar el arranque y el inicio de sesión (cancelado o error).",
    "System tools": "Herramientas del sistema",
    "All installed.": "Todo instalado.",
    "Windows theme": "Tema de ventanas",
    "Icon set": "Set de iconos",
    "Cursor": "Cursor",
    "Not downloaded.": "Sin descargar.",
    "Installed (update check skipped).": "Instalado (sin revisar actualizaciones).",
    "Could not reach GitHub to check for updates.": "No se pudo consultar GitHub para buscar actualizaciones.",
    "Up to date.": "Al día.",
    "Update available.": "Hay una actualización.",
    "Not installed.": "Sin instalar.",
    "GNOME reports: {state}.": "GNOME informa: {state}.",
    "Installed; it starts after you log in again.": "Instalada; arranca al volver a iniciar sesión.",
    "Update available: version {local} → {remote}.": "Hay actualización: versión {local} → {remote}.",
    "Running.": "Funcionando.",
    "Settings": "Ajustes",
    "Everything as Macify left it.": "Todo como lo dejó Macify.",
    "Changed since install: {keys}": "Cambiaron desde la instalación: {keys}",
    "Icons": "Iconos",
    "Macify icon theme missing.": "Falta el tema de iconos de Macify.",
    "SF fonts": "Fuentes SF",
    "Installed.": "Instaladas.",
    "Not found.": "No encontradas.",
    "Watching for new apps.": "Vigilando apps nuevas.",
    "Not running.": "Sin funcionar.",
    "Startup screen": "Pantalla de arranque",
    "Macify boot screen active.": "Arranque de Macify activo.",
    "Another boot screen is active.": "Hay otro arranque activo.",
    "Fixing: {name}": "Arreglando: {name}",
    "Fixed: {count}": "Arreglados: {count}",
    "{count} items need attention. Open Macify → Check for problems.":
        "{count} cosas necesitan atención. Abre Macify → Buscar problemas.",
    "Check for Problems": "Buscar problemas",
    "Fix All": "Arreglar todo",
    "Checking your Mac…": "Revisando tu Mac…",
    "Everything is fine": "Todo está bien",
    "Some things need attention": "Algunas cosas necesitan atención",
    "Nothing to fix.": "Nada que arreglar.",
    "{name} is open: its buttons will change at your next login.":
        "{name} está abierto: sus botones cambiarán en tu próximo inicio de sesión.",
    "{name}: use the system theme for its buttons": "{name}: usar el tema del sistema para sus botones",
    "{name}: restore its buttons": "{name}: restaurar sus botones",
    "Flatpak apps: use the system theme and icons": "Apps Flatpak: usar el tema y los iconos del sistema",
    "Flatpak apps: restore their default theme access": "Apps Flatpak: restaurar su acceso al tema",
    "Hide automatically": "Ocultar automáticamente",
    "When a window covers it. Move the pointer to the bottom edge to show it.":
        "Cuando una ventana lo tapa. Lleva el puntero al borde inferior para mostrarlo.",
    # Colores de acento
    "red": "rojo", "orange": "naranja", "yellow": "amarillo", "green": "verde", "teal": "turquesa",
    "blue": "azul", "purple": "morado", "pink": "rosa", "slate": "grafito",
}


def _(text: str) -> str:
    return SPANISH.get(text, text) if language() == "es" else text
