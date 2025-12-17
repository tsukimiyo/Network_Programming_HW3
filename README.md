# 112550205 Network Programming HW3

請先將專案clone至本地端，並進入專案資料夾：

若使用平台為Windows，請在專案目錄下開啟 PowerShell 執行以下指令
1. 環境設定(Setup)： ./run.ps1 setup
2. 啟動 Client： ./run.ps1 client
3. 啟動 Developer： ./run.ps1 developer

若使用平台為Linux，請使用 Makefile (不保證能正常運作)
1. 環境設定(Setup)： make setup
2. 啟動 Client： make client
3. 啟動 Developer： make developer

如果想要更改各個file中的IP位置：
1. /servers/developer_server.py : 在class DeveloperServer()的 __init__中可以修改self.HOST = ... & self.DBIP = ...(約程式碼第9行)
2. /servers/lobby_server.py : 在class LobbyServer()的 __init__中可以修改self.HOST = ... & self.DBIP = ...(約程式碼第12行)
3. /servers/DB_server.py : 在第13行處可以修改 HOST = ...
4. /client/lobby_client.py : 在class PlayerClient()的 __init__中可以修改self.LOBBY_IP = ... (約程式碼第42行)
5. /developer/developer_client.py : 在class DeveloperClient()的 __init__中可以修改self.LOBBY_IP = ... (約程式碼第26行)

如何使用example_games？
將example_games底下的遊戲資料夾(ex: Connect_4)整份資料夾複製，並放到/developer/games/底下，接下來利用developer_client將遊戲檔案上傳至server即可。