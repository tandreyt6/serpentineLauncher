from fnmatch import fnmatchcase
from base64 import b64encode
import sys
from urllib.parse import unquote
from urllib.request import ProxyHandler, _parse_proxy, getproxies_environment, proxy_bypass_environment, proxy_bypass as system_proxy_bypass


class ConfiguredProxyHandler(ProxyHandler):
    def proxy_open(self, request, proxy, scheme):
        original = request.type
        proxy_type, username, password, endpoint = _parse_proxy(proxy)
        proxy_type = proxy_type or original
        if request.host and proxy_bypass(request.host):
            return None
        if username is not None and password is not None:
            credentials = unquote(username) + ':' + unquote(password)
            request.add_header('Proxy-Authorization', 'Basic ' + b64encode(credentials.encode()).decode('ascii'))
        request.set_proxy(unquote(endpoint), proxy_type)
        if original == proxy_type or original == 'https':
            return None
        return self.parent.open(request, timeout=request.timeout)


def proxy_bypass(host):
    environment = getproxies_environment()
    if environment:
        return proxy_bypass_environment(host, environment)
    if sys.platform != 'win32':
        return system_proxy_bypass(host)
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as settings:
            enabled = winreg.QueryValueEx(settings, 'ProxyEnable')[0]
            overrides = winreg.QueryValueEx(settings, 'ProxyOverride')[0]
    except OSError:
        return False
    if not enabled or not isinstance(overrides, str):
        return False
    host = host.casefold()
    if host.startswith('['):
        host = host[1:].partition(']')[0]
    elif host.count(':') == 1:
        name, port = host.rsplit(':', 1)
        if port.isdigit():
            host = name
    for pattern in overrides.split(';'):
        pattern = pattern.strip().casefold()
        if pattern == '<local>' and '.' not in host:
            return True
        if pattern and fnmatchcase(host, pattern):
            return True
    return False
