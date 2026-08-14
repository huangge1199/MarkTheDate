# 构建
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json ./
# 不锁 package-lock.json，使用 npm install 自动生成
RUN npm install
COPY . .
RUN npm run build

# 运行
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]