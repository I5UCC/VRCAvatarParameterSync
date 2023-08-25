from pythonosc import dispatcher, osc_server, udp_client
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port, check_if_tcp_port_open, check_if_udp_port_open
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from threading import Thread
from json import load
from psutil import process_iter
import sys
import os
import time
import ctypes
import zeroconf
import traceback


def get_absolute_path(relative_path, script_path=__file__) -> str:
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(script_path)))
    return os.path.join(base_path, relative_path)


def print_padded(parameter, value):
    if isinstance(value, float):
        value = f"{value:.4f}"
    print(f"{parameter.ljust(23, ' ')}\t{value}")


def is_running() -> bool:
        """Checks if VRChat is running."""
        _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
        return _proc_name in (p.name() for p in process_iter())


def wait_get_oscquery_client():
    service_info = None
    print("Waiting for VRChat to be discovered.", end="")
    while service_info is None:
        print(".", end="")
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    print("\nVRChat discovered!")
    client = OSCQueryClient(service_info)
    print("Waiting for VRChat to be ready.", end="")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        print(".", end="")
        time.sleep(2)
    print("\nVRChat ready!")
    return OSCQueryClient(service_info)


def reset_params():
    global params, curr_avatar, config

    curr_avatar = qclient.query_node(AVATAR_CHANGE_PARAMETER).value[0]
    print_padded("Current Avatar:", curr_avatar)
    for param in config["parameters"]:
        addr = PARAMETER_PREFIX + param
        try:
            params[addr] = qclient.query_node(addr).value[0]
            print_padded(param, params[addr])
        except:
            print_padded(param, None)

def set_avatar_change(addr, value):
    global params, osc_client, avatar_changed, curr_avatar
    avatar_changed = curr_avatar != value
    if not avatar_changed:
        print("Avatar Reset, clearing parameters")
        reset_params()
        return

    curr_avatar = value
    print("Avatar changed, resending parameters:")
    for key, val in params.items():
        if val is None:
            continue
        print_padded(key[key.rindex("/") + 1:], val)
        osc_client.send_message(key, val)


def receive_message(addr, value):
    global params, avatar_changed

    time.sleep(0.5)
    if avatar_changed:
        time.sleep(1)
        avatar_changed = False
        return
    global params
    params[addr] = value
    print(f"Received message: {addr} {value}")


def osc_server_serve():
    print(f"Starting OSC client on {osc_server_ip}:{osc_server_port}:{http_port}")
    server.serve_forever(2)


config: dict = load(open(get_absolute_path("config.json", __file__)))
PARAMETER_PREFIX = "/avatar/parameters/"
AVATAR_CHANGE_PARAMETER = "/avatar/change"
qclient: OSCQueryClient = None
osc_client: udp_client.SimpleUDPClient = None
avatar_changed = False
params = {}
osc_client_port = config["port"]
osc_server_ip = config["ip"]
osc_server_port = config["server_port"]
http_port = config["http_port"]

if osc_server_port != 9001:
    print("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
    if osc_server_port <= 0 or not check_if_udp_port_open(osc_server_port):
        osc_server_port = get_open_udp_port()
    if http_port <= 0 or not check_if_tcp_port_open(http_port):
        http_port = osc_server_port if check_if_tcp_port_open(osc_server_port) else get_open_tcp_port()
else:
    print("OSC Server port is default.")

disp = dispatcher.Dispatcher()
disp.map(AVATAR_CHANGE_PARAMETER, set_avatar_change)
for param in config["parameters"]:
    disp.map(PARAMETER_PREFIX + param, receive_message)

try:
    print("Waiting for VRChat to start.", end="")
    while not is_running():
        print(".", end="")
        time.sleep(3)
    print("\nVRChat started!")
    osc_client = udp_client.SimpleUDPClient(osc_server_ip, osc_client_port)
    qclient = wait_get_oscquery_client()
    reset_params()
    server = osc_server.ThreadingOSCUDPServer((osc_server_ip, osc_server_port), disp)
    server_thread = Thread(target=osc_server_serve, daemon=True)
    server_thread.start()
except OSError as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, "You can only bind to the port 9001 once.", "AvatarParameterSync - Error", 0)
    sys.exit(1)
except zeroconf._exceptions.NonUniqueNameException as e:
    print("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "AvatarParameterSync - Unexpected Error", 0)
    print(traceback.format_exc())
    sys.exit(1)


oscqs = OSCQueryService("AvatarParameterSync", http_port, osc_server_port)
oscqs.advertise_endpoint(AVATAR_CHANGE_PARAMETER, access="readwrite")
for param in config["parameters"]:
    oscqs.advertise_endpoint(PARAMETER_PREFIX + param, access="readwrite")

if len(params) <= 0:
    print("You didn't set any parameters in the config.json file, please set some parameters and restart the program.")

while is_running():
    time.sleep(10)

sys.exit(0)
