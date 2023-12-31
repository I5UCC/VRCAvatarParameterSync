from cx_Freeze import setup, Executable

packages = ["pythonosc", "psutil", "zeroconf", "json", "threading", "time", "os", "sys", "ctypes", "traceback", "openvr"]
file_include = ["config.json", "app.vrmanifest"]

build_exe_options = {"packages": packages, "include_files": file_include, 'include_msvcr': True, 'optimize': 2}

setup(
    name="AvatarParameterSync",
    version="0.2.1",
    description="AvatarParameterSync",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", target_name="AvatarParameterSync.exe", base=False), Executable("main.py", target_name="AvatarParameterSync_NoConsole.exe", base="Win32GUI")],
)