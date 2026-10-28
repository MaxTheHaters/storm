import AppKit

func writeIconSet(to directory: URL) throws {
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    for size in [16, 32, 128, 256, 512] {
        for retina in [1, 2] {
            let pixels = size * retina
            let scale = CGFloat(pixels) / 256
            let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
                bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
            NSColor(calibratedRed: 0.157, green: 0.412, blue: 0.780, alpha: 1).setFill()
            NSBezierPath(roundedRect: NSRect(x: 4 * scale, y: 4 * scale,
                width: 248 * scale, height: 248 * scale), xRadius: 52 * scale, yRadius: 52 * scale).fill()
            let bolt = NSBezierPath()
            let points: [(CGFloat, CGFloat)] = [(148, 228), (70, 116), (118, 116), (98, 28), (194, 148), (144, 148)]
            bolt.move(to: NSPoint(x: points[0].0 * scale, y: points[0].1 * scale))
            for point in points.dropFirst() { bolt.line(to: NSPoint(x: point.0 * scale, y: point.1 * scale)) }
            bolt.close()
            NSColor.white.setFill()
            bolt.fill()
            NSGraphicsContext.restoreGraphicsState()
            let suffix = retina == 2 ? "@2x" : ""
            let file = directory.appendingPathComponent("icon_\(size)x\(size)\(suffix).png")
            try bitmap.representation(using: .png, properties: [:])!.write(to: file)
        }
    }
}

@MainActor
final class StormApp: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var status: NSTextField!
    var spinner: NSProgressIndicator!
    var retryButton: NSButton!
    var process: Process?
    var pipe: Pipe?
    var buffer = Data()
    var projectRoot: URL!
    var researchURL: URL?
    var quitting = false
    var reportedError = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let appMenu = NSMenu()
        let appItem = NSMenuItem()
        appItem.submenu = appMenu
        menu.addItem(appItem)
        appMenu.addItem(withTitle: "開啟研究介面", action: #selector(openResearch), keyEquivalent: "o").target = self
        appMenu.addItem(withTitle: "顯示啟動狀態", action: #selector(showStatus), keyEquivalent: "").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "結束 STORM", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        NSApp.mainMenu = menu
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 500, height: 240),
            styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
        window.title = "STORM"
        window.isReleasedWhenClosed = false
        let heading = NSTextField(labelWithString: "STORM")
        heading.font = .systemFont(ofSize: 28, weight: .bold)
        status = NSTextField(wrappingLabelWithString: "正在啟動研究介面…")
        status.isSelectable = true
        spinner = NSProgressIndicator()
        spinner.style = .spinning
        retryButton = NSButton(title: "重新啟動", target: self, action: #selector(startServer))
        let stack = NSStackView(views: [heading, spinner, status, retryButton])
        stack.orientation = .vertical
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: window.contentView!.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: window.contentView!.centerYAnchor),
            stack.widthAnchor.constraint(equalToConstant: 440)
        ])
        window.center()
        showStatus()
        guard let resource = Bundle.main.url(forResource: "project-root", withExtension: "txt"),
              let root = try? String(contentsOf: resource, encoding: .utf8) else {
            fail("找不到專案設定，請重新安裝 STORM.app。")
            return
        }
        projectRoot = URL(fileURLWithPath: root)
        startServer()
    }

    @objc func showStatus() {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func openResearch() {
        if let url = researchURL { NSWorkspace.shared.open(url) }
        else { showStatus() }
    }

    @objc func startServer() {
        if process?.isRunning == true { openResearch(); return }
        guard let root = projectRoot else { return }
        researchURL = nil
        reportedError = false
        buffer = Data()
        spinner.startAnimation(nil)
        retryButton.isHidden = true
        status.stringValue = "正在啟動研究介面…"
        let child = Process()
        child.executableURL = root.appendingPathComponent(".venv/bin/python")
        child.arguments = [root.appendingPathComponent("tools/macos_launcher.py").path,
            "--project-root", root.path, "--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
        child.currentDirectoryURL = root
        let output = Pipe()
        pipe = output
        child.standardOutput = output
        let log = root.appendingPathComponent("local/macos-launcher/launcher.log")
        try? FileManager.default.createDirectory(at: log.deletingLastPathComponent(), withIntermediateDirectories: true)
        _ = FileManager.default.createFile(atPath: log.path, contents: nil)
        child.standardError = try? FileHandle(forWritingTo: log)
        process = child
        do {
            try child.run()
            // One reader orders all messages before EOF/completion, including fast errors.
            DispatchQueue.global(qos: .utility).async { [weak self] in
                while true {
                    let data = output.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    DispatchQueue.main.async { self?.receive(data) }
                }
                child.waitUntilExit()
                DispatchQueue.main.async {
                    guard let self = self, self.process === child else { return }
                    if self.quitting { NSApp.reply(toApplicationShouldTerminate: true) }
                    else if !self.reportedError {
                        self.fail("STORM 已停止。請重新啟動，或查看 \(log.deletingLastPathComponent().path) 內的紀錄。")
                    }
                }
            }
        }
        catch { fail("無法啟動 STORM。請確認專案與 .venv 尚在原來的位置。\n\(error.localizedDescription)") }
    }

    func receive(_ data: Data) {
        buffer.append(data)
        while let newline = buffer.firstIndex(of: 10) {
            let line = Data(buffer.prefix(upTo: newline))
            buffer.removeSubrange(...newline)
            guard let message = try? JSONSerialization.jsonObject(with: line) as? [String: String] else { continue }
            if let error = message["error"] { fail(error) }
            if let value = message["url"], let url = URL(string: value),
               url.scheme == "http", url.host == "127.0.0.1", url.port != nil,
               url.user == nil, url.password == nil {
                researchURL = url
                spinner.stopAnimation(nil)
                status.stringValue = "服務已啟動。點 Dock 圖示可再次開啟；右鍵點 STORM 圖示並選「結束」可停止服務。"
                window.orderOut(nil)
                openResearch()
            }
        }
    }

    func fail(_ message: String) {
        if let root = projectRoot {
            let log = root.appendingPathComponent("local/macos-launcher/launcher.log")
            if let file = try? FileHandle(forWritingTo: log) {
                file.seekToEndOfFile()
                file.write(Data((message + "\n").utf8))
                try? file.close()
            }
        }
        reportedError = true
        researchURL = nil
        spinner.stopAnimation(nil)
        status.stringValue = message
        retryButton.isHidden = false
        showStatus()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        openResearch()
        return false
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        quitting = true
        guard let process = process, process.isRunning else { return .terminateNow }
        process.terminate()
        return .terminateLater
    }
}

@main
struct STORMMain {
    @MainActor
    static func main() throws {
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--write-iconset" {
            try writeIconSet(to: URL(fileURLWithPath: CommandLine.arguments[2]))
        } else {
            let app = NSApplication.shared
            let delegate = StormApp()
            app.delegate = delegate
            app.setActivationPolicy(.regular)
            withExtendedLifetime(delegate) { app.run() }
        }
    }
}
