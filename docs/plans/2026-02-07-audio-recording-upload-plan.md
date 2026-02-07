# 录音保存与上传 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** iOS 长按录音生成 .m4a 文件；FastAPI 接口接收录音并上传至 Supabase Storage 的 user-audio 桶，返回公开 URL。

**Architecture:** iOS 使用 AVAudioRecorder 录音；服务端使用 FastAPI + supabase-py 上传。录音入口在 AccountingView，服务端新增 /audio/upload 接口。

**Tech Stack:** SwiftUI/AVFoundation/Swift Testing；FastAPI/uvicorn/supabase-py/pytest

---

### Task 1: 录音文件命名与路径生成（TDD）

**Files:**
- Create: `VoiceAccount/VoiceAccountTests/AudioRecordingControllerTests.swift`
- Create: `VoiceAccount/VoiceAccount/AudioRecordingController.swift`

**Step 1: Write the failing test**

```swift
import Foundation
import Testing
@testable import VoiceAccount

struct AudioRecordingControllerTests {
    @Test func recordingFileNameShouldBeM4a() throws {
        let fixedDate = Date(timeIntervalSince1970: 1_700_000_000)
        let url = try AudioRecordingController.makeRecordingURL(date: fixedDate, fileManager: .default)

        #expect(url.lastPathComponent.hasPrefix("voice-"))
        #expect(url.pathExtension == "m4a")
    }
}
```

**Step 2: Run test to verify it fails**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" test`
Expected: FAIL (编译错误：找不到 `AudioRecordingController` 或 `makeRecordingURL`)

**Step 3: Write minimal implementation**

```swift
import Foundation

final class AudioRecordingController {
    static func makeRecordingURL(date: Date, fileManager: FileManager) throws -> URL {
        guard let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first else {
            throw CocoaError(.fileNoSuchFile)
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let filename = "voice-\(formatter.string(from: date)).m4a"
        return documents.appendingPathComponent(filename)
    }
}
```

**Step 4: Run test to verify it passes**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" test`
Expected: PASS

**Step 5: Commit**

```bash
git -C VoiceAccount add VoiceAccount/AudioRecordingController.swift VoiceAccountTests/AudioRecordingControllerTests.swift
git -C VoiceAccount commit -m "feat: add recording file name builder"
```

---

### Task 2: 录音开始/结束逻辑与权限处理（TDD）

**Files:**
- Modify: `VoiceAccount/VoiceAccount/AudioRecordingController.swift`
- Modify: `VoiceAccount/VoiceAccountTests/AudioRecordingControllerTests.swift`

**Step 1: Write the failing tests**

```swift
import AVFoundation
import Foundation
import Testing
@testable import VoiceAccount

final class RecordingSessionStub: RecordingSession {
    private(set) var didRecord = false
    private(set) var didStop = false
    var recordResult = true

    func record() -> Bool {
        didRecord = true
        return recordResult
    }

    func stop() {
        didStop = true
    }
}

struct AudioRecordingControllerTests {
    @Test @MainActor func startRecordingShouldUpdateState() async throws {
        let session = RecordingSessionStub()
        let dependencies = AudioRecordingDependencies(
            permissionProvider: { true },
            sessionFactory: { _, _ in session },
            activateSession: {},
            deactivateSession: {}
        )
        let controller = AudioRecordingController(
            fileManager: .default,
            dateProvider: { Date(timeIntervalSince1970: 1_700_000_000) },
            dependencies: dependencies
        )

        let started = await controller.startRecording()

        #expect(started)
        #expect(controller.isRecording)
        #expect(controller.lastRecordingURL != nil)
        #expect(session.didRecord)
    }

    @Test @MainActor func startRecordingShouldFailWhenPermissionDenied() async {
        let dependencies = AudioRecordingDependencies(
            permissionProvider: { false },
            sessionFactory: { _, _ in RecordingSessionStub() },
            activateSession: {},
            deactivateSession: {}
        )
        let controller = AudioRecordingController(dependencies: dependencies)

        let started = await controller.startRecording()

        #expect(!started)
        #expect(!controller.isRecording)
    }

    @Test @MainActor func stopRecordingShouldResetState() async {
        let session = RecordingSessionStub()
        let dependencies = AudioRecordingDependencies(
            permissionProvider: { true },
            sessionFactory: { _, _ in session },
            activateSession: {},
            deactivateSession: {}
        )
        let controller = AudioRecordingController(dependencies: dependencies)

        _ = await controller.startRecording()
        controller.stopRecording()

        #expect(!controller.isRecording)
        #expect(session.didStop)
    }
}
```

