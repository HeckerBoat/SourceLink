"""Flask 应用工厂：装配配置、蓝图、错误处理与前端静态资源。"""

import logging

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from .config import Config
from .init_db import init_and_seed
from .api.admin import bp as admin_bp
from .api.auth import bp as auth_bp
from .api.captcha import bp as captcha_bp
from .api.feedback import bp as feedback_bp
from .api.resources import bp as resource_bp
from .api.verification import bp as verification_bp


def _json_error(message: str, http_status: int):
    return jsonify({"code": 1, "msg": message, "data": None}), http_status


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 建表 + 初始化管理员 / 默认配置（配置同步到内存缓存，相当于同步给前端）
    init_and_seed()

    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        expose_headers=["X-Refresh-Token"],
    )

    for blueprint in (auth_bp, captcha_bp, verification_bp, resource_bp, feedback_bp, admin_bp):
        app.register_blueprint(blueprint, url_prefix="/api")

    # 全局异常：完整堆栈打印在后端，前端只收到 JSON 提示，不弹错误窗
    @app.errorhandler(Exception)
    def handle_exception(exc):
        app.logger.exception("未处理异常: %s", exc)
        if request.path.startswith("/api/"):
            return _json_error("服务器内部错误，请查看后端日志", 500)
        return _json_error("服务器内部错误", 500)

    @app.errorhandler(404)
    def handle_404(_exc):
        if request.path.startswith("/api/"):
            return _json_error("接口不存在", 404)
        return _json_error("接口不存在", 404)

    # 生产形态：托管 Frontend/dist 的 Vue 构建产物（前端未构建时不注册，提示先 build）
    dist_dir = Config.FRONTEND_DIST
    if dist_dir.exists():

        @app.get("/")
        def index():
            return send_from_directory(dist_dir, "index.html")

        @app.get("/<path:path>")
        def static_files(path: str):
            target = dist_dir / path
            if target.is_file():
                return send_from_directory(dist_dir, path)
            return send_from_directory(dist_dir, "index.html")

    else:

        @app.get("/")
        def index_placeholder():
            return (
                "<h2>SourceLink 后端已启动</h2>"
                "<p>尚未检测到 Frontend/dist，请先在 Frontend 目录执行 "
                "<code>npm install &amp;&amp; npm run build</code> 构建前端。</p>"
                "<p>接口前缀：<code>/api</code></p>"
            )

    app.logger.info("SourceLink 服务就绪，前端目录: %s", dist_dir if dist_dir.exists() else "未构建")
    return app
