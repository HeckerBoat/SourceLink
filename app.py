"""SourceLink 项目统一启动入口。

运行方式（PowerShell）：
    .\\.venv\\Scripts\\python.exe app.py

启动后：
- 后端 API：http://<本机IP>:5000/api
- 前端页面：http://<本机IP>:5000/  （需先构建 Frontend）
"""

from backend.app import create_app
from backend.config import Config

app = create_app()

if __name__ == "__main__":
    print(f" * SourceLink 监听地址: http://{Config.HOST}:{Config.PORT}")
    print(f" * 管理员账号: {Config.ADMIN_USERNAME} / {Config.ADMIN_PASSWORD} (手机: {Config.ADMIN_PHONE})")
    app.run(host=Config.HOST, port=Config.PORT, debug=False)
