"""Dictado falso para la prueba del Shell aislado: el mismo nombre e interfaz D-Bus que el real
(dev.dictado.Dictado1), sin audio ni Whisper. La prueba cambia su estado con TestSet y
TestLevel; StopDictation y StopTranscription lo devuelven a reposo y quedan anotados."""

from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="dev.dictado.Dictado1">
    <method name="StopDictation"/>
    <method name="StopTranscription"><arg type="s" name="path" direction="out"/></method>
    <method name="TestSet"><arg type="s" direction="in"/><arg type="s" direction="in"/></method>
    <method name="TestLevel"><arg type="d" direction="in"/></method>
    <method name="TestCalls"><arg type="as" direction="out"/></method>
    <property name="Dictation" type="s" access="read"/>
    <property name="Transcription" type="s" access="read"/>
    <property name="TranscriptionStarted" type="x" access="read"/>
    <signal name="StateChanged"><arg type="s"/><arg type="s"/></signal>
    <signal name="Level"><arg type="d"/></signal>
  </interface>
</node>"""
PATH = "/dev/dictado/Dictado"
IFACE = "dev.dictado.Dictado1"
state = {"Dictation": "idle", "Transcription": "idle", "TranscriptionStarted": 0}
calls = []


def emit(connection, name, variant):
    connection.emit_signal(None, PATH, IFACE, name, variant)


def set_state(connection, dictation, transcription):
    if transcription == "recording" and state["Transcription"] != "recording":
        state["TranscriptionStarted"] = int(GLib.get_real_time() / 1000) - 65_000   # «1:05»
    state.update(Dictation=dictation, Transcription=transcription)
    emit(connection, "StateChanged", GLib.Variant("(ss)", (dictation, transcription)))


def method(connection, _sender, _path, _iface, name, params, invocation):
    if name == "TestSet":
        set_state(connection, *params.unpack())
        invocation.return_value(None)
    elif name == "TestLevel":
        emit(connection, "Level", params)
        invocation.return_value(None)
    elif name == "TestCalls":
        invocation.return_value(GLib.Variant("(as)", (calls,)))
    elif name == "StopDictation":
        calls.append(name)
        set_state(connection, "idle", state["Transcription"])
        invocation.return_value(None)
    elif name == "StopTranscription":
        calls.append(name)
        set_state(connection, state["Dictation"], "idle")
        invocation.return_value(GLib.Variant("(s)", ("/tmp/transcript.txt",)))


def prop(_connection, _sender, _path, _iface, name):
    value = state[name]
    return GLib.Variant("x" if isinstance(value, int) else "s", value)


def acquired(connection, _name):
    info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
    connection.register_object(PATH, info, method, prop, None)


Gio.bus_own_name(Gio.BusType.SESSION, "dev.dictado.Dictado", Gio.BusNameOwnerFlags.NONE, acquired, None, None)
GLib.MainLoop().run()
