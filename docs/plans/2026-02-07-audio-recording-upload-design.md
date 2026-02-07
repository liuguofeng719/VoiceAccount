# 录音保存与上传设计方案

- 日期：2026-02-07
- 执行者：Codex

## 目标
实现 iOS 端长按录音并保存为 .m4a 文件；服务端 FastAPI 接收录音文件上传至 Supabase Storage 的 user-audio 桶并返回公开 URL。

## 架构概览
- 客户端：SwiftUI 负责交互与录音控制，使用 AVAudioRecorder 生成 .m4a 文件。
- 服务端：FastAPI 提供上传接口，使用 supabase-py 上传文件并返回公开 URL。

## 客户端设计（iOS）
- 录音入口：`VoiceAccount/VoiceAccount/AccountingView.swift` 的“语音输入”卡片。
- 交互方式：长按开始录音，松开结束。
- 录音控制：新增轻量录音控制器（如 `AudioRecordingController`），单一职责：请求权限、开始/结束录音、返回本地文件 URL。
- 文件格式：AAC 编码的 `.m4a`，采样率 44.1kHz，单声道。
- 文件命名：`voice-YYYYMMdd-HHmmss.m4a`，保存到 Documents 目录。
- UI 状态：录音中显示“录音中…松开结束”，并增加轻量高亮提示。

## 服务端设计（FastAPI）
- 项目结构：创建最小结构 `VoiceServer/main.py`、`VoiceServer/requirements.txt`。
- 环境配置：`VoiceServer/.env`（`SUPABASE_URL`、`SUPABASE_KEY`、`SUPABASE_BUCKET=user-audio`）。
- 接口：`POST /audio/upload`，接收 `multipart/form-data` 的 `UploadFile`。
- 上传逻辑：supabase-py Storage 上传，返回公开 URL。
- 响应格式：`{ "url": "...", "path": "...", "size": ... }`。
- 错误处理：缺文件返回 400；配置缺失 500；上传失败 502（仅功能性错误，不增加安全设计）。

## 数据流
1. 用户长按“语音输入” → 客户端开始录音。
2. 松开结束 → 保存 `.m4a` 文件 → 得到本地 URL。
3. 客户端上传文件 → FastAPI 接收 → Supabase Storage 上传。
4. 服务端返回公开 URL 给客户端。

## 测试与验证
- 客户端：新增单元测试覆盖录音控制器的文件命名与状态切换（使用 Swift Testing）。
- 服务端：新增接口测试验证缺文件与正常上传流程（本地运行）。

## 备注
- 严格遵循“复用官方 SDK/主流生态”的约束，避免自研实现。
- 不新增安全性设计与鉴权流程。
