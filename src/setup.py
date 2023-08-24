from cx_Freeze import setup, Executable

packages = ["pythonosc"]
file_include = ["config.json", "app.vrmanifest"]

build_exe_options = {"packages": packages, "include_files": file_include, 'include_msvcr': True, 'optimize': 2}

setup(
    name="AvatarParameterSync",
    version="0.1",
    description="Syncs parameters between Avatars in VRChat",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", targetName="AvatarParameterSync.exe", base=False), Executable("main.py", targetName="AvatarParameterSync_NoConsole.exe", base="Win32GUI")],
)