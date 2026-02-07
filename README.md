# Voice 项目概述与部署

## 项目概述
本项目包含三部分：

- `VoiceAccount/`：iOS 客户端（SwiftUI + SwiftData）。支持录音、上传、AI 解析、编辑并保存记账条目。
- `VoiceServer/`：服务端（FastAPI）。提供 `/audio/upload` 与 `/audio/parse` 接口，负责上传音频到 Supabase 并调用 AI 解析。
- `VoiceAccounting/`：前端原型与设计资料（HTML + 文档）。

## 目录结构
- `VoiceAccount/`：iOS 客户端工程
- `VoiceServer/`：FastAPI 服务
- `VoiceAccounting/`：原型与设计文档
- `docs/`：项目计划与说明

## 部署流程

### 1) 服务端（VoiceServer）
前置条件：已安装 Python 3.12（建议使用虚拟环境）

1. 进入服务端目录
   ```bash
   cd VoiceServer
   ```
2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```
3. 配置环境变量（示例）
   在 `VoiceServer/.env` 中配置：
   ```env
   SUPABASE_URL=你的supabase项目地址
   SUPABASE_SERVICE_ROLE_KEY=你的service_role_key
   DASHSCOPE_API_KEY=你的DashScope Key
   # 可选：DASHSCOPE_BASE_URL、DASHSCOPE_MODEL、SUPABASE_BUCKET
   ```
4. 启动服务
   ```bash
   uvicorn main:app --reload
   ```

服务默认监听：`http://127.0.0.1:8000`

### 2) iOS 客户端（VoiceAccount）
前置条件：macOS + Xcode

1. 打开工程
   - 使用 Xcode 打开 `VoiceAccount/VoiceAccount.xcodeproj`
2. 配置服务端地址
   - 在 App 的设置页填写 `voiceServerBaseURL`
   - 真机测试需使用局域网 IP（例如 `http://192.168.x.x:8000`）
3. 运行
   - 选择模拟器或真机运行

## 运行流程（简要）
1. 点击“录音”
2. 开始录制 → 结束录制自动上传
3. AI 解析完成后弹窗显示条目
4. 用户编辑金额/标题/分类/时间并确认保存到本地

## 常见问题
- 解析失败：检查 `DASHSCOPE_API_KEY` 与网络访问是否正常
- 上传失败：检查 `SUPABASE_URL` 与 `SUPABASE_SERVICE_ROLE_KEY`
- 真机无法访问服务端：确认手机与电脑同一局域网，并使用局域网 IP
