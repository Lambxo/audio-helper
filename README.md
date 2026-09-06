# 语音约碰面地点（audio_helper）

按语音描述"我在A，朋友在B，帮我们找个中间的某类店铺"，自动完成
录音 → 识别 → 提取地址与需求 → 查询坐标 → 计算中点并搜店 → 展示结果 → 语音播报
的全栈示例项目。第一版仅支持同一座城市内的两个人。

> 本 README 会随开发进度逐轮补充，当前内容只覆盖已经实现的部分。

## 技术栈

- 前端：React + Vite + JavaScript，Axios 发请求，MediaRecorder 录音（尚未实现）。
- 后端：FastAPI + httpx（调用外部服务）+ Pydantic（数据校验）。
- 外部服务（尚未接入）：百炼 Qwen3-ASR-Flash / Qwen3-TTS-Flash / deepseek-v4-flash，高德 Web服务 API。

## 目录结构

```
project/
├── backend/
│   ├── main.py          服务入口
│   ├── api/             接口路由
│   ├── services/        外部服务调用与业务算法（占位，待实现）
│   ├── prompts/         两套 DeepSeek 提示词（占位，待实现）
│   ├── schemas.py       请求与响应的数据结构
│   ├── config.py        统一读取配置
│   ├── storage/         临时音频与查询结果（运行时生成，不提交内容）
│   ├── tests/           接口测试
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js       Axios 请求封装
│   │   └── components/
│   └── package.json
├── .gitignore
└── README.md
```

## 当前进度

- [x] 项目骨架（目录结构 / 配置读取 / CORS / 依赖清单）
- [x] `GET /health`
- [ ] `POST /upload`
- [ ] `POST /asr`
- [ ] `POST /extract`
- [ ] `POST /search`
- [ ] `POST /finalize`
- [ ] `GET /audio/{audio_id}`
- [ ] 前端录音与业务流程页面

## 环境要求

- Python 3.11
- Node.js 22.12 及以上的 22.x 版本

## 本地开发：后端

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# 当前阶段 .env 中的密钥留空即可，/health 不依赖任何外部服务

uvicorn main:app --reload --port 8003
```

启动后访问：

- 健康检查：http://localhost:8003/health
- 交互式文档：http://localhost:8003/docs

## 本地开发：前端

```bash
cd frontend
npm install
npm run dev
```

启动后访问 http://localhost:5175 ，页面会自动请求后端 `/health` 并显示连接状态。

## 测试说明

### 模拟测试（Mock，当前阶段）

`backend/tests/test_health.py` 不涉及任何外部服务，可随时运行：

```bash
cd backend
pytest
```

### 真实接口验收（尚未适用）

当前阶段没有接入任何外部服务，因此没有需要真实密钥验证的内容。
后续实现 `/asr`、`/extract`、`/search`、`/finalize` 后，本节会补充：
真实密钥填写方式、真实调用验证步骤，以及一次完整的前端全链路验收流程。
