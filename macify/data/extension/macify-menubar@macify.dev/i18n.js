// Textos en inglés; en español si el idioma del sistema es español.

import GLib from 'gi://GLib';

const SPANISH = {
    // Menú del logo
    'About This Computer': 'Acerca de este equipo',
    'System Settings…': 'Ajustes del sistema…',
    'App Center…': 'App Center…',
    'Force Quit…': 'Forzar salida…',
    'Sleep': 'Suspender',
    'Restart…': 'Reiniciar…',
    'Shut Down…': 'Apagar…',
    'Lock Screen': 'Bloquear pantalla',
    'Log Out…': 'Cerrar sesión…',
    // Menús de app
    'File': 'Archivo',
    'Edit': 'Edición',
    'View': 'Ver',
    'Go': 'Ir',
    'Window': 'Ventana',
    'Help': 'Ayuda',
    'About {app}': 'Acerca de {app}',
    'Settings…': 'Ajustes…',
    'Hide {app}': 'Ocultar {app}',
    'Hide Others': 'Ocultar otras',
    'Show All': 'Mostrar todo',
    'Quit {app}': 'Salir de {app}',
    'New Window': 'Nueva ventana',
    'New Tab': 'Nueva pestaña',
    'New Folder': 'Nueva carpeta',
    'Open…': 'Abrir…',
    'Save': 'Guardar',
    'Save As…': 'Guardar como…',
    'Print…': 'Imprimir…',
    'Close Window': 'Cerrar ventana',
    'Undo': 'Deshacer',
    'Redo': 'Rehacer',
    'Cut': 'Cortar',
    'Copy': 'Copiar',
    'Paste': 'Pegar',
    'Select All': 'Seleccionar todo',
    'Find…': 'Buscar…',
    'Emoji & Symbols': 'Emojis y símbolos',
    'Enter Full Screen': 'Pantalla completa',
    'Exit Full Screen': 'Salir de pantalla completa',
    'Zoom In': 'Acercar',
    'Zoom Out': 'Alejar',
    'Actual Size': 'Tamaño real',
    'Reload': 'Recargar',
    'Back': 'Atrás',
    'Forward': 'Adelante',
    'Enclosing Folder': 'Carpeta contenedora',
    'Home': 'Inicio',
    'Documents': 'Documentos',
    'Downloads': 'Descargas',
    'Desktop': 'Escritorio',
    'Pictures': 'Imágenes',
    'Music': 'Música',
    'Videos': 'Vídeos',
    'Trash': 'Papelera',
    'Computer': 'Equipo',
    'Minimize': 'Minimizar',
    'Zoom': 'Zoom',
    'Move to {display}': 'Mover a {display}',
    'Tile Window to Left of Screen': 'Ventana a la izquierda de la pantalla',
    'Tile Window to Right of Screen': 'Ventana a la derecha de la pantalla',
    'Bring All to Front': 'Traer todo al frente',
    '{app} Help': 'Ayuda de {app}',
    'Keyboard Shortcuts': 'Atajos de teclado',
    'Macify Website': 'Web de Macify',
    'Files': 'Archivos',
    'Main Display': 'pantalla principal',
    'Display {n}': 'pantalla {n}',
    // Live Activities
    'Charging': 'Cargando',
    'Fully Charged': 'Carga completa',
    'Battery Low': 'Batería baja',
    'On Battery': 'Con batería',
    'Connected': 'Conectado',
    'Offline': 'Sin conexión',
    'Spotlight': 'Spotlight',
    'Control Center': 'Centro de control',
};

const IS_SPANISH = GLib.get_language_names()[0].startsWith('es');

// _('Quit {app}', {app: 'Brave'}) → «Quit Brave» o «Salir de Brave».
export function _(text, values = {}) {
    let result = (IS_SPANISH && SPANISH[text]) || text;
    for (const [key, value] of Object.entries(values))
        result = result.replace(`{${key}}`, value);
    return result;
}