**Step 2: Run test to verify it fails**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" test`
Expected: FAIL（`RecordingSession`/`AudioRecordingDependencies`/`startRecording` 未定义）

**Step 3: Write minimal implementation**

```swift
import AVFoundation
import Foundation

protocol RecordingSession {
    func record() -> Bool
    func stop()
}

struct AudioRecordingDependencies {
    let permissionProvider: () async -> Bool
    let sessionFactory: (URL, [String: Any]) throws -> RecordingSession
    let activateSession: () throws -> Void
    let deactivateSession: () throws -> Void

    static var live: AudioRecordingDependencies {
        AudioRecordingDependencies(
            permissionProvider: {
                await withCheckedContinuation { continuation in
                    AVAudioSession.sharedInstance().requestRecordPermission { granted in
                        continuation.resume(returning: granted)
                    }
                }
            },
            sessionFactory: { url, settings in
                let recorder = try AVAudioRecorder(url: url, settings: settings)
                recorder.prepareToRecord()
                return SystemRecordingSession(recorder: recorder)
            },
            activateSession: {
                let session = AVAudioSession.sharedInstance()
                try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
                try session.setActive(true)
            },
            deactivateSession: {
                let session = AVAudioSession.sharedInstance()
                try session.setActive(false, options: .notifyOthersOnDeactivation)
            }
        )
    }
}

private struct SystemRecordingSession: RecordingSession {
    let recorder: AVAudioRecorder

    func record() -> Bool {
        recorder.record()
    }

    func stop() {
        recorder.stop()
    }
}

@MainActor
final class AudioRecordingController: NSObject, ObservableObject {
    @Published private(set) var isRecording = false
    @Published private(set) var lastRecordingURL: URL?

    private let fileManager: FileManager
    private let dateProvider: () -> Date
    private let dependencies: AudioRecordingDependencies
    private var session: RecordingSession?

    init(
        fileManager: FileManager = .default,
        dateProvider: @escaping () -> Date = Date.init,
        dependencies: AudioRecordingDependencies = .live
    ) {
        self.fileManager = fileManager
        self.dateProvider = dateProvider
        self.dependencies = dependencies
    }

    static func makeRecordingURL(date: Date, fileManager: FileManager) throws -> URL {
        guard let documents = fileManager.urls(for: .documentDirectory, in: .userDomainMask).first else {
            throw CocoaError(.fileNoSuchFile)
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        let filename = "voice-\(formatter.string(from: date)).m4a"
        return documents.appendingPathComponent(filename)
    }

    func startRecording() async -> Bool {
        guard !isRecording else { return true }
        let granted = await dependencies.permissionProvider()
        guard granted else { return false }

        do {
            try dependencies.activateSession()
            let url = try Self.makeRecordingURL(date: dateProvider(), fileManager: fileManager)
            let settings: [String: Any] = [
                AVFormatIDKey: kAudioFormatMPEG4AAC,
                AVSampleRateKey: 44_100,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
            ]
            let session = try dependencies.sessionFactory(url, settings)
            guard session.record() else { return false }
            self.session = session
            self.lastRecordingURL = url
            self.isRecording = true
            return true
        } catch {
            return false
        }
    }

    func stopRecording() {
        guard isRecording else { return }
        session?.stop()
        session = nil
        isRecording = false
        try? dependencies.deactivateSession()
    }
}
```

**Step 4: Run test to verify it passes**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" test`
Expected: PASS

**Step 5: Commit**

```bash
git -C VoiceAccount add VoiceAccount/AudioRecordingController.swift VoiceAccountTests/AudioRecordingControllerTests.swift
git -C VoiceAccount commit -m "feat: add audio recording controller"
```

---

### Task 3: 录音交互接入 UI（长按开始/松开结束）

**Files:**
- Modify: `VoiceAccount/VoiceAccount/AccountingView.swift`

**Step 1: Write the failing test**

