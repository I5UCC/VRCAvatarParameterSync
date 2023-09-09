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
import logging


def get_absolute_path(relative_path, script_path=__file__) -> str:
    """Gets absolute path from relative path"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(script_path)))
    return os.path.join(base_path, relative_path)


def get_padded_string(parameter, value):
    if isinstance(value, float):
        value = f"{value:.4f}"
    parameter = parameter + " "
    return f"{parameter.ljust(33, '-')} {value}"


def is_running() -> bool:
        """Checks if VRChat is running."""
        _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
        return _proc_name in (p.name() for p in process_iter())


def check_if_duplicate_message(addr, value) -> bool:
    global last_message
    if last_message == (addr, value):
        return True
    last_message = (addr, value)
    return False


def wait_get_oscquery_client():
    service_info = None
    logging.info("Waiting for VRChat to be discovered.")
    while service_info is None:
        browser = OSCQueryBrowser()
        time.sleep(2) # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    logging.info("VRChat discovered!")
    client = OSCQueryClient(service_info)
    logging.info("Waiting for VRChat to be ready.")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        time.sleep(2)
    logging.info("VRChat ready!")
    return client


def reset_params():
    global params, curr_avatar, config

    curr_avatar = qclient.query_node(AVATAR_CHANGE_PARAMETER).value[0]
    logging.info(get_padded_string("Current Avatar", curr_avatar))
    for param in config["parameters"]:
        addr = PARAMETER_PREFIX + param
        try:
            params[addr] = qclient.query_node(addr).value[0]
            logging.info(get_padded_string(param, params[addr]))
        except:
            logging.info(get_padded_string(param, None))

def set_avatar_change(addr, value):
    global params, osc_client, avatar_changed, curr_avatar

    if check_if_duplicate_message(addr, value):
        return

    avatar_changed = curr_avatar != value
    if not avatar_changed:
        logging.info("Avatar Reset, clearing parameters")
        reset_params()
        return

    curr_avatar = value
    logging.info("Avatar changed, resending parameters:")
    for key, val in params.items():
        if val is None:
            continue
        logging.info(get_padded_string(key[key.rindex("/") + 1:], val))
        osc_client.send_message(key, val)


def receive_message(addr, value):
    global params, avatar_changed

    if check_if_duplicate_message(addr, value):
        return

    time.sleep(0.5)
    if avatar_changed:
        time.sleep(1)
        avatar_changed = False
        return
    global params
    params[addr] = value
    logging.info(get_padded_string("Recieved: " + addr[19:], value))


def osc_server_serve():
    logging.info(f"Starting OSC client on {osc_server_ip}:{osc_server_port}:{http_port}")
    server.serve_forever(2)


logging.basicConfig(level=logging.DEBUG if len(sys.argv) > 1 else logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S', handlers=[logging.StreamHandler(), logging.FileHandler(get_absolute_path("log.log"))])


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
last_message = (None, None)

if osc_server_port != 9001:
    logging.info("OSC Server port is not default, testing port availability and advertising OSCQuery endpoints")
    if osc_server_port <= 0 or not check_if_udp_port_open(osc_server_port):
        osc_server_port = get_open_udp_port()
    if http_port <= 0 or not check_if_tcp_port_open(http_port):
        http_port = osc_server_port if check_if_tcp_port_open(osc_server_port) else get_open_tcp_port()
else:
    logging.info("OSC Server port is default.")

disp = dispatcher.Dispatcher()
disp.map(AVATAR_CHANGE_PARAMETER, set_avatar_change)
for param in config["parameters"]:
    disp.map(PARAMETER_PREFIX + param, receive_message)

try:
    logging.info("Waiting for VRChat to start.")
    while not is_running():
        time.sleep(3)
    logging.info("VRChat started!")
    osc_client = udp_client.SimpleUDPClient(osc_server_ip, osc_client_port)
    qclient = wait_get_oscquery_client()
    reset_params()
    server = osc_server.BlockingOSCUDPServer((osc_server_ip, osc_server_port), disp)
    server_thread = Thread(target=osc_server_serve, daemon=True)
    server_thread.start()
    oscqs = OSCQueryService("AvatarParameterSync", http_port, osc_server_port)
    oscqs.advertise_endpoint(AVATAR_CHANGE_PARAMETER, access="readwrite")
    for param in config["parameters"]:
        oscqs.advertise_endpoint(PARAMETER_PREFIX + param, access="readwrite")
    if len(params) <= 0:
        logging.info("You didn't set any parameters in the config.json file, please set some parameters and restart the program.")

    while is_running():
        time.sleep(10)

    sys.exit(0)
except OSError as e:
    logging.error("You can only bind to the port 9001 once.")
    logging.error(traceback.format_exc())
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, "You can only bind to the port 9001 once.", "AvatarParameterSync - Error", 0)
    sys.exit(1)
except zeroconf._exceptions.NonUniqueNameException as e:
    logging.error("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except KeyboardInterrupt:
    logging.info("Exiting...")
    sys.exit(0)
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, traceback.format_exc(), "AvatarParameterSync - Unexpected Error", 0)
    logging.error(traceback.format_exc())
    sys.exit(1)
