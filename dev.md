# Problem
After first trial on new  fresh windows machine it was found that it shares folder correctly but 
1.Does not share it with everyone and thus it will be needed to be done externally
    -Usually you would go to folder to be shared right click properties security edit add everyone fullcontrol apply
    -But i think it will be better to create a user named WinShare for more isolated behaviour
    -As of now no extra settings needs to be changed such as disable password protected sharing

### Step1
    -net user winshare qwertyuiop /add
        this creates a new user named winshare with password
        this runs only on admin powershell
    -net localgroup "Users" winshare /delete
        this makes it so that the new user created is only there for file sharing 
        otherwise this creation of new user would create a new profie such as admin to be selected when you start pc
    -icacls "C:\Path\To\ppts" /grant winshare:(OI)(CI)R /T
        this basically shares folder to winshare user 
    -icacls "C:\Path\To\ppts" /inheritance:e
        this means that after sharing if shared folder is changed on host then new files also inherit sharing properties
        ideally this should be run b4 grant winshare command

## Update
As of now the program works well on androids to check for windows and on isolated platforms is the next step

### If everything orks next step would be to get it add help section