import os
import sys
import json
import shutil
import shlex
import ctypes
import subprocess
from InquirerPy import inquirer
from InquirerPy.separator import Separator

POWER_SHELL = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")

# ================= CONFIG =================
SHARE_USER = "winshare"
SHARE_PASSWORD = "qwertyuiop"
ACCESS_LEVEL = "R"   # R | M | F
# =========================================

ACCESS_MAP = {
    "R": "Read",
    "M": "Change",
    "F": "Full"
}

CMD_CREATE_USER = 'net user {user} {password} /add'
CMD_DISABLE_PWD_CHANGE = 'net user {user} /passwordchg:no'
CMD_REMOVE_USERS_GROUP = 'net localgroup "Users" {user} /delete'
CMD_ENABLE_INHERITANCE = 'icacls "{path}" /inheritance:e'
CMD_GRANT_NTFS = 'icacls "{path}" /grant {user}:(OI)(CI){access} /T'
CMD_CREATE_SHARE = 'New-SmbShare -Name "{share}" -Path "{path}" -ErrorAction SilentlyContinue'
CMD_GRANT_SMB = (
    'Grant-SmbShareAccess -Name "{share}" '
    '-AccountName {user} -AccessRight {smb_access} -Force'
)
CMD_REMOVE_SHARE = 'Remove-SmbShare -Name "{share}" -Force'

# -------------------------------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_admin():
    if is_admin():
        return
    params = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    sys.exit(0)

def run_ps(cmd):
    args = [POWER_SHELL, "-NoProfile", "-NonInteractive", "-Command", cmd]
    return subprocess.run(args, capture_output=True, text=True)

# -------------------------------------------------

def setup_winshare(path):
    if not os.path.isdir(path):
        print("Invalid path")
        input("Press Enter...")
        return

    share = os.path.basename(path.rstrip("\\/"))
    smb_access = ACCESS_MAP[ACCESS_LEVEL]

    commands = [
        CMD_CREATE_USER.format(user=SHARE_USER, password=SHARE_PASSWORD),
        CMD_DISABLE_PWD_CHANGE.format(user=SHARE_USER),
        CMD_REMOVE_USERS_GROUP.format(user=SHARE_USER),

        CMD_ENABLE_INHERITANCE.format(path=path),
        CMD_GRANT_NTFS.format(
            path=path,
            user=SHARE_USER,
            access=ACCESS_LEVEL
        ),

        CMD_CREATE_SHARE.format(share=share, path=path),
        CMD_GRANT_SMB.format(
            share=share,
            user=SHARE_USER,
            smb_access=smb_access
        )
    ]

    for cmd in commands:
        res = run_ps(cmd)
        if res.returncode != 0 and res.stderr:
            print("Failed:", cmd)
            print(res.stderr)

    print(f"Share '{share}' created for user '{SHARE_USER}'")
    input("Press Enter...")

# -------------------------------------------------

def remove_share():
    name = inquirer.text(message="Enter share name to remove:").execute().strip()
    if not name:
        return
    res = run_ps(CMD_REMOVE_SHARE.format(share=name))
    print(res.stdout or res.stderr)
    input("Press Enter...")

def list_shares():
    res = run_ps("Get-SmbShare | Select Name,Path")
    print(res.stdout)
    input("Press Enter...")

# -------------------------------------------------

def main_menu():
    while True:
        clear_screen()
        choice = inquirer.select(
            message="Main Menu",
            choices=[
                "Share new folder",
                "Remove share",
                "List shares",
                "Exit"
            ],
        ).execute()

        if choice == "Share new folder":
            path = inquirer.text(message="Enter folder path:").execute().strip()
            setup_winshare(path)

        elif choice == "Remove share":
            remove_share()

        elif choice == "List shares":
            list_shares()

        elif choice == "Exit":
            break

# -------------------------------------------------

if __name__ == "__main__":
    ensure_admin()
    main_menu()
