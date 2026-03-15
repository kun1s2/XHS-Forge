# 第一阶段：构建阶段
FROM node:20-slim AS build-stage

WORKDIR /app

# 复制依赖定义
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制前端源码
COPY . .

# 执行构建
RUN npm run build

# 第二阶段：生产阶段 (使用 Nginx 托管)
FROM nginx:stable-alpine AS production-stage

# 复制构建产物到 Nginx 目录
COPY --from=build-stage /app/dist /usr/share/nginx/html

# 复制 Nginx 配置（处理 Vue Router history 模式等）
# 如果没有自定义配置，可以使用默认
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
