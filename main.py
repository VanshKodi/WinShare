import os
import sys
import shutil
import shlex
import ctypes
import subprocess
import socket
from InquirerPy import inquirer
from InquirerPy.separator import Separator

POWER_SHELL = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")

# ================= USER CONFIG =================
SHARE_USER = "winshare"
SHARE_PASSWORD = "qwertyuiop"
ACCESS_LEVEL = "R"      # R = Read | M = Modify | F = Full
# ===============================================

ACCESS_MAP = {
    "R": "Read",
    "M": "Change",
    "F": "Full"
}

CMD_CHECK_USER = 'Get-LocalUser -Name "{user}" -ErrorAction SilentlyContinue'
CMD_CREATE_USER = 'net user {user} {password} /add'
CMD_DISABLE_PWD_CHANGE = 'net user {user} /passwordchg:no'
CMD_CHECK_GROUP_MEMBER = 'Get-LocalGroupMember -Group "Users" -Member "{user}" -ErrorAction SilentlyContinue'
CMD_REMOVE_USERS_GROUP = 'net localgroup "Users" {user} /delete'
CMD_ENABLE_INHERITANCE = 'icacls "{path}" /inheritance:e'
CMD_GRANT_NTFS = 'icacls "{path}" /grant "{user}:(OI)(CI){access}" /T'
CMD_CHECK_SHARE = 'Get-SmbShare -Name "{share}" -ErrorAction SilentlyContinue'
CMD_CREATE_SHARE = 'New-SmbShare -Name "{share}" -Path "{path}" -ErrorAction SilentlyContinue'
CMD_GRANT_SMB = 'Grant-SmbShareAccess -Name "{share}" -AccountName {user} -AccessRight {smb_access} -Force'
CMD_REMOVE_SHARE = 'Remove-SmbShare -Name "{share}" -Force'
CMD_LIST_SHARES = 'Get-SmbShare | Select-Object Name,Path'


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
    if len(sys.argv) > 1:
        params += " " + shlex.join(sys.argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit(0)


def run_ps(cmd):
    return subprocess.run([POWER_SHELL, "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True)


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


def show_help():
    clear_screen()
    hostname = socket.gethostname()
    print(f"""
==================== HELP ====================

Windows (Client):
    On the device where you want to access the share.
    Win + R → \\\\{hostname}
    Or directly:
    \\\\{hostname}\\<ShareName>
    <ShareName> is the folder name you shared seen in <List Shares>.
   
Android:
  Process Varies from app to app, generally:
    1. Open SMB client app(Cx File Explorer is recomended)
    2. Go to network section.
    3. Add New Location
    4. Remote then Local Network.
    5. Enter the following details:

Credentials:
  Username: {SHARE_USER}
  Password: {SHARE_PASSWORD}
  
If These dont work then try using your IP address:
by running ipconfig in cmd and looking for IPv4 Address.
then apply credentials as above.

Notes:
  • Hostname works best for Windows-to-Windows
  • Android SMB clients usually require IP

================== ADVANCED ==================
You can change the default username and password manyally by opening main.py in a text editor
going to line number 13 and 14 and changing the values of SHARE_USER and SHARE_PASSWORD

Also You can change the access level by changing the value of ACCESS_LEVEL on line 15 to:
    R = Read Only 
    M = Modify (Read/Write)
    F = Full Control
Please procede with caution when changing access levels as it may expose your files to unwanted changes.
===============================================
""")
    
    input("Press Enter to return...")


def settings_menu():
    global SHARE_USER, SHARE_PASSWORD
    clear_screen()
    SHARE_USER = inquirer.text(message="Enter new share username:", default=SHARE_USER).execute()
    SHARE_PASSWORD = inquirer.secret(message="Enter new password:").execute()
    print("Settings updated. Re-run share setup to apply changes.")
    input("Press Enter...")


def list_shares():
    clear_screen()
    res = run_ps(CMD_LIST_SHARES)
    print(res.stdout if res.stdout.strip() else "No shares found")
    input("Press Enter...")


def remove_share():
    clear_screen()
    res = run_ps(CMD_LIST_SHARES)
    shares = []

    for line in res.stdout.splitlines()[2:]:
        parts = line.split()
        if parts:
            shares.append(parts[0])

    if not shares:
        print("No shares to remove")
        input("Press Enter...")
        return

    shares.append("⬅ Back")

    choice = inquirer.select(
        message="Select share to remove:",
        choices=shares
    ).execute()

    if choice == "⬅ Back":
        return

    run_ps(CMD_REMOVE_SHARE.format(share=choice))
    print(f"Share '{choice}' removed")
    input("Press Enter...")


def setup_winshare(path):
    if not os.path.isdir(path):
        print("Invalid path")
        input("Press Enter...")
        return

    share = os.path.basename(path.rstrip("\\/"))
    smb_access = ACCESS_MAP[ACCESS_LEVEL]

    if not run_ps(CMD_CHECK_USER.format(user=SHARE_USER)).stdout.strip():
        run_ps(CMD_CREATE_USER.format(user=SHARE_USER, password=SHARE_PASSWORD))
        run_ps(CMD_DISABLE_PWD_CHANGE.format(user=SHARE_USER))

    if run_ps(CMD_CHECK_GROUP_MEMBER.format(user=SHARE_USER)).stdout.strip():
        run_ps(CMD_REMOVE_USERS_GROUP.format(user=SHARE_USER))

    run_ps(CMD_ENABLE_INHERITANCE.format(path=path))
    run_ps(CMD_GRANT_NTFS.format(path=path, user=SHARE_USER, access=ACCESS_LEVEL))

    if not run_ps(CMD_CHECK_SHARE.format(share=share)).stdout.strip():
        run_ps(CMD_CREATE_SHARE.format(share=share, path=path))

    run_ps(CMD_GRANT_SMB.format(share=share, user=SHARE_USER, smb_access=smb_access))
    print(f"Share '{share}' ready")
    input("Press Enter...")


def main_menu():
    while True:
        clear_screen()
        choice = inquirer.select(
            message="WinShare Manager",
            choices=[
                "Share new folder",
                "List shares",
                "Remove share",
                "Help",
                "Settings",
                "Exit"
            ]
        ).execute()

        if choice == "Share new folder":
            path = inquirer.text(message="Enter folder path:").execute()
            setup_winshare(path)
        elif choice == "List shares":
            list_shares()
        elif choice == "Remove share":
            remove_share()
        elif choice == "Help":
            show_help()
        elif choice == "Settings":
            settings_menu()
        elif choice == "Exit":
            break


if __name__ == "__main__":
    ensure_admin()
    main_menu()