此步骤属于 UI 交互集成，按现有项目惯例不编写 UI 自动化测试，改为验证编译与功能测试。

**Step 2: Run test to verify it fails**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" build`
Expected: PASS（此步用于保证改动前基线可编译）

**Step 3: Write minimal implementation**

```swift
import SwiftData
import SwiftUI

struct AccountingView: View {
    @Query(sort: \ExpenseRecord.date, order: .reverse) private var records: [ExpenseRecord]
    @Query(sort: \Category.name) private var categories: [Category]
    @AppStorage("monthlyBudget") private var monthlyBudget: Double = 6000
    @AppStorage("currencyName") private var currencyName: String = "人民币"
    @State private var showManualEntry = false
    @StateObject private var recordingController = AudioRecordingController()
    @State private var showPermissionHint = false

    private let avatarURL = URL(string: "https://images.unsplash.com/photo-1762831063004-bbd3ea38ba3a?auto=format&fit=crop&fm=jpg&ixlib=rb-4.1.0&q=60&w=200")

    private var recordingSubtitle: String {
        if showPermissionHint {
            return "请在设置允许麦克风"
        }
        if recordingController.isRecording {
            return "录音中…松开结束"
        }
        return "长按开始录音"
    }

    var body: some View {
        let now = Date()
        let calendar = Calendar.current
        let todayRecords = AnalyticsBuilder.todayRecords(from: records, now: now, calendar: calendar)
        let monthTotal = AnalyticsBuilder.monthTotal(from: records, now: now, calendar: calendar)
        let currencySymbol = CurrencySymbolProvider.symbol(for: currencyName)

        ZStack {
            Color(.systemGroupedBackground)
                .ignoresSafeArea()

            ScrollView(showsIndicators: false) {
                VStack(spacing: 20) {
                    PageHeaderView(subtitle: "记账", title: "本月支出", avatarURL: avatarURL)

                    SummaryCardView(
                        monthText: Formatters.monthString(from: now),
                        totalText: Formatters.currency(amount: monthTotal, symbol: currencySymbol, decimals: 2),
                        budgetText: Formatters.currency(amount: monthlyBudget, symbol: currencySymbol, decimals: 0)
                    )

                    HStack(spacing: 12) {
                        ActionCardView(
                            title: "语音输入",
                            subtitle: recordingSubtitle,
                            systemImage: "mic.fill",
                            isPrimary: recordingController.isRecording,
                            action: {}
                        )
                        .simultaneousGesture(
                            LongPressGesture(minimumDuration: 0.2)
                                .onChanged { _ in
                                    if recordingController.isRecording { return }
                                    Task {
                                        let started = await recordingController.startRecording()
                                        if started {
                                            showPermissionHint = false
                                        } else {
                                            showPermissionHint = true
                                            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                                                showPermissionHint = false
                                            }
                                        }
                                    }
                                }
                                .onEnded { _ in
                                    recordingController.stopRecording()
                                }
                        )
                        ActionCardView(
                            title: "手动输入",
                            subtitle: "点击录入",
                            systemImage: "pencil",
                            isPrimary: true,
                            action: { showManualEntry = true }
                        )
                    }

                    VStack(spacing: 12) {
                        HStack {
                            Text("今日记录")
                                .font(.headline)
                            Spacer()
                            Text(Formatters.dayString(from: now))
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        VStack(spacing: 12) {
                            ForEach(todayRecords) { record in
                                RecordRowView(record: record, currencySymbol: currencySymbol)
                            }
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 16)
                .padding(.bottom, 32)
            }
        }
        .sheet(isPresented: $showManualEntry) {
            ManualEntrySheetView(categories: categories, currencySymbol: currencySymbol)
        }
    }
}
```

**Step 4: Run test to verify it passes**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" build`
Expected: PASS

**Step 5: Commit**

```bash
git -C VoiceAccount add VoiceAccount/AccountingView.swift
git -C VoiceAccount commit -m "feat: add long-press recording entry"
```

---

### Task 4: 添加麦克风权限声明（配置项）

**Files:**
- Modify: `VoiceAccount/VoiceAccount.xcodeproj/project.pbxproj`

**Step 1: Write the failing test**

配置文件改动不做自动化测试。

