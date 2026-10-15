@echo off
rem 激活虚拟环境
call .\.venv\Scripts\activate.bat

rem 启动app.py 文件
.\.venv\Scripts\python.exe app.py

rem 暂停脚本，方便查看输出结果
rem pause

rem 退出虚拟环境
deactivate
