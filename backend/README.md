# MarkTheDate 后端

## 本地运行

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env       # 填入 AI key / SMTP 等
uvicorn app.main:app --reload --port 8000
```

访问 http://localhost:8000/docs 查看 API 文档。

## Docker

```bash
docker build -t markthedate-backend .
docker run -p 8000:8000 -v $(pwd)/data:/app/data markthedate-backend
```