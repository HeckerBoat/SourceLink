# 云主机反向代理配置指南（CloudConfig.md）

本文档说明如何用一台公网云主机（IP：`113.46.196.84`）反向代理本地主机（IP：`100.93.80.112`）上端口 5000-6000 的服务，使外部用户可通过云主机统一访问。

## 前提条件

- 云主机与本地主机之间网络互通（建议通过内网/专线/WireGuard/Tailscale 打通，保证低延迟与安全）。
- 云主机已安装 Nginx（本文以 Nginx 为例，Windows 可用 Nginx for Windows 或 Caddy，命令类似）。
- 本地主机服务已监听 `0.0.0.0:5000-6000`（本项目默认 `FLASK_HOST=0.0.0.0`，无需改动）。

## 步骤 1：云主机安装 Nginx

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y nginx

# CentOS/RHEL
sudo yum install -y nginx

# Windows（PowerShell，使用 Chocolatey）
choco install nginx -y
```

> 安装 Nginx 是为了用其反向代理与负载均衡能力，把外部请求转发到本地主机。

## 步骤 2：配置 Nginx 反向代理

创建/编辑 Nginx 配置文件：

```bash
# Linux
sudo nano /etc/nginx/conf.d/sourcelink-proxy.conf

# Windows 默认路径
notepad "C:\tools\nginx\conf\conf.d\sourcelink-proxy.conf"
```

写入以下内容（按实际服务端口调整）：

```nginx
# 将云主机 80 端口代理到本地主机 5000 端口（SourceLink 主服务）
server {
    listen 80;
    server_name 113.46.196.84;  # 或你的域名

    location / {
        proxy_pass http://100.93.80.112:1314;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    server_name 113.46.196.84;  # 或你的域名

    location / {
        proxy_pass http://100.93.80.112:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    server_name 113.46.196.84;  # 或你的域名

    location / {
        proxy_pass http://100.93.80.112:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}

server {
    listen 80;
    server_name 113.46.196.84;  # 或你的域名

    location / {
        proxy_pass http://100.93.80.112:5002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

> 关键配置说明：
>
> - `proxy_pass`：把请求转发到本地主机的对应端口。
> - `proxy_set_header`：把真实客户端 IP、协议等信息透传给后端，避免日志里全是云主机 IP。
> - `proxy_connect_timeout / proxy_read_timeout`：防止长时间无响应导致连接挂起。

## 步骤 3：检查配置并重启 Nginx

```bash
# Linux
sudo nginx -t                # 检查配置语法是否正确
sudo systemctl restart nginx # 重启使配置生效
sudo systemctl enable nginx  # 设置开机自启

# Windows
nginx -t
nginx -s reload
```

> `nginx -t` 必须先通过，否则重启后 Nginx 可能无法启动。

## 步骤 4：配置云主机安全组/防火墙

在云服务商控制台开放所需端口：

- TCP 80（HTTP 入口）
- TCP 443（如后续上 HTTPS）
- 如需直接暴露 5000-6000，也一并开放

同时确保云主机本机防火墙放行：

```bash
# Linux（ufw 示例）
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload

# Windows PowerShell（管理员）
New-NetFirewallRule -DisplayName "Allow HTTP 80" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName "Allow HTTPS 443" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

> 只开放必要端口，减少攻击面。

## 步骤 5：本地主机确认服务监听外网地址

本地主机启动服务前，确认 `.env` 中：

```ini
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

> `0.0.0.0` 表示监听所有网卡，这样云主机才能通过 `100.93.80.112` 访问到服务。

## 步骤 6：验证代理是否生效

```bash
# 在云主机上执行，测试能否访问本地服务
curl http://100.93.80.112:5000/api/config/public

# 在外部机器执行，通过云主机 IP 访问
curl http://113.46.196.84/api/config/public
```

> 若外部能返回与本地相同的 JSON 响应，说明反向代理成功。

## 步骤 7（可选）：配置 HTTPS

```bash
# 使用 Certbot 申请免费 SSL 证书（需域名已解析到云主机）
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

> HTTPS 可加密传输，避免网盘链接、密码等敏感信息被中间人窃取。

## 步骤 8（可选）：端口范围批量代理（5000-6000）

若需把云主机 5000-6000 端口全部映射到本地同端口，可在 Nginx 使用 `stream` 模块做 TCP 转发：

```nginx
stream {
    server {
        listen 1314;
        proxy_pass 100.93.80.112:5001;
    }
    server {
        listen 5000;
        proxy_pass 100.93.80.112:5000;
    }
    server {
        listen 5001;
        proxy_pass 100.93.80.112:5001;
    }
    server {
        listen 5001;
        proxy_pass 100.93.80.112:5002;
    }
}
```

> `stream` 是四层 TCP 代理，适用于非 HTTP 服务或需要直接端口映射的场景。

## 常见问题

1. **502 Bad Gateway**：本地服务未启动或云主机与本地主机网络不通，检查 `curl http://100.93.80.112:5000` 是否通。
2. **访问慢**：云主机与本地主机之间延迟高，建议使用内网互联或同地域部署。
3. **IP 显示为云主机**：确认 `proxy_set_header X-Real-IP` 已配置，后端日志读取该头获取真实 IP。
4. **WebSocket 不通**：若后续用到 WebSocket，需加 `proxy_http_version 1.1` 与 `Upgrade` 头。

***

配置完成后，外部用户访问 `http://113.46.196.84` 即可使用部署在本地主机 5000 端口的 SourceLink 服务。