**Step 2: Run test to verify it fails**

无需运行（配置项）。

**Step 3: Write minimal implementation**

在 `VoiceAccount` 目标的 Debug/Release buildSettings 中加入：

```
INFOPLIST_KEY_NSMicrophoneUsageDescription = "需要使用麦克风进行语音记账";
```

**Step 4: Run test to verify it passes**

Run: `xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" build`
Expected: PASS

**Step 5: Commit**

```bash
git -C VoiceAccount add VoiceAccount.xcodeproj/project.pbxproj
git -C VoiceAccount commit -m "chore: add microphone usage description"
```

---

### Task 5: FastAPI 上传接口（TDD）

**Files:**
- Create: `VoiceServer/main.py`
- Create: `VoiceServer/requirements.txt`
- Create: `VoiceServer/tests/test_upload.py`

**Step 1: Write the failing tests**

```python
from fastapi.testclient import TestClient
import main

class FakeStorage:
    def __init__(self):
        self.uploaded = None

    def upload(self, path, data, file_options=None):
        self.uploaded = {"path": path, "data": data, "options": file_options}
        return {"path": path}

    def get_public_url(self, path):
        return {"publicUrl": f"https://example.com/{path}"}


def test_upload_requires_file():
    client = TestClient(main.app)
    response = client.post("/audio/upload")
    assert response.status_code == 400


def test_upload_returns_public_url(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(main, "get_storage", lambda: fake)

    client = TestClient(main.app)
    response = client.post(
        "/audio/upload",
        files={"file": ("test.m4a", b"abc", "audio/mp4")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == f"https://example.com/{fake.uploaded[path]}"
    assert body["path"] == fake.uploaded["path"]
    assert body["size"] == 3
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest VoiceServer/tests/test_upload.py -q`
Expected: FAIL（无法导入 `main` 或接口未实现）

**Step 3: Write minimal implementation**

`VoiceServer/requirements.txt`
```
fastapi
uvicorn
python-dotenv
supabase
pytest
httpx
```

`VoiceServer/main.py`
```python
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from supabase import create_client

load_dotenv()

app = FastAPI()

@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    key: str
    bucket: str


def load_settings() -> SupabaseSettings:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET", "user-audio")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Supabase 配置缺失")
    return SupabaseSettings(url=url, key=key, bucket=bucket)


def get_storage():
    settings = load_settings()
    client = create_client(settings.url, settings.key)
    return client.storage.from_(settings.bucket)


def build_object_path(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if not suffix:
        suffix = ".m4a"
    return f"{uuid.uuid4().hex}{suffix}"


def extract_public_url(response) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("publicUrl") or response.get("public_url") or ""
    return getattr(response, "publicUrl", "") or getattr(response, "public_url", "") or ""


@app.post("/audio/upload")
async def upload_audio(file: UploadFile = File(...)):
    if file is None:
        raise HTTPException(status_code=400, detail="缺少录音文件")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="录音文件为空")

    storage = get_storage()
    path = build_object_path(file.filename)
    options = {"content-type": file.content_type or "audio/mp4"}

    try:
        storage.upload(path, data, file_options=options)
    except Exception:
        raise HTTPException(status_code=502, detail="上传失败")

    public_url = extract_public_url(storage.get_public_url(path))
    if not public_url:
        raise HTTPException(status_code=502, detail="获取公开地址失败")

    return {"url": public_url, "path": path, "size": len(data)}
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest VoiceServer/tests/test_upload.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git -C VoiceServer add main.py requirements.txt tests/test_upload.py
git -C VoiceServer commit -m "feat: add audio upload api"
```

---

### Task 6: 本地验证（冒烟）

**Files:**
- Verify: `VoiceAccount` 编译与测试
- Verify: `VoiceServer` 测试

**Step 1: Run tests**

```bash
xcodebuild -project VoiceAccount/VoiceAccount.xcodeproj -scheme VoiceAccount -destination "platform=iOS Simulator,name=iPhone 15" test
python -m pytest VoiceServer/tests/test_upload.py -q
```

**Step 2: Record results**

将输出记录到 `.codex/testing.md` 与 `verification.md`。

**Step 3: Commit**

```bash
git add .codex/testing.md verification.md
git commit -m "test: record local verification"
```

