import ctypes
import sys


def configure_application_identity(app_id: str) -> None:
    if sys.platform != "win32":
        return
    setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = (ctypes.c_wchar_p,)
    setter.restype = ctypes.c_long
    result = setter(app_id)
    if result != 0:
        raise OSError(result, "Could not configure launcher taskbar identity")
